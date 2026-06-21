/* ==========================================================================
   League History — "The Rafters"  (viewer tab)
   Fetches the raw season archive from GET /api/v1/league-history and derives
   every leaderboard + the finish grid client-side, then renders into
   #view-history. Self-contained: exposes window.LeagueHistory.render().
   ========================================================================== */
(function () {
  "use strict";
  const API = "/api/v1/league-history";
  const AUCTION_API = "/api/v1/auction-prices";
  const OWNERS_API = "/api/v1/owners";
  const $ = (s, el) => (el || document).querySelector(s);
  const ce = (t, c) => { const e = document.createElement(t); if (c) e.className = c; return e; };
  const ord = (n) => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th"));
  const posClass = (p) => (p || "").replace("/", "") || "NA";
  const skipPlayer = (n) => /D\/ST| - DEF/.test(n);
  // normalize a player name for joining auction prices ↔ end-of-season rosters
  const normName = (n) => (n || "").toLowerCase().replace(/\b(jr|sr|ii|iii|iv|v)\b\.?/g, "").replace(/[^a-z ]/g, "").replace(/\s+/g, " ").trim();
  const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  // distinct, legible-on-dark palette so every charted line reads as its own color
  const LINECOLORS = ["#4FC3F7", "#FF8A65", "#AED581", "#BA68C8", "#FFD54F", "#F06292", "#4DD0E1", "#9CCC65", "#7986CB", "#FFB74D", "#E57373", "#4DB6AC", "#DCE775", "#90A4AE", "#F48FB1", "#A1887F"];

  let DATA = null, MONEY = null, OWNER_COLOR = () => "var(--lh-silver)", built = false;
  let mvSel = new Set();   // currently-charted players on the price chart
  let bbMaxY = 80;         // fixed y-axis ceiling so toggling lines never rescales the chart

  /* shared hover tooltip (reuses #lhTip) for the money charts */
  function tipAt(html, x, y) {
    const tip = $("#lhTip"); tip.innerHTML = html; tip.classList.add("on");
    const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
    let L = x + pad, T = y + pad;
    if (L + w > innerWidth - 8) L = x - pad - w;
    if (T + h > innerHeight - 8) T = y - pad - h;
    tip.style.left = L + "px"; tip.style.top = T + "px";
  }
  const hideTip = () => $("#lhTip").classList.remove("on");

  // owner → brand color (owners.json for the active league, stable hash for departed owners)
  function buildOwnerColor(owners) {
    const map = {};
    (owners || []).forEach((o) => { if (o && o.owner_name && o.color) map[o.owner_name] = o.color; });
    return (name) => {
      if (map[name]) return map[name];
      let h = 0; for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) % 360;
      return `hsl(${h} 55% 62%)`;
    };
  }

  /* ---------------- derive everything from raw seasons ---------------- */
  function derive(seasonsIn) {
    const seasons = seasonsIn.slice().sort((a, b) => a.year - b.year);
    const years = seasons.map((s) => s.year);
    const latest = years[years.length - 1];
    const active = new Set(seasons.find((s) => s.year === latest).standings.map((t) => t.owner));
    const appear = {}, career = {};
    seasons.forEach((s) => s.standings.forEach((t) => {
      appear[t.owner] = (appear[t.owner] || 0) + 1;
      const c = career[t.owner] || (career[t.owner] = { w: 0, l: 0, t: 0 });
      c.w += t.wins || 0; c.l += t.losses || 0; c.t += t.ties || 0;
    }));

    const titles = {}, lastTitle = {}, titleYears = {};
    seasons.forEach((s) => {
      const winners = [s.champion.owner];
      if (s.shared_title) winners.push(s.runner_up.owner);
      winners.forEach((o) => { titles[o] = (titles[o] || 0) + 1; lastTitle[o] = Math.max(lastTitle[o] || 0, s.year); (titleYears[o] = titleYears[o] || []).push(s.year); });
    });
    const champions = Object.keys(titles)
      .map((o) => ({ owner: o, titles: titles[o], last: lastTitle[o], active: active.has(o) }))
      .sort((a, b) => b.titles - a.titles || b.last - a.last || a.owner.localeCompare(b.owner));

    const best = {}, bestYears = {};
    seasons.forEach((s) => { const o = s.best_record.owner; best[o] = (best[o] || 0) + 1; (bestYears[o] = bestYears[o] || []).push(s.year); });
    const regime = [...new Set([...Object.keys(titles), ...Object.keys(best)])]
      .map((o) => ({ owner: o, titles: titles[o] || 0, best: best[o] || 0, active: active.has(o) }))
      .sort((a, b) => b.best - a.best || b.titles - a.titles);

    // finish grid (regular-season rank) + rosters, in one pass
    const winpct = (t) => { const g = t.wins + t.losses + t.ties; return g ? (t.wins + 0.5 * t.ties) / g : 0; };
    const size = {}, cells = {}, rosters = {};
    seasons.forEach((s) => {
      size[s.year] = s.standings.length;
      const champO = s.champion.owner, runO = s.runner_up.owner, shared = !!s.shared_title;
      const order = s.standings.slice().sort((a, b) => winpct(b) - winpct(a) || (b.points_for || 0) - (a.points_for || 0));
      order.forEach((t, i) => {
        const rank = i + 1;
        const rec = `${t.wins}-${t.losses}` + (t.ties ? `-${t.ties}` : "");
        // a shared title makes the runner-up a co-champion, not a runner-up
        const isC = t.owner === champO || (shared && t.owner === runO);
        const isR = t.owner === runO && !shared;
        (cells[t.owner] = cells[t.owner] || {})[s.year] = { r: rank, rec, champ: isC, runner: isR };
        (rosters[t.owner] = rosters[t.owner] || {})[s.year] = {
          team: t.team_name, rec, rsRank: rank, final: t.final_rank, champ: isC, runner: isR,
          src: s.source, draft: s.draft_type,
          roster: (t.roster || []).map((e) => ({ n: e.player_name, pos: e.position || "", nfl: e.nfl_team || "", slot: e.slot || "" })),
        };
      });
    });
    const avg = (o) => { const rs = Object.values(cells[o]).map((c) => c.r); return rs.reduce((a, b) => a + b, 0) / rs.length; };
    const gridRows = Object.keys(cells)
      .map((o) => ({ owner: o, active: active.has(o), titles: titles[o] || 0, seasons: appear[o], cells: cells[o] }))
      .sort((a, b) => (b.active - a.active) || b.titles - a.titles || b.seasons - a.seasons || avg(a.owner) - avg(b.owner) || a.owner.localeCompare(b.owner));

    // loyalty: the player each manager kept rostering
    const po = {}, posmap = {}, poYears = {};
    seasons.forEach((s) => s.standings.forEach((t) => {
      const seen = new Set();
      (t.roster || []).forEach((e) => {
        const p = e.player_name;
        if (seen.has(p) || skipPlayer(p)) return;
        seen.add(p);
        po[p] = po[p] || {}; po[p][t.owner] = (po[p][t.owner] || 0) + 1; posmap[p] = e.position || "";
        (poYears[p] = poYears[p] || {}); (poYears[p][t.owner] = poYears[p][t.owner] || []).push(s.year);
      });
    }));
    const pairs = [];
    Object.keys(po).forEach((p) => {
      let bo = null, bc = 0;
      Object.entries(po[p]).forEach(([o, c]) => { if (c > bc) { bc = c; bo = o; } });
      if (bc >= 5) pairs.push({ player: p, owner: bo, seasons: bc, pos: posmap[p] || "", years: poYears[p][bo] });
    });
    pairs.sort((a, b) => b.seasons - a.seasons);
    const seenO = new Set(); const loy = [];
    pairs.forEach((pr) => { if (!seenO.has(pr.owner)) { seenO.add(pr.owner); loy.push(pr); } });
    const loyaltyActive = loy.filter((l) => active.has(l.owner)).slice(0, 8);
    const loyalty = loyaltyActive.length ? loyaltyActive : loy.slice(0, 8);

    // the ledger: career regular-season records, best win rate first (min 3 seasons)
    const winPct = (c) => { const g = c.w + c.l + c.t; return g ? (c.w + 0.5 * c.t) / g : 0; };
    const ledger = Object.keys(career)
      .filter((o) => appear[o] >= 3)
      .map((o) => ({ owner: o, ...career[o], pct: winPct(career[o]), active: active.has(o) }))
      .sort((a, b) => b.pct - a.pct || (b.w - b.l) - (a.w - a.l) || a.owner.localeCompare(b.owner));

    // league royalty: most-rostered NFL players ever (with per-season appearances for the hover)
    const pop = {}, popApp = {};
    seasons.forEach((s) => s.standings.forEach((t) => {
      const seen = new Set();
      (t.roster || []).forEach((e) => {
        const p = e.player_name; if (skipPlayer(p) || seen.has(p)) return; seen.add(p);
        pop[p] = (pop[p] || 0) + 1;
        (popApp[p] = popApp[p] || []).push({ year: s.year, owner: t.owner });
      });
    }));
    const royalty = Object.entries(pop).map(([player, n]) => ({ player, seasons: n, app: popApp[player] })).sort((a, b) => b.seasons - a.seasons).slice(0, 12);

    return {
      meta: { years, nSeasons: seasons.length, nManagers: Object.keys(appear).length, latest, active },
      champions, regime, grid: { years, size, rows: gridRows }, loyalty, ledger, royalty, rosters,
      titleYears, bestYears,
    };
  }

  /* ---------------- derive the auction-money views ----------------
     Joins the auction archive (season → owner → picks) against the
     end-of-season rosters in league history. Produces:
       burns      — auction buys NOT on their owner's final roster
       parc       — every player's price arc across the auction years
       retention  — career auction-dollar retention vs. win rate per owner   */
  function deriveMoney(seasons, auctionSeasons) {
    const winpctOf = (t) => { const g = (t.wins || 0) + (t.losses || 0) + (t.ties || 0); return g ? ((t.wins || 0) + 0.5 * (t.ties || 0)) / g : 0; };
    const posOf = {}, rosterSet = {}, meta = {}, leagueByYear = {}, ownersByYear = {};
    seasons.forEach((s) => {
      const champO = s.champion && s.champion.owner, runO = s.runner_up && s.runner_up.owner, shared = !!s.shared_title;
      const lset = leagueByYear[s.year] = new Set();
      const olist = ownersByYear[s.year] = [];
      s.standings.forEach((t) => {
        const set = new Set();
        (t.roster || []).forEach((e) => { const nn = normName(e.player_name); set.add(nn); lset.add(nn); if (e.position) posOf[nn] = e.position; });
        rosterSet[`${s.year}|${t.owner}`] = set;
        olist.push(t.owner);
        const isC = t.owner === champO || (shared && t.owner === runO);
        const isR = t.owner === runO && !shared;
        meta[`${s.year}|${t.owner}`] = {
          wins: t.wins || 0, losses: t.losses || 0, ties: t.ties || 0, winpct: winpctOf(t),
          rec: `${t.wins || 0}-${t.losses || 0}` + (t.ties ? `-${t.ties}` : ""),
          champ: isC, runner: isR, team: t.team_name,
        };
      });
    });

    const years = Object.keys(auctionSeasons).map(Number).sort((a, b) => a - b);
    const burns = [], parc = {}, parcOwner = {}, ret = {};
    years.forEach((y) => {
      const owners = (auctionSeasons[String(y)] || {}).owners || {};
      Object.entries(owners).forEach(([owner, picks]) => {
        const set = rosterSet[`${y}|${owner}`], m = meta[`${y}|${owner}`];
        const r = ret[owner] || (ret[owner] = { spend: 0, retained: 0, wins: 0, losses: 0, ties: 0, seasons: 0 });
        r.seasons++;
        if (m) { r.wins += m.wins; r.losses += m.losses; r.ties += m.ties; }
        (picks || []).forEach((p) => {
          if (skipPlayer(p.player)) return;       // D/ST: not a "superstar", and names rarely match rosters
          const nn = normName(p.player);
          const arc = parc[p.player] || (parc[p.player] = {});
          if (arc[y] == null || p.price > arc[y]) { arc[y] = p.price; (parcOwner[p.player] = parcOwner[p.player] || {})[y] = owner; }
          r.spend += p.price;
          if (set && set.has(nn)) { r.retained += p.price; return; }
          if (!set) return;                                   // no roster to judge against
          const inLeague = (leagueByYear[y] || new Set()).has(nn);
          // who finished the season with the player (the rival who claimed them off waivers)
          let claimedBy = null;
          if (inLeague) {
            for (const o2 of (ownersByYear[y] || [])) {
              if (o2 !== owner && rosterSet[`${y}|${o2}`] && rosterSet[`${y}|${o2}`].has(nn)) { claimedBy = o2; break; }
            }
          }
          burns.push({
            // a "burn" = an auction buy missing from the owner's end-of-season roster.
            // gone   = not on ANY roster at year's end (dropped, never re-rostered)
            // claimed = on a RIVAL's end-of-season roster (dropped, then picked up off waivers)
            year: y, owner, player: p.player, price: p.price, keeper: !!p.keeper,
            gone: !inLeague, claimed: inLeague, claimedBy,
            rec: m ? m.rec : "", win: m ? m.wins > m.losses : false,
            champ: m ? m.champ : false, runner: m ? m.runner : false,
          });
        });
      });
    });
    burns.sort((a, b) => b.price - a.price || a.year - b.year);

    const retention = Object.entries(ret)
      .filter(([, v]) => v.seasons >= 3 && v.spend > 0)
      .map(([owner, v]) => {
        const g = v.wins + v.losses + v.ties;
        return { owner, retPct: v.retained / v.spend * 100, winPct: g ? (v.wins + 0.5 * v.ties) / g * 100 : 0, seasons: v.seasons, spend: v.spend, retained: v.retained };
      });

    return { years, burns, parc, parcOwner, posOf, retention };
  }

  /* ---------------- scaffold ---------------- */
  function scaffold(host) {
    const money = MONEY ? moneyScaffold() : "";
    host.innerHTML =
      `<div class="lh-wrap">
        <header class="lh-mast">
          <div class="lh-eyebrow">The League · Est. 2003</div>
          <h1 class="lh-title">The Rafters</h1>
          <div class="lh-span" id="lh-span"></div>
        </header>
        <div class="lh-rail"><div class="lh-rafters" id="lh-rafters"></div></div>

        <section class="lh-sec">
          <div class="lh-sec-head"><span class="lh-num">01</span><h2>Season by Season</h2></div>
          <p class="lh-sub">Twenty-three years of finishes, one square each. <b>Gold is a title, bright is a top year, dark is a lean one.</b> A dynasty reads as a bright row, a slump as a dark stretch. Hover a name to follow one manager; the squares show regular-season finish and gold marks who actually won it. Click any square for that team's full roster.</p>
          <div class="lh-gridcard">
            <div class="lh-grid" id="lh-grid"></div>
            <div class="lh-legend" id="lh-legend"></div>
          </div>
        </section>

        <section class="lh-sec">
          <div class="lh-sec-head"><span class="lh-num">02</span><h2>Best Records vs. Titles</h2></div>
          <p class="lh-sub">Most seasons with the best regular-season record, against most championships won. They don't always go to the same manager. The gap between the two columns is the gap between dominant and decisive.</p>
          <div class="lh-talehead"><div class="l">Best records</div><div class="c">Manager</div><div class="r">Titles</div></div>
          <div class="lh-tale" id="lh-tale"></div>
        </section>

        <section class="lh-sec">
          <div class="lh-sec-head"><span class="lh-num">03</span><h2>Most-Rostered Player, by Manager</h2></div>
          <p class="lh-sub">The player each manager kept coming back for, drafted or stashed, year after year.</p>
          <div class="lh-loyal" id="lh-loyal"></div>
        </section>

        <div class="lh-cols">
          <section class="lh-sec" style="margin-top:0">
            <div class="lh-sec-head"><span class="lh-num">04</span><h2>Career Win-Loss Records</h2></div>
            <p class="lh-sub">Every manager's career regular-season record. <b>Gold is wins, the rest is losses</b>, best rate on top. Three seasons or more.</p>
            <div id="lh-ledger"></div>
            <p class="lh-foot">Regular-season games only. Playoffs aren't counted. <b>Ties score as half a win.</b></p>
          </section>
          <section class="lh-sec lh-roy" style="margin-top:0">
            <div class="lh-sec-head"><span class="lh-num">05</span><h2>Most-Rostered Players, League-Wide</h2></div>
            <p class="lh-sub">The NFL names that defined the era: most seasons rostered by <i>anyone</i> in the league. Hover a bar for every season.</p>
            <div id="lh-royalty"></div>
          </section>
        </div>
        ${money}
      </div>`;

    if (!$("#lhDrawer")) {
      const frag = ce("div");
      frag.innerHTML =
        `<div id="lhTip" class="lh-tip"></div>
         <div id="lhScrim" class="lh-scrim"></div>
         <aside id="lhDrawer" class="lh-drawer" aria-hidden="true" aria-label="Historical roster">
           <button id="lhDrawerX" class="lh-drawer-x" aria-label="Close">×</button>
           <div id="lhDrawerHead" class="lh-dhead"></div>
           <div id="lhDrawerBody" class="lh-dbody"></div>
           <div class="lh-dfoot">end-of-season roster · ‹ › or arrow keys to step through seasons</div>
         </aside>`;
      while (frag.firstChild) document.body.appendChild(frag.firstChild);
    }
  }

  /* ---------------- sections ---------------- */
  function renderBanners() {
    $("#lh-span").innerHTML =
      `<b>${DATA.meta.nSeasons}</b> seasons · <b>${DATA.meta.nManagers}</b> managers · <b>${DATA.champions.length}</b> champions`;
    const raf = $("#lh-rafters"), maxT = DATA.champions[0].titles;
    DATA.champions.forEach((c, i) => {
      const b = ce("div", "lh-banner" + (c.titles > 1 ? " champ" : ""));
      b.dataset.o = c.owner;
      const drop = 20 + Math.round((c.titles / maxT) * 30);
      b.innerHTML =
        `<div class="lh-cord" style="height:${drop}px"></div>
         <div class="lh-cloth">
           <div class="lh-bname">${c.owner}</div>
           <div class="lh-bttl">${c.titles}</div>
           <div class="lh-blbl">${c.titles > 1 ? "Titles" : "Title"}</div>
           <div class="lh-pips">${Array.from({ length: c.titles }).map(() => '<span class="lh-pip"></span>').join("")}</div>
           <div class="lh-byr">last ${c.last}</div>
         </div>`;
      raf.appendChild(b);
      setTimeout(() => b.classList.add("in"), 300 + i * 170);
    });
    raf.addEventListener("mousemove", (e) => {
      const bn = e.target.closest(".lh-banner"); if (!bn || !bn.dataset.o) { hideTip(); return; }
      tipAt(bannerTip(bn.dataset.o), e.clientX, e.clientY);
    });
    raf.addEventListener("mouseleave", hideTip);
  }

  function renderGrid() {
    const G = DATA.grid, GY = G.years, gridEl = $("#lh-grid");
    const heat = (r, N) => { const t = (N - r) / (N - 1); const L = Math.round(14 + t * 46); return `hsl(270 7% ${L}%)`; };
    let html =
      `<div class="lh-eras"><div></div><div class="lh-eseg">Yahoo · ’03–’11</div><div class="lh-eseg es">ESPN · ’12–’25</div></div>` +
      `<div class="lh-grow ghead"><div class="lh-gname"></div>` +
      GY.map((y) => `<div class="lh-yhd${y === 2012 ? " edge" : ""}">’${String(y).slice(2)}</div>`).join("") + `</div>`;
    G.rows.forEach((row) => {
      const name = `<div class="lh-gname${row.active ? "" : " gone"}" data-o="${row.owner}">${row.owner}` +
        (row.titles ? `<b>${row.titles}★</b>` : "") + `</div>`;
      const cellsH = GY.map((y) => {
        const c = row.cells[y], edge = y === 2012 ? " edge" : "";
        if (!c) return `<div class="lh-cell empty${edge}"></div>`;
        if (c.champ) return `<div class="lh-cell champ clk${edge}" data-o="${row.owner}" data-y="${y}">★</div>`;
        return `<div class="lh-cell clk${c.runner ? " runner" : ""}${edge}" data-o="${row.owner}" data-y="${y}" style="background:${heat(c.r, G.size[y])}"></div>`;
      }).join("");
      html += `<div class="lh-grow">${name}${cellsH}</div>`;
    });
    gridEl.innerHTML = html;
    $("#lh-legend").innerHTML =
      `<span><i class="lh-lg champ">★</i>won the title</span>` +
      `<span><i class="lh-lg hi"></i>strong season</span>` +
      `<span><i class="lh-lg lo"></i>down year</span>` +
      `<span><i class="lh-lg empty"></i>not in the league</span>` +
      `<span class="lh-ghint">hover a row to trace one manager</span>`;
    // diagonal cascade reveal
    const rows = [...gridEl.querySelectorAll(".lh-grow:not(.ghead)")];
    rows.forEach((rw, ri) => [...rw.querySelectorAll(".lh-cell")].forEach((c, ci) => {
      c.style.opacity = 0; c.style.transform = "translateY(7px)";
      requestAnimationFrame(() => {
        c.style.transition = "opacity .5s ease, transform .5s ease";
        c.style.transitionDelay = (0.15 + ri * 0.03 + ci * 0.018) + "s";
        c.style.opacity = ""; c.style.transform = "";
      });
    }));
    // once the cascade settles, drop the slow inline reveal transition so the
    // snappy hover lift (.12s, from the stylesheet) takes over on each cell.
    const settle = (0.15 + Math.max(0, rows.length - 1) * 0.03 + 22 * 0.018 + 0.55) * 1000;
    setTimeout(() => rows.forEach((rw) => rw.querySelectorAll(".lh-cell").forEach((c) => {
      c.style.transition = ""; c.style.transitionDelay = "";
    })), settle);
    wireGrid(gridEl);
  }

  function renderRegime() {
    const reg = DATA.regime.filter((r) => r.titles > 0 || r.best >= 2);
    const maxB = Math.max(...reg.map((r) => r.best), 1), maxC = Math.max(...reg.map((r) => r.titles), 1);
    const kingBest = reg.slice().sort((a, b) => b.best - a.best)[0].owner;
    const kingCrown = reg.slice().sort((a, b) => b.titles - a.titles)[0].owner;
    const tale = $("#lh-tale"); tale.innerHTML = "";
    reg.forEach((r, i) => {
      const king = r.owner === kingBest || r.owner === kingCrown;
      const row = ce("div", "lh-tr lh-hov" + (king ? " king" : ""));
      row.dataset.o = r.owner;
      row.innerHTML =
        `<div class="lh-barl"><span class="bv">${r.best || ""}</span><span class="b"></span></div>` +
        `<div class="who">${r.owner}</div>` +
        `<div class="lh-barr"><span class="b"></span><span class="bv">${r.titles || ""}</span></div>`;
      tale.appendChild(row);
      setTimeout(() => {
        $(".lh-barl .b", row).style.width = (r.best / maxB * 46) + "%";
        $(".lh-barr .b", row).style.width = (r.titles / maxC * 46) + "%";
      }, 200 + i * 70);
    });
    tale.addEventListener("mousemove", (e) => {
      const row = e.target.closest(".lh-tr"); if (!row || !row.dataset.o) { hideTip(); return; }
      tipAt(regimeTip(row.dataset.o), e.clientX, e.clientY);
    });
    tale.addEventListener("mouseleave", hideTip);
  }

  function renderLoyalty() {
    const loyal = $("#lh-loyal"); loyal.innerHTML = "";
    DATA.loyalty.forEach((l, i) => {
      const p = ce("div", "lh-plq" + (l.seasons >= 9 ? " top" : ""));
      p.dataset.i = i;
      p.innerHTML =
        `<span class="lh-pos ${posClass(l.pos)}">${l.pos || "—"}</span>` +
        `<div class="lh-of">${l.owner}<b>'s</b> guy</div>` +
        `<div class="lh-pl">${l.player}</div>` +
        `<div class="lh-lmeta"><span class="lh-x" data-n="${l.seasons}">×0</span><span class="lh-seas">seasons rostered</span></div>`;
      loyal.appendChild(p);
      const obs = new IntersectionObserver((es) => es.forEach((e) => {
        if (e.isIntersecting) {
          p.classList.add("in");
          let n = 0; const x = $(".lh-x", p);
          const iv = setInterval(() => { n++; x.textContent = "×" + n; if (n >= l.seasons) clearInterval(iv); }, 70);
          obs.disconnect();
        }
      }), { threshold: 0.4 });
      setTimeout(() => obs.observe(p), i * 40);
    });
    loyal.addEventListener("mousemove", (e) => {
      const card = e.target.closest(".lh-plq"); if (!card || card.dataset.i == null) { hideTip(); return; }
      tipAt(loyaltyTip(DATA.loyalty[+card.dataset.i]), e.clientX, e.clientY);
    });
    loyal.addEventListener("mouseleave", hideTip);
  }

  function renderLedger() {
    const el = $("#lh-ledger"); el.innerHTML = "";
    DATA.ledger.forEach((m, i) => {
      const row = ce("div", "lh-row lh-led lh-hov" + (m.active ? "" : " gone") + (i === 0 ? " top" : ""));
      row.dataset.o = m.owner;
      const rec = `${m.w}–${m.l}` + (m.t ? `–${m.t}` : "");
      const pct = m.pct.toFixed(3).replace(/^0/, ""); // ".597"
      row.innerHTML =
        `<div class="lh-nm">${m.owner}</div>` +
        `<div class="lh-led-track"><span class="lh-led-fill"></span></div>` +
        `<div class="lh-led-val"><span class="lh-led-pct">${pct}</span><span class="lh-led-rec">${rec}</span></div>`;
      el.appendChild(row);
      setTimeout(() => { $(".lh-led-fill", row).style.width = (m.pct * 100) + "%"; }, 250 + i * 55);
    });
    el.addEventListener("mousemove", (e) => {
      const row = e.target.closest(".lh-row"); if (!row || !row.dataset.o) { hideTip(); return; }
      tipAt(ledgerTip(row.dataset.o), e.clientX, e.clientY);
    });
    el.addEventListener("mouseleave", hideTip);
  }

  function renderRoyalty() {
    const ro = $("#lh-royalty"); ro.innerHTML = "";
    const maxR = DATA.royalty[0].seasons;
    DATA.royalty.forEach((p, i) => {
      const row = ce("div", "lh-row lh-hov");
      row.dataset.i = i;
      row.innerHTML =
        `<div class="lh-nm">${p.player}</div>` +
        `<div class="lh-track"><span class="lh-fill ${i === 0 ? "gold" : "pew"}"></span></div>` +
        `<div class="lh-val">${p.seasons}</div>`;
      ro.appendChild(row);
      setTimeout(() => { $(".lh-fill", row).style.width = (p.seasons / maxR * 100) + "%"; }, 250 + i * 55);
    });
    ro.addEventListener("mousemove", (e) => {
      const row = e.target.closest(".lh-row"); if (!row || row.dataset.i == null) { hideTip(); return; }
      tipAt(royaltyTip(DATA.royalty[+row.dataset.i]), e.clientX, e.clientY);
    });
    ro.addEventListener("mouseleave", hideTip);
  }

  // a gold star for a championship season, a silver star for a runner-up
  const starFor = (r) => r.champ ? ' <span class="lh-star ch">★</span>' : (r.runner ? ' <span class="lh-star ru">★</span>' : "");
  // one detail line for a manager's season: ’YY · team · record ★   (owner added when the list spans managers)
  function seasonLine(owner, year, withOwner) {
    const r = (DATA.rosters[owner] || {})[year] || {};
    const mid = withOwner ? `${r.team || "?"} · ${owner}` : (r.team || "?");
    return `<div class="lh-ttline"><span class="lh-tty">’${String(year).slice(2)}</span>${mid} · ${r.rec || "—"}${starFor(r)}</div>`;
  }
  const sortYrs = (ys) => (ys || []).slice().sort((a, b) => a - b);

  // §05 — every season a player was rostered, across managers
  function royaltyTip(p) {
    const rows = (p.app || []).slice().sort((a, b) => a.year - b.year).map((a) => seasonLine(a.owner, a.year, true)).join("");
    return `<div class="lh-tth">${p.player}</div><div class="lh-ttteam">${p.seasons} seasons rostered</div>${rows}`;
  }
  // top champion banners — the championship seasons
  function bannerTip(o) {
    const ys = sortYrs(DATA.titleYears[o]);
    return `<div class="lh-tth">${o}</div><div class="lh-ttteam">${ys.length} ${ys.length === 1 ? "title" : "titles"}</div>` + ys.map((y) => seasonLine(o, y)).join("");
  }
  // §02 — the best-record seasons and the title seasons behind the two bars
  function regimeTip(o) {
    const by = sortYrs(DATA.bestYears[o]), ty = sortYrs(DATA.titleYears[o]);
    let h = `<div class="lh-tth">${o}</div>`;
    if (by.length) h += `<div class="lh-ttteam">Best record · ${by.length}</div>` + by.map((y) => seasonLine(o, y)).join("");
    if (ty.length) h += `<div class="lh-ttteam" style="margin-top:8px">Titles · ${ty.length}</div>` + ty.map((y) => seasonLine(o, y)).join("");
    if (!by.length && !ty.length) h += `<div class="lh-ttline">No best records or titles yet</div>`;
    return h;
  }
  // §03 — the seasons a manager rostered their go-to player
  function loyaltyTip(l) {
    const ys = sortYrs(l.years);
    return `<div class="lh-tth">${l.player}</div><div class="lh-ttteam">${l.owner} · ${ys.length} seasons</div>` + ys.map((y) => seasonLine(l.owner, y)).join("");
  }
  // §04 — a manager's full season-by-season record
  function ledgerTip(o) {
    const ys = Object.keys(DATA.rosters[o] || {}).map(Number).sort((a, b) => a - b);
    return `<div class="lh-tth">${o}</div><div class="lh-ttteam">${ys.length} seasons</div>` + ys.map((y) => seasonLine(o, y)).join("");
  }

  /* ================= Part II · The Money ================= */
  function moneyScaffold() {
    const yrs = MONEY.years, span = yrs.length ? `${yrs[0]}–${yrs[yrs.length - 1]}` : "";
    return (
      `<div class="lh-act">
         <span class="lh-actrule"></span>
         <span class="lh-acttext">Auction Money &middot; ${span}</span>
         <span class="lh-actrule"></span>
       </div>
       <p class="lh-actsub">What each player cost at auction, what stayed on the roster, and how it lined up with winning.</p>

       <section class="lh-sec">
         <div class="lh-sec-head"><span class="lh-num">06</span><h2>Priciest Dropped Players</h2></div>
         <p class="lh-sub">The most expensive players who weren't on their manager's roster at season's end. <b>Charred bars were dropped and never re-rostered; amber bars were dropped, then claimed by a rival off waivers.</b> Glowing tags mark managers who <b>won anyway.</b> Hover a row to see who finished the year with the player.</p>
         <div class="lh-sunkcard"><div id="lh-sunk"></div></div>
         <p class="lh-foot">Keepers count as committed dollars. This counts any auction buy missing from the manager's end-of-season roster.</p>
       </section>

       <section class="lh-sec">
         <div class="lh-sec-head"><span class="lh-num">07</span><h2>Player Prices Over Time</h2></div>
         <p class="lh-sub">What each player cost at auction, season by season. Four names are charted to start; tap any chip below to add or remove a line. <b>Hover a point</b> for the price, year, and team that paid it.</p>
         <div class="lh-boardcard">
           <div class="lh-movers" id="lh-movers"></div>
           <div class="lh-board" id="lh-board"></div>
           <div class="lh-chips" id="lh-chips"></div>
         </div>
       </section>

       <section class="lh-sec">
         <div class="lh-sec-head"><span class="lh-num">08</span><h2>Auction Retention vs. Win Rate</h2></div>
         <p class="lh-sub">Two ways to win: keep the players you paid for at auction, or win with players added off waivers. Each manager's share of auction dollars still on the roster at season's end, plotted against win rate over the auction years. <b>Bigger tokens mean more seasons played.</b></p>
         <div class="lh-quad" id="lh-quad"></div>
         <p class="lh-foot">Win rate here covers the auction years (${span}) only, so it won't match the all-time Ledger above.</p>
       </section>`
    );
  }

  /* --- 06 · Priciest Dropped Players -------------------------------------- */
  function renderSunkCosts() {
    const el = $("#lh-sunk"); if (!el) return;
    el.innerHTML = "";
    const shown = MONEY.burns.slice(0, 14);
    const maxP = Math.max(1, ...MONEY.burns.map((b) => b.price));
    shown.forEach((b, i) => {
      const tag = b.champ ? `<span class="lh-btag champ">★ Champion</span>`
        : b.runner ? `<span class="lh-btag won">Runner-up</span>`
          : b.win ? `<span class="lh-btag won">Won anyway</span>` : "";
      const row = ce("div", "lh-burn lh-hov" + (b.gone ? " gone" : " claimed") + (b.win ? " winrec" : ""));
      row.dataset.i = i;
      row.innerHTML =
        `<div class="lh-bowner">${b.owner}</div>` +
        `<div class="lh-bmid">` +
          `<div class="lh-bplayer">${b.player}${b.keeper ? `<span class="lh-bkeep">keeper</span>` : ""}` +
            `<span class="lh-bstat ${b.gone ? "gone" : "claimed"}">${b.gone ? "Dropped" : "Claimed"}</span></div>` +
          `<div class="lh-btrack"><span class="lh-bfill"></span></div>` +
        `</div>` +
        `<div class="lh-bend"><div class="lh-bprice">$${b.price}</div>` +
          `<div class="lh-brec">${b.rec}${tag}</div></div>`;
      el.appendChild(row);
      setTimeout(() => { $(".lh-bfill", row).style.width = (b.price / maxP * 100) + "%"; }, 220 + i * 55);
    });
    el.addEventListener("mousemove", (e) => {
      const row = e.target.closest(".lh-burn"); if (!row || row.dataset.i == null) { hideTip(); return; }
      tipAt(burnTip(MONEY.burns[+row.dataset.i]), e.clientX, e.clientY);
    });
    el.addEventListener("mouseleave", hideTip);
  }

  // who finished the season with the player, and the manager's result that year
  function burnTip(b) {
    const team = ((DATA.rosters[b.owner] || {})[b.year] || {}).team || "";
    let end;
    if (b.gone) {
      end = `<div class="lh-ttline">Dropped, never re-rostered</div>`;
    } else {
      const ct = ((DATA.rosters[b.claimedBy] || {})[b.year] || {}).team || "";
      end = b.claimedBy
        ? `<div class="lh-ttline">Finished on <b>${b.claimedBy}</b>'s ${ct}</div>`
        : `<div class="lh-ttline">Claimed off waivers by a rival</div>`;
    }
    const res = b.champ ? '<b class="ch">✦ champion</b>' : (b.runner ? '<b class="ru">runner-up</b>' : (b.win ? "winning record" : "missed the cut"));
    return `<div class="lh-tth">${b.player}</div>` +
      `<div class="lh-ttteam">${b.year} · ${b.owner}'s ${team}</div>` +
      `<div class="lh-ttline">$${b.price} at auction${b.keeper ? " · keeper" : ""}</div>` +
      end +
      `<div class="lh-ttline">${b.owner} went ${b.rec} · ${res}</div>`;
  }

  /* --- 07 · Player Prices Over Time --------------------------------------- */
  let bbChips = [], bbCandIdx = {};
  function renderBigBoard() {
    const years = MONEY.years, y0 = years[0], yN = years[years.length - 1];
    const cand = Object.keys(MONEY.parc).map((pl) => {
      const d = MONEY.parc[pl], ys = Object.keys(d).map(Number), vals = ys.map((y) => d[y]);
      const first = d[Math.min(...ys)], last = d[Math.max(...ys)], peak = Math.max(...vals);
      return { player: pl, peak, n: ys.length, first, last, drama: (peak - first) + (peak - last), full: d[y0] != null && d[yN] != null };
    }).filter((c) => c.n >= 5);
    cand.sort((a, b) => b.peak - a.peak);
    bbCandIdx = {}; cand.forEach((c, i) => { bbCandIdx[c.player] = i; });   // stable order for color assignment
    bbChips = cand.slice(0, 16);
    bbMaxY = Math.ceil(Math.max(10, ...cand.map((c) => c.peak)) / 10) * 10;   // stable axis across all selections
    const full = cand.filter((c) => c.full);
    // default to the most dramatic arcs that also have a toggle chip on screen,
    // preferring full-decade players, then topping up to four by sheer drama
    const byDrama = bbChips.slice().sort((a, b) => b.drama - a.drama);
    const defaults = byDrama.filter((c) => c.full).slice(0, 4).map((c) => c.player);
    for (const c of byDrama) { if (defaults.length >= 4) break; if (!defaults.includes(c.player)) defaults.push(c.player); }
    mvSel = new Set(defaults);

    // market-movers ticker — biggest run-ups and biggest collapses (each player's own span; no repeats)
    const risers = cand.slice().sort((a, b) => (b.peak - b.first) - (a.peak - a.first)).slice(0, 2);
    const riserSet = new Set(risers.map((c) => c.player));
    const fallers = cand.filter((c) => !riserSet.has(c.player)).sort((a, b) => (b.peak - b.last) - (a.peak - a.last)).slice(0, 2);
    const mv = (c, dir) => `<button class="lh-mv ${dir}" data-p="${esc(c.player)}">${dir === "up" ? "▲" : "▼"} <b>${c.player.split(" ").slice(-1)[0]}</b> $${dir === "up" ? c.first : c.peak}→$${dir === "up" ? c.peak : c.last}</button>`;
    $("#lh-movers").innerHTML =
      `<span class="lh-mvlbl">Movers</span>` +
      risers.map((c) => mv(c, "up")).join("") + fallers.map((c) => mv(c, "down")).join("");

    $("#lh-chips").innerHTML = bbChips.map((c) =>
      `<button class="lh-chip" data-p="${esc(c.player)}"><span class="lh-chipdot"></span>${c.player}<i>$${c.peak}</i></button>`).join("");

    const toggle = (pl) => { if (mvSel.has(pl)) mvSel.delete(pl); else mvSel.add(pl); drawBoard(); };
    $("#lh-chips").querySelectorAll(".lh-chip").forEach((b) => { b.onclick = () => toggle(b.dataset.p); });
    $("#lh-movers").querySelectorAll(".lh-mv").forEach((b) => { b.onclick = () => toggle(b.dataset.p); });

    const board = $("#lh-board");
    board.addEventListener("mousemove", (e) => {
      const dot = e.target.closest(".bb-dot");
      if (!dot) { hideTip(); return; }
      const o = dot.dataset.o, y = dot.dataset.y;
      const team = ((DATA.rosters[o] || {})[y] || {}).team || "";
      tipAt(`<div class="lh-tth">${dot.dataset.p}</div>` +
        `<div class="lh-ttteam">${o}${team ? ` · ${team}` : ""}</div>` +
        `<div class="lh-ttline">’${String(y).slice(2)} auction · <b style="color:var(--lh-gold-hi)">$${dot.dataset.v}</b></div>`, e.clientX, e.clientY);
    });
    board.addEventListener("mouseleave", hideTip);
    drawBoard();
  }

  function drawBoard() {
    const sel = [...mvSel], years = MONEY.years, y0 = years[0], yN = years[years.length - 1];
    const W = 920, H = 360, padL = 52, padR = 78, padT = 16, padB = 34, plotW = W - padL - padR, plotH = H - padT - padB;
    const xFor = (y) => padL + (yN === y0 ? 0 : (y - y0) / (yN - y0)) * plotW;
    const maxY = bbMaxY;                              // fixed: toggling lines never rescales the chart
    const yFor = (v) => padT + (1 - v / maxY) * plotH;
    const step = maxY > 60 ? 20 : 10;

    // axes + gridlines are always drawn, so the chart keeps a stable footprint even with nothing selected
    let grid = "";
    for (let v = 0; v <= maxY; v += step) {
      const yy = yFor(v);
      grid += `<line class="bb-grid" x1="${padL}" y1="${yy.toFixed(1)}" x2="${W - padR}" y2="${yy.toFixed(1)}"/>` +
        `<text class="bb-yl" x="${padL - 8}" y="${(yy + 3.5).toFixed(1)}" text-anchor="end">$${v}</text>`;
    }
    years.forEach((y) => { grid += `<text class="bb-xl" x="${xFor(y).toFixed(1)}" y="${H - 12}" text-anchor="middle">’${String(y).slice(2)}</text>`; });

    // assign a distinct color to each charted line (stable order so colors don't churn on toggle)
    const order = sel.slice().sort((a, b) => (bbCandIdx[a] ?? 999) - (bbCandIdx[b] ?? 999));
    const colorOf = {}; order.forEach((pl, i) => { colorOf[pl] = LINECOLORS[i % LINECOLORS.length]; });

    let lines = "";
    order.forEach((pl) => {
      const d = MONEY.parc[pl] || {}, pts = years.filter((y) => d[y] != null);
      if (!pts.length) return;
      const col = colorOf[pl], own = (MONEY.parcOwner[pl] || {});
      const path = pts.map((y, i) => `${i ? "L" : "M"}${xFor(y).toFixed(1)} ${yFor(d[y]).toFixed(1)}`).join(" ");
      lines += `<path class="bb-line" style="stroke:${col}" d="${path}"/>`;
      pts.forEach((y) => { lines += `<circle class="bb-dot" style="fill:${col}" cx="${xFor(y).toFixed(1)}" cy="${yFor(d[y]).toFixed(1)}" r="4.2" data-p="${esc(pl)}" data-y="${y}" data-v="${d[y]}" data-o="${esc(own[y] || "")}"/>`; });
      const ly = pts[pts.length - 1];
      lines += `<text class="bb-end" style="fill:${col}" x="${(xFor(ly) + 8).toFixed(1)}" y="${(yFor(d[ly]) + 3.5).toFixed(1)}">${esc(pl.split(" ").slice(-1)[0])}</text>`;
    });

    const hint = sel.length ? "" : `<text class="bb-hint" x="${(padL + plotW / 2).toFixed(1)}" y="${(padT + plotH / 2).toFixed(1)}" text-anchor="middle">Tap a player below to chart their auction price</text>`;
    $("#lh-board").innerHTML = `<svg class="bb-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Auction price by year">${grid}${lines}${hint}</svg>`;
    $("#lh-chips").querySelectorAll(".lh-chip").forEach((c) => {
      const on = mvSel.has(c.dataset.p);
      c.classList.toggle("on", on);
      const dot = c.querySelector(".lh-chipdot");
      if (dot) dot.style.background = on ? colorOf[c.dataset.p] : "var(--lh-ink3)";
    });
  }

  /* --- 08 · Auction Retention vs. Win Rate -------------------------------- */
  function renderManagerMap() {
    const el = $("#lh-quad"); if (!el) return;
    const pts = MONEY.retention.slice();
    if (!pts.length) { el.innerHTML = ""; return; }
    const xs = pts.map((p) => p.retPct), ys = pts.map((p) => p.winPct);
    const xmin = Math.floor(Math.min(...xs) - 2), xmax = 100;
    const ymin = Math.floor(Math.min(...ys) - 4), ymax = Math.ceil(Math.max(...ys) + 4);
    const med = (a) => { const s = a.slice().sort((p, q) => p - q), m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
    const medX = med(xs), medY = med(ys);
    const X = (v) => (v - xmin) / (xmax - xmin) * 100, Y = (v) => (1 - (v - ymin) / (ymax - ymin)) * 100;
    const mxp = X(medX), myp = Y(medY), maxS = Math.max(...pts.map((p) => p.seasons));

    let inner =
      `<div class="lh-qzone maestro" style="left:${mxp}%;top:0;width:${100 - mxp}%;height:${myp}%"><span>Won via auction</span></div>` +
      `<div class="lh-qzone wizard" style="left:0;top:0;width:${mxp}%;height:${myp}%"><span>Won via waivers</span></div>` +
      `<div class="lh-qzone forget" style="left:${mxp}%;top:${myp}%;width:${100 - mxp}%;height:${100 - myp}%"><span>Kept players, lost</span></div>` +
      `<div class="lh-qzone adrift" style="left:0;top:${myp}%;width:${mxp}%;height:${100 - myp}%"><span>Lost both ways</span></div>` +
      `<div class="lh-qx" style="left:${mxp}%"><span>med ${Math.round(medX)}%</span></div>` +
      `<div class="lh-qy" style="top:${myp}%"><span>med ${Math.round(medY)}%</span></div>`;
    pts.forEach((p) => {
      const r = 9 + (p.seasons / maxS) * 9, c = OWNER_COLOR(p.owner);
      inner += `<div class="lh-qpt" style="left:${X(p.retPct)}%;top:${Y(p.winPct)}%" data-o="${esc(p.owner)}">` +
        `<span class="lh-qdot" style="width:${(r * 2).toFixed(0)}px;height:${(r * 2).toFixed(0)}px;background:${c};box-shadow:0 0 0 1.5px color-mix(in srgb,${c} 55%,transparent),0 0 16px -2px ${c}"></span>` +
        `<span class="lh-qname">${p.owner}</span></div>`;
    });

    el.innerHTML =
      `<div class="lh-qcorner tl">${Math.round(ymax)}%</div><div class="lh-qcorner bl">${Math.round(ymin)}%</div>` +
      `<div class="lh-plot">${inner}</div>` +
      `<div class="lh-qaxx">Auction-dollar retention &rarr; (${xmin}–100%)</div>` +
      `<div class="lh-qaxy">Win rate &rarr;</div>`;

    const plot = $(".lh-plot", el), byOwner = {}; pts.forEach((p) => byOwner[p.owner] = p);
    plot.addEventListener("mousemove", (e) => {
      const t = e.target.closest(".lh-qpt");
      plot.querySelectorAll(".lh-qpt.hot").forEach((n) => { if (n !== t) n.classList.remove("hot"); });
      if (!t) { hideTip(); return; }
      t.classList.add("hot");
      const p = byOwner[t.dataset.o];
      tipAt(`<div class="lh-tth">${p.owner}</div>` +
        `<div class="lh-ttrow"><b style="color:var(--lh-money-hi)">${Math.round(p.retPct)}%</b> of auction $ kept · <b style="color:var(--lh-gold-hi)">${Math.round(p.winPct)}%</b> win rate</div>` +
        `<div class="lh-ttrow">$${p.retained} of $${p.spend} survived · ${p.seasons} seasons</div>`, e.clientX, e.clientY);
    });
    plot.addEventListener("mouseleave", () => { hideTip(); plot.querySelectorAll(".lh-qpt.hot").forEach((n) => n.classList.remove("hot")); });
  }

  /* ---------------- interactions: grid tooltip + roster drawer ---------------- */
  function wireGrid(gridEl) {
    const tip = $("#lhTip");
    // trace one manager: light up only the row the cursor is genuinely over.
    // Hovering the gaps, the era strip or the year header marks no row, so nothing
    // is promoted on dead space. No dimming — just a spotlight on the active row.
    let activeRow = null;
    const trace = (row) => {
      if (row === activeRow) return;
      if (activeRow) activeRow.classList.remove("is-active");
      activeRow = row;
      if (activeRow) activeRow.classList.add("is-active");
    };
    gridEl.addEventListener("mousemove", (e) => {
      trace(e.target.closest(".lh-grow:not(.ghead)"));
      const cell = e.target.closest(".lh-cell.clk");
      if (!cell) { tip.classList.remove("on"); return; }
      const o = cell.dataset.o, y = +cell.dataset.y, d = (DATA.rosters[o] || {})[y];
      if (!d) { tip.classList.remove("on"); return; }
      const badge = d.champ ? '<b class="ch">✦ Champion</b>' : (d.runner ? '<b class="ru">Runner-up</b>' : "");
      tip.innerHTML =
        `<div class="lh-tth">${o} · ${y}</div><div class="lh-ttteam">${d.team}</div>` +
        `<div class="lh-ttrow">${d.rec} · ${ord(d.rsRank)} of ${DATA.grid.size[y]} in the regular season</div>` +
        (badge ? `<div class="lh-ttrow">${badge}</div>` : "") +
        `<div class="lh-ttcta">click for the full roster</div>`;
      tip.classList.add("on");
      const pad = 14, w = tip.offsetWidth, h = tip.offsetHeight;
      let x = e.clientX + pad, top = e.clientY + pad;
      if (x + w > innerWidth - 8) x = e.clientX - pad - w;
      if (top + h > innerHeight - 8) top = e.clientY - pad - h;
      tip.style.left = x + "px"; tip.style.top = top + "px";
    });
    gridEl.addEventListener("mouseleave", () => { tip.classList.remove("on"); trace(null); });
    gridEl.addEventListener("click", (e) => {
      const cell = e.target.closest(".lh-cell.clk");
      if (cell) { openRoster(cell.dataset.o, +cell.dataset.y); return; }
      const nm = e.target.closest(".lh-gname");
      if (nm && nm.dataset.o) {
        const yrs = Object.keys(DATA.rosters[nm.dataset.o] || {}).map(Number);
        if (yrs.length) openRoster(nm.dataset.o, Math.max(...yrs));
      }
    });
  }

  const POS_ORDER = { QB: 0, RB: 1, WR: 2, TE: 3, K: 5, "D/ST": 6 };
  let curO = null, curYears = [];

  function openRoster(o, y) {
    const d = (DATA.rosters[o] || {})[y]; if (!d) return;
    curO = o; curYears = Object.keys(DATA.rosters[o]).map(Number).sort((a, b) => a - b);
    const idx = curYears.indexOf(y);
    const prev = idx > 0 ? curYears[idx - 1] : null, next = idx < curYears.length - 1 ? curYears[idx + 1] : null;
    const fin = d.final ? `finished ${ord(d.final)}` : `${ord(d.rsRank)} in the regular season`;
    const badge = d.champ ? '<span class="lh-dbadge ch">✦ Champion</span>'
      : (d.runner ? '<span class="lh-dbadge ru">Runner-up</span>' : "");
    const era = d.draft ? `${(d.src || "").toUpperCase()} · ${d.draft} draft` : "";
    const bench = (p) => /bench|ir|taxi|reserve/i.test(p.slot || "");
    const sortP = (a, b) => (POS_ORDER[a.pos] ?? 4) - (POS_ORDER[b.pos] ?? 4) || a.n.localeCompare(b.n);
    const starters = d.roster.filter((p) => !bench(p)).sort(sortP);
    const benchers = d.roster.filter(bench).sort(sortP);
    const line = (p) =>
      `<div class="lh-rrow"><span class="lh-rpos ${posClass(p.pos)}">${p.pos || "—"}</span>` +
      `<span class="lh-rname">${p.n}</span><span class="lh-rnfl">${p.nfl || ""}</span></div>`;
    const grp = (label, arr) => arr.length ? `<div class="lh-rgrph">${label} · ${arr.length}</div>` + arr.map(line).join("") : "";
    $("#lhDrawerBody").innerHTML = grp("Starting lineup", starters) + grp("Bench & IR", benchers);
    $("#lhDrawerHead").innerHTML =
      `<div class="lh-dtop"><div class="lh-dyear">${y}</div>` +
      `<div class="lh-dnav"><button class="lh-dnavbtn" data-go="${prev ?? ""}" ${prev ? "" : "disabled"}>‹ ${prev || ""}</button>` +
      `<button class="lh-dnavbtn" data-go="${next ?? ""}" ${next ? "" : "disabled"}>${next || ""} ›</button></div></div>` +
      `<div class="lh-dteam">${d.team}</div>` +
      `<div class="lh-dsub"><span class="lh-dmgr">${o}</span> · ${d.rec} · ${fin} ${badge}</div>` +
      (era ? `<div class="lh-dera">${era}</div>` : "");
    $("#lhDrawer").querySelectorAll(".lh-dnavbtn").forEach((b) => { b.onclick = () => { if (b.dataset.go) openRoster(o, +b.dataset.go); }; });
    $("#lhDrawer").classList.add("open"); $("#lhScrim").classList.add("on"); $("#lhDrawer").setAttribute("aria-hidden", "false");
    $("#lhTip").classList.remove("on");
  }

  function closeRoster() {
    $("#lhDrawer").classList.remove("open"); $("#lhScrim").classList.remove("on"); $("#lhDrawer").setAttribute("aria-hidden", "true");
  }

  function wireDrawerOnce() {
    $("#lhDrawerX").onclick = closeRoster;
    $("#lhScrim").onclick = closeRoster;
    document.addEventListener("keydown", (e) => {
      if (!$("#lhDrawer").classList.contains("open")) return;
      if (e.key === "Escape") { closeRoster(); return; }
      const yr = +($(".lh-dyear") ? $(".lh-dyear").textContent : 0);
      const i = curYears.indexOf(yr);
      if (e.key === "ArrowLeft" && i > 0) openRoster(curO, curYears[i - 1]);
      if (e.key === "ArrowRight" && i >= 0 && i < curYears.length - 1) openRoster(curO, curYears[i + 1]);
    });
  }

  /* ---------------- entry ---------------- */
  function render() {
    if (built) return;
    const host = $("#view-history");
    host.innerHTML = '<div class="lh-error">Loading the archive…</div>';
    const grab = (url) => fetch(url).then((r) => r.json()).catch(() => null);
    Promise.all([grab(API), grab(AUCTION_API), grab(OWNERS_API)]).then(([hist, auction, owners]) => {
      const seasons = (hist && hist.seasons) || [];
      if (!seasons.length) { host.innerHTML = '<div class="lh-error">No league history is available yet.</div>'; built = true; return; }
      DATA = derive(seasons);
      MONEY = (auction && auction.seasons && Object.keys(auction.seasons).length) ? deriveMoney(seasons, auction.seasons) : null;
      OWNER_COLOR = buildOwnerColor(owners);
      scaffold(host);
      renderBanners(); renderGrid(); renderRegime(); renderLoyalty(); renderLedger(); renderRoyalty();
      if (MONEY) { renderSunkCosts(); renderBigBoard(); renderManagerMap(); }
      wireDrawerOnce();
      built = true;
    }).catch(() => { host.innerHTML = '<div class="lh-error">Couldn’t load the league history.</div>'; });
  }

  window.LeagueHistory = { render };
})();
