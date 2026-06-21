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
  const POSVAR = { QB: "--qb", RB: "--rb", WR: "--wr", TE: "--te", K: "--k", "D/ST": "--dst" };
  const posVar = (p) => POSVAR[p] || "--lh-silver";

  let DATA = null, MONEY = null, OWNER_COLOR = () => "var(--lh-silver)", built = false;
  let mvSel = new Set();   // currently-charted players on The Big Board

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

    const titles = {}, lastTitle = {};
    seasons.forEach((s) => {
      const winners = [s.champion.owner];
      if (s.shared_title) winners.push(s.runner_up.owner);
      winners.forEach((o) => { titles[o] = (titles[o] || 0) + 1; lastTitle[o] = Math.max(lastTitle[o] || 0, s.year); });
    });
    const champions = Object.keys(titles)
      .map((o) => ({ owner: o, titles: titles[o], last: lastTitle[o], active: active.has(o) }))
      .sort((a, b) => b.titles - a.titles || b.last - a.last || a.owner.localeCompare(b.owner));

    const best = {};
    seasons.forEach((s) => { best[s.best_record.owner] = (best[s.best_record.owner] || 0) + 1; });
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
    const po = {}, posmap = {};
    seasons.forEach((s) => s.standings.forEach((t) => {
      const seen = new Set();
      (t.roster || []).forEach((e) => {
        const p = e.player_name;
        if (seen.has(p) || skipPlayer(p)) return;
        seen.add(p);
        po[p] = po[p] || {}; po[p][t.owner] = (po[p][t.owner] || 0) + 1; posmap[p] = e.position || "";
      });
    }));
    const pairs = [];
    Object.keys(po).forEach((p) => {
      let bo = null, bc = 0;
      Object.entries(po[p]).forEach(([o, c]) => { if (c > bc) { bc = c; bo = o; } });
      if (bc >= 5) pairs.push({ player: p, owner: bo, seasons: bc, pos: posmap[p] || "" });
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

    // league royalty: most-rostered NFL players ever
    const pop = {};
    seasons.forEach((s) => s.standings.forEach((t) => {
      const seen = new Set();
      (t.roster || []).forEach((e) => { const p = e.player_name; if (skipPlayer(p) || seen.has(p)) return; seen.add(p); pop[p] = (pop[p] || 0) + 1; });
    }));
    const royalty = Object.entries(pop).map(([player, n]) => ({ player, seasons: n })).sort((a, b) => b.seasons - a.seasons).slice(0, 12);

    return {
      meta: { years, nSeasons: seasons.length, nManagers: Object.keys(appear).length, latest, active },
      champions, regime, grid: { years, size, rows: gridRows }, loyalty, ledger, royalty, rosters,
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
    const posOf = {}, rosterSet = {}, meta = {}, leagueByYear = {};
    seasons.forEach((s) => {
      const champO = s.champion && s.champion.owner, runO = s.runner_up && s.runner_up.owner, shared = !!s.shared_title;
      const lset = leagueByYear[s.year] = new Set();
      s.standings.forEach((t) => {
        const set = new Set();
        (t.roster || []).forEach((e) => { const nn = normName(e.player_name); set.add(nn); lset.add(nn); if (e.position) posOf[nn] = e.position; });
        rosterSet[`${s.year}|${t.owner}`] = set;
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
    const burns = [], parc = {}, ret = {};
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
          (parc[p.player] = parc[p.player] || {})[y] = Math.max(parc[p.player][y] || 0, p.price);
          r.spend += p.price;
          if (set && set.has(nn)) { r.retained += p.price; return; }
          if (!set) return;                                   // no roster to judge against
          const inLeague = (leagueByYear[y] || new Set()).has(nn);
          burns.push({
            year: y, owner, player: p.player, price: p.price, keeper: !!p.keeper,
            gone: !inLeague, traded: inLeague,
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

    return { years, burns, parc, posOf, retention };
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
          <p class="lh-sub">Twenty-three years of finishes, one square each. <b>Gold is a title, bright is a top year, dark is a lean one</b> — a dynasty reads as a bright row, a slump as a dark stretch. Hover a name to follow one manager; the squares show regular-season finish and gold marks who actually won it. Click any square for that team's full roster.</p>
          <div class="lh-gridcard">
            <div class="lh-grid" id="lh-grid"></div>
            <div class="lh-legend" id="lh-legend"></div>
          </div>
        </section>

        <section class="lh-sec">
          <div class="lh-sec-head"><span class="lh-num">02</span><h2>Régime vs. Crown</h2></div>
          <p class="lh-sub">Best regular-season record is a régime; a championship is a crown. They don't always go to the same house — the gap between the two columns is the gap between dominant and decisive.</p>
          <div class="lh-talehead"><div class="l">Best records · régime</div><div class="c">Manager</div><div class="r">Titles · crown</div></div>
          <div class="lh-tale" id="lh-tale"></div>
        </section>

        <section class="lh-sec">
          <div class="lh-sec-head"><span class="lh-num">03</span><h2>Their Guy</h2></div>
          <p class="lh-sub">Some attachments outlast coaching staffs. These are the players each manager kept coming back for — drafted or stashed, season after season.</p>
          <div class="lh-loyal" id="lh-loyal"></div>
        </section>

        <div class="lh-cols">
          <section class="lh-sec" style="margin-top:0">
            <div class="lh-sec-head"><span class="lh-num">04</span><h2>The Ledger</h2></div>
            <p class="lh-sub">Every manager's career regular-season record — <b>gold is wins, the rest is losses</b>, best rate on top. Three seasons or more.</p>
            <div id="lh-ledger"></div>
            <p class="lh-foot">Regular-season games only — playoffs aren't counted. <b>Ties score as half a win.</b></p>
          </section>
          <section class="lh-sec lh-roy" style="margin-top:0">
            <div class="lh-sec-head"><span class="lh-num">05</span><h2>League Royalty</h2></div>
            <p class="lh-sub">The NFL names that defined the era — most seasons rostered by <i>anyone</i> in the league.</p>
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
      const row = ce("div", "lh-tr" + (king ? " king" : ""));
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
  }

  function renderLoyalty() {
    const loyal = $("#lh-loyal"); loyal.innerHTML = "";
    DATA.loyalty.forEach((l, i) => {
      const p = ce("div", "lh-plq" + (l.seasons >= 9 ? " top" : ""));
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
  }

  function renderLedger() {
    const el = $("#lh-ledger"); el.innerHTML = "";
    DATA.ledger.forEach((m, i) => {
      const row = ce("div", "lh-row lh-led" + (m.active ? "" : " gone") + (i === 0 ? " top" : ""));
      const rec = `${m.w}–${m.l}` + (m.t ? `–${m.t}` : "");
      const pct = m.pct.toFixed(3).replace(/^0/, ""); // ".597"
      row.innerHTML =
        `<div class="lh-nm">${m.owner}</div>` +
        `<div class="lh-led-track"><span class="lh-led-fill"></span></div>` +
        `<div class="lh-led-val"><span class="lh-led-pct">${pct}</span><span class="lh-led-rec">${rec}</span></div>`;
      el.appendChild(row);
      setTimeout(() => { $(".lh-led-fill", row).style.width = (m.pct * 100) + "%"; }, 250 + i * 55);
    });
  }

  function renderRoyalty() {
    const ro = $("#lh-royalty"); ro.innerHTML = "";
    const maxR = DATA.royalty[0].seasons;
    DATA.royalty.forEach((p, i) => {
      const row = ce("div", "lh-row");
      row.innerHTML =
        `<div class="lh-nm">${p.player}</div>` +
        `<div class="lh-track"><span class="lh-fill ${i === 0 ? "gold" : "pew"}"></span></div>` +
        `<div class="lh-val">${p.seasons}</div>`;
      ro.appendChild(row);
      setTimeout(() => { $(".lh-fill", row).style.width = (p.seasons / maxR * 100) + "%"; }, 250 + i * 55);
    });
  }

  /* ================= Part II · The Money ================= */
  function moneyScaffold() {
    const yrs = MONEY.years, span = yrs.length ? `${yrs[0]}–${yrs[yrs.length - 1]}` : "";
    return (
      `<div class="lh-act">
         <span class="lh-actrule"></span>
         <span class="lh-acttext">Part II &middot; The Money</span>
         <span class="lh-actrule"></span>
       </div>
       <p class="lh-actsub">Auction salaries, ${span} &mdash; what the room paid, what survived the season, and who turned it into wins.</p>

       <section class="lh-sec">
         <div class="lh-sec-head"><span class="lh-num">06</span><h2>Sunk Costs</h2></div>
         <p class="lh-sub">Big money at the block, gone by the final whistle &mdash; auction buys that weren't on the roster at season's end. <b>Charred bars left the league entirely; amber ones were traded away.</b> The glowing tags are the managers who <b>won anyway.</b></p>
         <div class="lh-sunkcard"><div id="lh-sunk"></div></div>
         <p class="lh-foot">Keepers count as committed dollars. A burn is any auction buy missing from that manager's end-of-season roster.</p>
       </section>

       <section class="lh-sec">
         <div class="lh-sec-head"><span class="lh-num">07</span><h2>The Big Board</h2></div>
         <p class="lh-sub">Nine auctions, one ticker. What the room was willing to pay for the names that moved the market &mdash; <b>lines are colored by position.</b> Tap a player to chart or drop their price line.</p>
         <div class="lh-boardcard">
           <div class="lh-movers" id="lh-movers"></div>
           <div class="lh-board" id="lh-board"></div>
           <div class="lh-chips" id="lh-chips"></div>
         </div>
       </section>

       <section class="lh-sec">
         <div class="lh-sec-head"><span class="lh-num">08</span><h2>Maestro &amp; Wizard</h2></div>
         <p class="lh-sub">Two ways to win: <b>master the auction</b> (keep the players you paid for) or <b>master the waiver wire</b> (win with the ones you didn't). Career auction-dollar retention against regular-season win rate. <b>Bigger tokens mean more seasons played.</b></p>
         <div class="lh-quad" id="lh-quad"></div>
       </section>`
    );
  }

  /* --- 06 · Sunk Costs ----------------------------------------------------- */
  function renderSunkCosts() {
    const el = $("#lh-sunk"); if (!el) return;
    el.innerHTML = "";
    const shown = MONEY.burns.slice(0, 14);
    const maxP = Math.max(1, ...MONEY.burns.map((b) => b.price));
    shown.forEach((b, i) => {
      const tag = b.champ ? `<span class="lh-btag champ">★ Champion</span>`
        : b.runner ? `<span class="lh-btag won">Runner-up</span>`
          : b.win ? `<span class="lh-btag won">Won anyway</span>` : "";
      const row = ce("div", "lh-burn" + (b.gone ? " gone" : " traded") + (b.win ? " winrec" : ""));
      row.innerHTML =
        `<div class="lh-bowner">${b.owner}</div>` +
        `<div class="lh-bmid">` +
          `<div class="lh-bplayer">${b.player}${b.keeper ? `<span class="lh-bkeep">keeper</span>` : ""}` +
            `<span class="lh-bstat ${b.gone ? "gone" : "traded"}">${b.gone ? "Gone" : "Traded"}</span></div>` +
          `<div class="lh-btrack"><span class="lh-bfill"></span></div>` +
        `</div>` +
        `<div class="lh-bend"><div class="lh-bprice">$${b.price}</div>` +
          `<div class="lh-brec">${b.rec}${tag}</div></div>`;
      el.appendChild(row);
      setTimeout(() => { $(".lh-bfill", row).style.width = (b.price / maxP * 100) + "%"; }, 220 + i * 55);
    });
  }

  /* --- 07 · The Big Board -------------------------------------------------- */
  let bbChips = [];
  function renderBigBoard() {
    const years = MONEY.years, y0 = years[0], yN = years[years.length - 1];
    const cand = Object.keys(MONEY.parc).map((pl) => {
      const d = MONEY.parc[pl], ys = Object.keys(d).map(Number), vals = ys.map((y) => d[y]);
      const first = d[Math.min(...ys)], last = d[Math.max(...ys)], peak = Math.max(...vals);
      return { player: pl, peak, n: ys.length, first, last, drama: (peak - first) + (peak - last), full: d[y0] != null && d[yN] != null };
    }).filter((c) => c.n >= 5);
    cand.sort((a, b) => b.peak - a.peak);
    bbChips = cand.slice(0, 16);
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
      `<button class="lh-chip" data-p="${esc(c.player)}"><span class="lh-chipdot" style="background:var(${posVar(MONEY.posOf[normName(c.player)] || "")})"></span>${c.player}<i>$${c.peak}</i></button>`).join("");

    const toggle = (pl) => { if (mvSel.has(pl)) mvSel.delete(pl); else mvSel.add(pl); drawBoard(); };
    $("#lh-chips").querySelectorAll(".lh-chip").forEach((b) => { b.onclick = () => toggle(b.dataset.p); });
    $("#lh-movers").querySelectorAll(".lh-mv").forEach((b) => { b.onclick = () => toggle(b.dataset.p); });

    const board = $("#lh-board");
    board.addEventListener("mousemove", (e) => {
      const dot = e.target.closest(".bb-dot");
      if (!dot) { hideTip(); return; }
      tipAt(`<div class="lh-tth">${dot.dataset.p}</div><div class="lh-ttrow">’${String(dot.dataset.y).slice(2)} auction · <b style="color:var(--lh-gold-hi)">$${dot.dataset.v}</b></div>`, e.clientX, e.clientY);
    });
    board.addEventListener("mouseleave", hideTip);
    drawBoard();
  }

  function drawBoard() {
    const sel = [...mvSel], years = MONEY.years, y0 = years[0], yN = years[years.length - 1];
    const W = 920, H = 360, padL = 52, padR = 78, padT = 16, padB = 34, plotW = W - padL - padR, plotH = H - padT - padB;
    const xFor = (y) => padL + (yN === y0 ? 0 : (y - y0) / (yN - y0)) * plotW;
    let maxY = Math.max(10, ...sel.flatMap((pl) => Object.values(MONEY.parc[pl] || {})));
    maxY = Math.ceil(maxY / 10) * 10;
    const yFor = (v) => padT + (1 - v / maxY) * plotH;

    let grid = "";
    for (let v = 0; v <= maxY; v += 10) {
      const yy = yFor(v);
      grid += `<line class="bb-grid" x1="${padL}" y1="${yy}" x2="${W - padR}" y2="${yy}"/>` +
        `<text class="bb-yl" x="${padL - 8}" y="${yy + 3.5}" text-anchor="end">$${v}</text>`;
    }
    years.forEach((y) => { grid += `<text class="bb-xl" x="${xFor(y)}" y="${H - 12}" text-anchor="middle">’${String(y).slice(2)}</text>`; });

    let lines = "";
    sel.forEach((pl) => {
      const d = MONEY.parc[pl] || {}, pts = years.filter((y) => d[y] != null);
      if (!pts.length) return;
      const cv = posVar(MONEY.posOf[normName(pl)] || "");
      const path = pts.map((y, i) => `${i ? "L" : "M"}${xFor(y).toFixed(1)} ${yFor(d[y]).toFixed(1)}`).join(" ");
      lines += `<path class="bb-line" style="stroke:var(${cv})" d="${path}"/>`;
      pts.forEach((y) => { lines += `<circle class="bb-dot" style="fill:var(${cv})" cx="${xFor(y).toFixed(1)}" cy="${yFor(d[y]).toFixed(1)}" r="3.6" data-p="${esc(pl)}" data-y="${y}" data-v="${d[y]}"/>`; });
      const ly = pts[pts.length - 1];
      lines += `<text class="bb-end" style="fill:var(${cv})" x="${(xFor(ly) + 8).toFixed(1)}" y="${(yFor(d[ly]) + 3.5).toFixed(1)}">${esc(pl.split(" ").slice(-1)[0])}</text>`;
    });

    $("#lh-board").innerHTML = sel.length
      ? `<svg class="bb-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Auction price by year">${grid}${lines}</svg>`
      : `<div class="lh-boardempty">Tap a player below to chart their auction price.</div>`;
    $("#lh-chips").querySelectorAll(".lh-chip").forEach((c) => c.classList.toggle("on", mvSel.has(c.dataset.p)));
  }

  /* --- 08 · Maestro & Wizard ---------------------------------------------- */
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
      `<div class="lh-qzone maestro" style="left:${mxp}%;top:0;width:${100 - mxp}%;height:${myp}%"><span>The Maestro</span></div>` +
      `<div class="lh-qzone wizard" style="left:0;top:0;width:${mxp}%;height:${myp}%"><span>The Wizard</span></div>` +
      `<div class="lh-qzone forget" style="left:${mxp}%;top:${myp}%;width:${100 - mxp}%;height:${100 - myp}%"><span>Set &amp; Forget</span></div>` +
      `<div class="lh-qzone adrift" style="left:0;top:${myp}%;width:${mxp}%;height:${100 - myp}%"><span>Adrift</span></div>` +
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
