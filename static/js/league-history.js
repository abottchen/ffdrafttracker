/* ==========================================================================
   League History — "The Rafters"  (viewer tab)
   Fetches the raw season archive from GET /api/v1/league-history and derives
   every leaderboard + the finish grid client-side, then renders into
   #view-history. Self-contained: exposes window.LeagueHistory.render().
   ========================================================================== */
(function () {
  "use strict";
  const API = "/api/v1/league-history";
  const $ = (s, el) => (el || document).querySelector(s);
  const ce = (t, c) => { const e = document.createElement(t); if (c) e.className = c; return e; };
  const ord = (n) => n + (n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th"));
  const posClass = (p) => (p || "").replace("/", "") || "NA";
  const skipPlayer = (n) => /D\/ST| - DEF/.test(n);

  let DATA = null, built = false;

  /* ---------------- derive everything from raw seasons ---------------- */
  function derive(seasonsIn) {
    const seasons = seasonsIn.slice().sort((a, b) => a.year - b.year);
    const years = seasons.map((s) => s.year);
    const latest = years[years.length - 1];
    const active = new Set(seasons.find((s) => s.year === latest).standings.map((t) => t.owner));
    const appear = {};
    seasons.forEach((s) => s.standings.forEach((t) => { appear[t.owner] = (appear[t.owner] || 0) + 1; }));
    const ironmen = Object.values(appear).filter((c) => c === seasons.length).length;

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
      const champO = s.champion.owner, runO = s.runner_up.owner;
      const order = s.standings.slice().sort((a, b) => winpct(b) - winpct(a) || (b.points_for || 0) - (a.points_for || 0));
      order.forEach((t, i) => {
        const rank = i + 1;
        const rec = `${t.wins}-${t.losses}` + (t.ties ? `-${t.ties}` : "");
        const isC = t.owner === champO, isR = t.owner === runO;
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
      .sort((a, b) => b.titles - a.titles || b.seasons - a.seasons || avg(a.owner) - avg(b.owner) || a.owner.localeCompare(b.owner));

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

    // drought BETWEEN titles — active managers who have won at least once
    const drought = [...active].filter((o) => lastTitle[o])
      .map((o) => ({ owner: o, since: latest - lastTitle[o] }))
      .sort((a, b) => b.since - a.since);

    // league royalty: most-rostered NFL players ever
    const pop = {};
    seasons.forEach((s) => s.standings.forEach((t) => {
      const seen = new Set();
      (t.roster || []).forEach((e) => { const p = e.player_name; if (skipPlayer(p) || seen.has(p)) return; seen.add(p); pop[p] = (pop[p] || 0) + 1; });
    }));
    const royalty = Object.entries(pop).map(([player, n]) => ({ player, seasons: n })).sort((a, b) => b.seasons - a.seasons).slice(0, 12);

    return {
      meta: { years, nSeasons: seasons.length, nManagers: Object.keys(appear).length, ironmen, latest, active },
      champions, regime, grid: { years, size, rows: gridRows }, loyalty, drought, royalty, rosters,
    };
  }

  /* ---------------- scaffold ---------------- */
  function scaffold(host) {
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
            <div class="lh-sec-head"><span class="lh-num">04</span><h2>Time Since a Title</h2></div>
            <p class="lh-sub">Every champion eventually waits again — years since each manager who's <b>won at least once</b> last hoisted the trophy.</p>
            <div id="lh-drought"></div>
            <p class="lh-foot">Only past champions appear here — <b>win one and the clock starts.</b> Managers still chasing their first aren't on the board.</p>
          </section>
          <section class="lh-sec lh-roy" style="margin-top:0">
            <div class="lh-sec-head"><span class="lh-num">05</span><h2>League Royalty</h2></div>
            <p class="lh-sub">The NFL names that defined the era — most seasons rostered by <i>anyone</i> in the league.</p>
            <div id="lh-royalty"></div>
          </section>
        </div>
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
      `<b>${DATA.meta.nSeasons}</b> seasons · <b>${DATA.meta.nManagers}</b> managers · <b>${DATA.meta.ironmen}</b> iron men`;
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

  function renderDrought() {
    const dr = $("#lh-drought"); dr.innerHTML = "";
    const maxD = Math.max(...DATA.drought.map((d) => d.since), 1);
    DATA.drought.forEach((d, i) => {
      const defending = d.since === 0;
      const row = ce("div", "lh-row");
      row.innerHTML =
        `<div class="lh-nm">${d.owner}</div>` +
        `<div class="lh-track"><span class="lh-fill ${defending ? "gold" : "pew"}"></span></div>` +
        `<div style="display:flex;gap:9px;align-items:center"><span class="lh-val">${defending ? "★" : d.since}` +
        `<span style="font-size:10px;color:var(--lh-ink3)"> ${defending ? "now" : "yr"}</span></span>` +
        (defending ? '<span class="lh-tag def">Defending</span>' : "") + `</div>`;
      dr.appendChild(row);
      setTimeout(() => { $(".lh-fill", row).style.width = Math.max(4, d.since / maxD * 100) + "%"; }, 250 + i * 60);
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

  /* ---------------- interactions: grid tooltip + roster drawer ---------------- */
  function wireGrid(gridEl) {
    const tip = $("#lhTip");
    gridEl.addEventListener("mousemove", (e) => {
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
    gridEl.addEventListener("mouseleave", () => tip.classList.remove("on"));
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
    fetch(API).then((r) => r.json()).then((hist) => {
      const seasons = (hist && hist.seasons) || [];
      if (!seasons.length) { host.innerHTML = '<div class="lh-error">No league history is available yet.</div>'; built = true; return; }
      DATA = derive(seasons);
      scaffold(host);
      renderBanners(); renderGrid(); renderRegime(); renderLoyalty(); renderDrought(); renderRoyalty();
      wireDrawerOnce();
      built = true;
    }).catch(() => { host.innerHTML = '<div class="lh-error">Couldn’t load the league history.</div>'; });
  }

  window.LeagueHistory = { render };
})();
