/* team-viewer.js — page-specific JS for the read-only viewer (team_viewer.html).

   Loaded as a classic script after draft-shared.js, so shared globals
   (esc, getTeamLogoUrl, NFL_COLORS/teamColor, headshotUrl, budgetClass,
   BOOTH_PERSONAS/BOOTH_LINEUP/boothPersona, revealOnReady) are already in
   scope. Functions stay top-level globals for the template's inline
   onclick/onmouseenter/etc. handlers.

   Server-injected data (config, selected team id) arrives on window.APP,
   set inline in team_viewer.html before this file loads — a static .js can't
   use Jinja2 {{ }} interpolation. */
        const API_BASE = '/api/v1';
        // Server-injected (change F): config is authoritative; no hardcoded fallback.
        const config = window.APP.config;
        const TOTAL = config.total_rounds;
        const INITIAL = config.initial_budget;
        const POSMAX = config.position_maximums;            // {QB,RB,WR,TE,K,"D/ST"}
        const DRAFT_YEAR = config.draft_year || 2025;
        const STATS_YR = "'" + String(DRAFT_YEAR - 1).slice(-2);   // prior-season stats column header
        const RADAR_ORDER = ['QB','RB','WR','TE','K','D/ST'];
        const POSORDER = {QB:0,RB:1,WR:2,TE:3,K:4,'D/ST':5};
        const POSCOLOR = {QB:'#A877DE',RB:'#46B86C',WR:'#5790CF',TE:'#E08A45',K:'#E6B23E','D/ST':'#D6564A'};
        const LIGHTPOS = {QB:1,WR:1,'D/ST':1};
        const STATMAX = {YDS:5000,TD:30,INT:20,RUSH:2100,REC:130,FG:40,XP:60,PTS:170,SACK:60};

        let owners = [], ownersById = {}, playersById = {}, playerStats = {};
        let TEAMS = [];                 // normalized model (mockup shape)
        let lastDraftState = null;
        let selected = 0;               // index into TEAMS
        let initialized = false;        // one-time setup guard (F1)
        let curRoster = [], prevFrac = [0,0,0,0,0,0];
        let lastSeenMaxPickId = 0;      // for ledger new-pick flash
        let __recentSince = 0;          // watermark snapshot each poll for the ledger "new pick" flash
        const INITIAL_TEAM_ID = window.APP.selectedTeamId;
        let AVAILABLE = [];
        let rosterMode = 'cards';       // Teams view roster style: cards | bye | list
        let MARKET = {};                // per-position price stats (median/sd/min/max/total)
        let DUMPS = new Set();          // pick_ids that are end-of-draft budget dumps
        let matrixMode = 'count';       // Roster Matrix cell metric: count | dollars
        let marketView = null;          // Position Market visible $ window {min,max}; null = full range
        let marketGeo = null, marketWired = false, marketDragging = false, marketRAF = 0;
        let ledgerSort = 'order', ledgerDir = -1, ledgerQuery = '';   // ledger sort key + direction (-1 desc)
        let availPos = 'ALL', availSort = 'pos', availDir = 1;         // available-board filter + sort

        // esc(), getTeamLogoUrl(), NFL_COLORS/teamColor(), headshotUrl(), budgetClass(),
        // BOOTH_PERSONAS/BOOTH_LINEUP/boothPersona(), revealOnReady() all come from
        // /static/js/draft-shared.js (loaded above) — shared with the admin console.

        function hexA(hex, a){ const n = parseInt(hex.slice(1),16); return `rgba(${(n>>16)&255},${(n>>8)&255},${n&255},${a})`; }
        function median(a){ const s=[...a].sort((x,y)=>x-y), m=s.length>>1; return s.length? (s.length%2? s[m] : (s[m-1]+s[m])/2) : 0; }
        function ab2(n){ return (n||'').slice(0,2).toUpperCase(); }
        // D/ST headshot falls back to the team logo (no player headshot for defenses).
        // ESPN CDN images: hide on error so a CDN hiccup doesn't litter broken-image icons.
        const shotImg = (p, cls) => p.pos === 'D/ST'
            ? `<img class="${cls} logo" src="${getTeamLogoUrl(p.nfl)}" alt="" onerror="this.style.display='none'">`
            : `<img class="${cls}" src="${headshotUrl(p.id)}" alt="" onerror="this.style.display='none'">`;
        function defenseBye(teamAbbr){
            for (const id in playerStats){ const s = playerStats[id]; if (s && s.team === teamAbbr && s.bye_week) return s.bye_week; }
            return null;
        }

        async function loadStatic() {
            owners = await (await fetch(`${API_BASE}/owners`)).json();
            ownersById = Object.fromEntries(owners.map(o => [o.id, o]));
            const players = await (await fetch(`${API_BASE}/players`)).json();
            playersById = Object.fromEntries(players.map(p => [p.id, p]));
            try {
                const r = await fetch(`${API_BASE}/player/stats`);
                if (r.ok) playerStats = await r.json();
            } catch (e) { playerStats = {}; }
        }
        async function loadAvailable() {
            try {
                const list = await (await fetch(`${API_BASE}/players/available`)).json();
                AVAILABLE = list.map(p => ({ id: p.id, fn: p.first_name, ln: p.last_name, pos: p.position, nfl: p.team }));
            } catch (e) { AVAILABLE = []; }
        }

        // Normalize the live draft state into the array shape the mockup renderers expect.
        // Each entry: {ord, owner_id, team, owner, budget, picks (count), color, status, max_bid, _picks}
        function buildModel(ds) {
            const sorted = [...ds.teams].sort((a, b) => a.owner_id - b.owner_id);
            TEAMS = sorted.map((t, i) => {
                const o = ownersById[t.owner_id] || {};
                let status = '';
                if (t.manually_done || t.picks.length >= TOTAL) status = 'done';
                else if (t.owner_id === ds.next_to_nominate) status = 'clock';
                return {
                    ord: i + 1, owner_id: t.owner_id,
                    team: o.team_name || 'Unknown', owner: o.owner_name || '',
                    budget: t.budget_remaining, picks: t.picks.length,
                    color: o.color || '#E0A24A',
                    max_bid: t.max_bid, status, _picks: t.picks
                };
            });
        }
        // Indices for "On the Clock" / "Up Next", driven by the server (not re-derived).
        function clockInfo() {
            const clockIdx = lastDraftState ? TEAMS.findIndex(t => t.owner_id === lastDraftState.next_to_nominate) : -1;
            const nextIdx = (lastDraftState && lastDraftState.up_next)
                ? TEAMS.findIndex(t => t.owner_id === lastDraftState.up_next) : -1;
            return { clockIdx, nextIdx };
        }
        const isDone = t => t.status === 'done';
        const maxBid = t => t.max_bid;   // server-authoritative (— when null)

        function showError(msg){ const e = document.getElementById('vError'); e.textContent = msg; e.style.display = 'block'; }
        function hideError(){ document.getElementById('vError').style.display = 'none'; }

        async function pollState() {
            // Retry loadStatic until owners/players are loaded (F1 recovery).
            if (!owners.length) {
                try { await loadStatic(); } catch (e) { /* will retry next poll */ }
            }
            try {
                const ds = await (await fetch(`${API_BASE}/draft-state`)).json();
                hideError();
                lastDraftState = ds;
                buildModel(ds);
                // One-time setup deferred from init (F1): runs once after first
                // successful load even if the original init() threw.
                if (!initialized && owners.length) {
                    const idx = TEAMS.findIndex(t => t.owner_id === INITIAL_TEAM_ID);
                    selected = idx >= 0 ? idx : 0;
                    lastSeenMaxPickId = maxPickId(ds);
                    __recentSince = lastSeenMaxPickId;
                    setupTargetBoard();
                    setupStatusControls();
                    setupBooth();
                    initialized = true;
                }
                // Keep the selected team stable across polls (match by owner_id).
                if (TEAMS.length) {
                    if (selected >= TEAMS.length) selected = 0;
                }
                // Advance the watermark every poll regardless of which view is active,
                // so picks that land while on the Teams view don't all animate rp-new
                // when the user switches to Draft Status.
                __recentSince = lastSeenMaxPickId;
                lastSeenMaxPickId = Math.max(lastSeenMaxPickId, maxPickId(ds));
                computeMarket();                        // per-position price stats for tips/analysis
                renderChrome();                         // strip + clocknote + completion (Task 3)
                const v = activeViewId();
                if (v === 'view-status') renderStatusView();
                else if (v === 'view-analysis') renderAnalysisView();
                else renderTeamsView();
            } catch (e) {
                showError('Connection lost — retrying…');
            }
            try { await loadAvailable(); } catch (e) {}
            boothPollLive();   // commentary feed (independent of draft-state)
        }

        async function init() {
            // Register the poll unconditionally so recovery works even if
            // the initial bootstrap below throws (F1).
            setInterval(pollState, 5000);
            try {
                await loadStatic();
                await loadAvailable();
                const ds = await (await fetch(`${API_BASE}/draft-state`)).json();
                lastDraftState = ds; buildModel(ds);
                const idx = TEAMS.findIndex(t => t.owner_id === INITIAL_TEAM_ID);
                selected = idx >= 0 ? idx : 0;
                lastSeenMaxPickId = maxPickId(ds);
                __recentSince = lastSeenMaxPickId;
                computeMarket();
                renderChrome(); renderTeamsView();
                setupTargetBoard();
                setupStatusControls();
                setupBooth();
                boothPollLive();
                initialized = true;
            } catch (e) {
                showError('Server unavailable — will keep retrying…');
            }
        }
        function maxPickId(ds){ let m = 0; ds.teams.forEach(t => t.picks.forEach(p => { if (p.pick_id > m) m = p.pick_id; })); return m; }

        // FOUT guard
        revealOnReady(document.getElementById('app'));

        function renderChips(){
          const {clockIdx,nextIdx}=clockInfo();
          document.getElementById('chips').innerHTML=TEAMS.map((t,i)=>{
            const done=isDone(t);
            // Status is a small informative pip, never a reason to subdue the chip —
            // every team stays a full-strength, clickable selector card.
            const badge=i===clockIdx?'<span class="chip-badge clock">On Clock</span>'
              :i===nextIdx?'<span class="chip-badge next">Next</span>'
              :done?'<span class="chip-badge done">✓ Full</span>':'';
            const cls=`chip ${i===selected?'active':''} ${i===clockIdx?'is-clock':''}`;
            return `<button type="button" class="${cls}" style="--tc:${t.color}" onclick="selectTeam(${i})" title="View ${esc(t.team)}">
              <div class="ct">${esc(t.team)}</div>
              <div class="chip-foot"><span class="co">${esc(t.owner)}</span>${badge}</div></button>`;
          }).join('');
        }
        function renderClockNote(){
          const {clockIdx,nextIdx}=clockInfo();
          const c=clockIdx>=0?TEAMS[clockIdx]:null, n=nextIdx>=0?TEAMS[nextIdx]:null;
          document.getElementById('clocknote').innerHTML=
            (c?`<span class="cn-clock"><span class="cn-dot"></span>On the Clock <b>${esc(c.team)}</b></span>`:'')+
            (n?`<span class="cn-next">Up Next <b>${esc(n.team)}</b></span>`:'');
        }
        function renderChrome() {
            renderChips();
            renderClockNote();
            const drafted = TEAMS.reduce((n, t) => n + t.picks, 0);
            const pct = TEAMS.length ? Math.round(drafted / (TOTAL * TEAMS.length) * 100) : 0;
            document.getElementById('completion-fill').style.width = pct + '%';
            document.getElementById('completion-pct').textContent = pct + '%';
        }
        function selectTeam(i) {
            selected = i;
            const t = TEAMS[i];
            if (t) {
                const url = new URL(window.location);
                url.searchParams.set('team_id', t.owner_id);
                window.history.replaceState({}, '', url);
            }
            renderChips();
            renderTeamsView();
        }
        function navTeam(d) {
            if (!TEAMS.length) return;
            selected = (selected + d + TEAMS.length) % TEAMS.length;
            selectTeam(selected);
            const chip = document.getElementById('chips').children[selected];
            if (chip) chip.scrollIntoView({ inline: 'center', block: 'nearest' });
        }
        document.addEventListener('keydown', e => {
            if (!document.getElementById('view-teams').classList.contains('active')) return;
            const ae = document.activeElement;
            if (ae && (ae.tagName === 'INPUT' || ae.tagName === 'SELECT' || ae.tagName === 'TEXTAREA' || ae.isContentEditable)) return;
            if (e.key === 'ArrowLeft') navTeam(-1);
            if (e.key === 'ArrowRight') navTeam(1);
        });

        function renderIdentity() {
            const t = TEAMS[selected], bc = budgetClass(t.budget, INITIAL), spent = INITIAL - t.budget;
            const el = document.getElementById('identity'); el.style.setProperty('--tc', t.color);
            el.innerHTML = `
    <div class="id-main"><span class="id-name cond">${esc(t.team)}</span><span class="id-eyebrow">Managed by <b>${esc(t.owner)}</b></span></div>
    <div class="id-stats">
      <div class="idstat"><span class="k">Budget</span><b class="v money ${bc} tnum">$${t.budget}</b></div>
      <div class="idstat"><span class="k">Max Bid</span><b class="v max tnum">${t.picks >= TOTAL ? '—' : '$' + maxBid(t)}</b></div>
      <div class="idstat"><span class="k">Spent</span><b class="v tnum">$${spent}</b></div>
      <div class="idstat"><span class="k">Roster</span><b class="v tnum">${t.picks}/${TOTAL}</b></div>
    </div>
    <div class="id-prog" style="width:${t.picks / TOTAL * 100}%"></div>`;
        }
        function showView(v) {
            ['teams', 'status', 'analysis'].forEach(x => {
                document.getElementById('view-' + x).classList.toggle('active', v === x);
                document.getElementById('seg-' + x).classList.toggle('active', v === x);
            });
            document.getElementById('teamstrip').style.display = v === 'teams' ? 'flex' : 'none';
            if (v === 'status') renderStatusView();
            else if (v === 'analysis') { renderAnalysisView(); boothOnShow(); }
            else renderTeamsView();
        }
        function activeViewId() { const a = document.querySelector('.view.active'); return a ? a.id : 'view-teams'; }

        // ---- The Booth: live analyst commentary (/api/v1/comments) ----
        // Persona identity (BOOTH_PERSONAS / BOOTH_LINEUP / boothPersona) lives in draft-shared.js.
        let boothMaxSeq = 0;          // newest seq shown (live-tail watermark)
        let boothMinSeq = null;       // oldest seq shown (backward-paging cursor)
        let boothPinned = true;       // user is parked at the live edge
        let boothLoadingOlder = false;
        let boothMoreOlder = true;
        let boothStarted = false;

        function boothFmtTime(ts) {
            try { return new Date(ts).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }); }
            catch (e) { return ''; }
        }
        function boothMsgEl(c) {
            const meta = boothPersona(c.persona);
            const row = document.createElement('div');
            row.className = 'booth-msg' + (meta.key === 'eisen' ? ' host' : '');
            row.style.setProperty('--pa', meta.accent);
            const mono = document.createElement('span');
            mono.className = 'mono'; mono.textContent = meta.initials;
            if (meta.img) {
                const img = document.createElement('img');
                img.className = 'av'; img.src = meta.img; img.alt = ''; img.title = meta.fullName;
                img.onerror = () => { img.style.display = 'none'; mono.style.display = 'grid'; };
                row.append(img, mono);
            } else {
                mono.style.display = 'grid'; row.append(mono);
            }
            const body = document.createElement('div'); body.className = 'body';
            const meta2 = document.createElement('div'); meta2.className = 'meta';
            const who = document.createElement('span'); who.className = 'who'; who.textContent = meta.label;
            const when = document.createElement('span'); when.className = 'when'; when.textContent = boothFmtTime(c.ts);
            meta2.append(who, when);
            const say = document.createElement('div'); say.className = 'say'; say.textContent = c.text;
            body.append(meta2, say); row.append(body);
            return row;
        }
        function renderBoothPanel() {
            const panel = document.getElementById('boothPanel');
            if (!panel || panel.childElementCount) return;   // build once
            BOOTH_LINEUP.forEach(slug => {
                const meta = boothPersona(slug);
                const mono = document.createElement('span');
                mono.className = 'pmono'; mono.textContent = meta.initials;
                mono.style.setProperty('--pa', meta.accent);
                const img = document.createElement('img');
                img.src = meta.img; img.alt = meta.fullName; img.title = meta.fullName;
                img.style.setProperty('--pa', meta.accent);
                img.onerror = () => img.replaceWith(mono);
                panel.append(img);
            });
        }
        function boothAtBottom() {
            const s = document.getElementById('boothScroll');
            return s.scrollHeight - s.scrollTop - s.clientHeight < 50;
        }
        function boothScrollToBottom() {
            const s = document.getElementById('boothScroll'); s.scrollTop = s.scrollHeight;
        }
        function boothJumpToLive() {
            boothPinned = true; boothScrollToBottom();
            document.getElementById('boothJump').hidden = true;
        }
        function boothClearEmpty() {
            const e = document.getElementById('boothEmpty'); if (e) e.remove();
        }
        async function boothLoadOlder() {
            if (boothLoadingOlder || !boothMoreOlder || boothMinSeq === null || boothMinSeq <= 1) return;
            boothLoadingOlder = true;
            const older = document.getElementById('boothOlder'); older.hidden = false;
            try {
                const fresh = await (await fetch(`${API_BASE}/comments?before=${boothMinSeq}&limit=50`)).json();
                if (Array.isArray(fresh) && fresh.length) {
                    const log = document.getElementById('boothLog');
                    const s = document.getElementById('boothScroll');
                    const prevH = s.scrollHeight;
                    const frag = document.createDocumentFragment();
                    fresh.forEach(c => frag.append(boothMsgEl(c)));
                    log.prepend(frag);
                    boothMinSeq = fresh[0].seq;
                    s.scrollTop += s.scrollHeight - prevH;   // anchor the viewport
                    if (fresh.length < 50 || boothMinSeq <= 1) boothMoreOlder = false;
                } else { boothMoreOlder = false; }
            } catch (e) { /* ignore */ }
            older.hidden = true; boothLoadingOlder = false;
        }
        async function boothPollLive() {
            try {
                const q = boothStarted ? `?since=${boothMaxSeq}` : '?limit=50';
                const fresh = await (await fetch(`${API_BASE}/comments${q}`)).json();
                if (!Array.isArray(fresh)) return;
                const log = document.getElementById('boothLog');
                if (!boothStarted) {
                    boothStarted = true;
                    renderBoothPanel();
                    if (fresh.length) {
                        boothClearEmpty();
                        const frag = document.createDocumentFragment();
                        fresh.forEach(c => frag.append(boothMsgEl(c)));
                        log.append(frag);
                        boothMinSeq = fresh[0].seq;
                        boothMaxSeq = fresh[fresh.length - 1].seq;
                        if (fresh.length < 50) boothMoreOlder = boothMinSeq > 1;
                        if (activeViewId() === 'view-analysis') boothScrollToBottom();
                    }
                    return;
                }
                if (fresh.length) {
                    boothClearEmpty();
                    const wasBottom = boothAtBottom();
                    const frag = document.createDocumentFragment();
                    fresh.forEach(c => frag.append(boothMsgEl(c)));
                    log.append(frag);
                    boothMaxSeq = fresh[fresh.length - 1].seq;
                    if (boothMinSeq === null) boothMinSeq = fresh[0].seq;
                    if (boothPinned && (wasBottom || activeViewId() !== 'view-analysis')) boothScrollToBottom();
                    else document.getElementById('boothJump').hidden = false;
                }
            } catch (e) { /* booth may not be running; stay quiet */ }
        }
        function boothOnShow() {
            renderBoothPanel();
            if (boothPinned) boothScrollToBottom();
        }
        function setupBooth() {
            const s = document.getElementById('boothScroll');
            if (!s) return;
            s.addEventListener('scroll', () => {
                if (s.scrollTop < 60) boothLoadOlder();
                if (boothAtBottom()) {
                    boothPinned = true;
                    document.getElementById('boothJump').hidden = true;
                } else {
                    boothPinned = false;
                }
            });
        }

        function renderTeamsView() {
            if (!TEAMS.length) return;
            renderIdentity();
            renderRoster();      // Task 5
            renderRail();        // Task 6 (radar)
        }
        // Map real nested player_stats into the flat keys the card/tooltip use; '–' when absent.
        function flattenStats(pos, st) {
            const o = { YDS:'–', TD:'–', INT:'–', RUSH:'–', REC:'–', FG:'–', XP:'–', PTS:'–', SACK:'–' };
            if (!st) return o;
            if (pos === 'QB' && st.passing) { o.YDS = st.passing.yards; o.TD = st.passing.tds; o.INT = st.passing.ints; }
            else if (pos === 'RB') { if (st.rushing){ o.RUSH = st.rushing.yards; o.TD = st.rushing.tds; } if (st.receiving) o.REC = st.receiving.receptions; }
            else if (pos === 'WR' || pos === 'TE') { if (st.receiving){ o.REC = st.receiving.receptions; o.YDS = st.receiving.yards; o.TD = st.receiving.tds; } }
            else if (pos === 'K' && st.kicking) { o.FG = st.kicking.fgm; o.XP = st.kicking.xpm; o.PTS = st.kicking.points; }
            return o;  // D/ST has no structured stats in the backend -> all '–'
        }
        function normPlayer(pick) {
            const pl = playersById[pick.player_id];
            if (!pl) return null;
            const st = playerStats[pl.id];
            const bye = (pl.position === 'D/ST') ? defenseBye(pl.team) : (st ? st.bye_week : null);
            return { id: pl.id, fn: pl.first_name, ln: pl.last_name, pos: pl.position, nfl: pl.team,
                     bye: bye, price: pick.price, stats: flattenStats(pl.position, st) };
        }
        function rosterFor(t) {
            return t._picks.map(normPlayer).filter(Boolean)
                .sort((a, b) => (POSORDER[a.pos] - POSORDER[b.pos]) || (b.price - a.price));
        }
        function posCounts(roster) { const c = {}; roster.forEach(p => c[p.pos] = (c[p.pos] || 0) + 1); return c; }
        // The 3 card stat boxes per position (matches the mockup's statCells shape).
        function statCells(p) {
            if (p.pos === 'QB') return [['Yds', p.stats.YDS, STATMAX.YDS], ['TD', p.stats.TD, STATMAX.TD], ['Int', p.stats.INT, STATMAX.INT]];
            if (p.pos === 'RB') return [['Ru Yds', p.stats.RUSH, STATMAX.RUSH], ['TD', p.stats.TD, STATMAX.TD], ['Rec', p.stats.REC, STATMAX.REC]];
            if (p.pos === 'WR' || p.pos === 'TE') return [['Rec', p.stats.REC, STATMAX.REC], ['Yds', p.stats.YDS, STATMAX.YDS], ['TD', p.stats.TD, STATMAX.TD]];
            if (p.pos === 'K') return [['FG', p.stats.FG, STATMAX.FG], ['XP', p.stats.XP, STATMAX.XP], ['Pts', p.stats.PTS, STATMAX.PTS]];
            return [['Sack', p.stats.SACK, STATMAX.SACK], ['Int', p.stats.INT, STATMAX.INT], ['TD', p.stats.TD, STATMAX.TD]];
        }
        const SKILL = { QB: 1, RB: 1, WR: 1, TE: 1 };   // positions where a shared bye actually hurts
        function setRosterMode(m) {
            rosterMode = m;
            document.querySelectorAll('#rmode button').forEach(b => {
                const on = b.id === 'rm-' + m;
                b.classList.toggle('active', on);
                b.setAttribute('aria-pressed', String(on));
            });
            renderRoster();
        }
        function renderRoster() {
            curRoster = rosterFor(TEAMS[selected]);
            const box = document.getElementById('roster');
            if (rosterMode === 'bye') { box.className = 'roster-bye'; renderRosterBye(box); }
            else if (rosterMode === 'list') { box.className = 'roster-list'; renderRosterList(box); }
            else { box.className = 'roster-grid'; renderRosterCards(box); }
        }
        function renderRosterCards(box) {
            let html = '', lastPos = null;
            curRoster.forEach((p, idx) => {
                if (p.pos !== lastPos) { html += `<div class="posgroup" style="color:${POSCOLOR[p.pos]}"><span class="dot" style="background:${POSCOLOR[p.pos]}"></span>${p.pos}<span class="ln"></span></div>`; lastPos = p.pos; }
                const cells = statCells(p).map(c => `<div class="st"><b class="tnum">${c[1]}</b><span>${c[0]}</span></div>`).join('');
                const byeChip = p.bye ? `<span class="pc-bye tnum">BYE ${p.bye}</span>` : '';
                html += `<div class="pcard" style="--pc:${POSCOLOR[p.pos]};--tmc:${teamColor(p.nfl)}" data-idx="${idx}" onmouseenter="showTip(event,${idx})" onmousemove="moveTip(event)" onmouseleave="hideTip()">
      <div class="pc-photo">
        <img class="pc-wm" src="${getTeamLogoUrl(p.nfl)}" alt="" onerror="this.style.display='none'">
        ${shotImg(p, 'pc-shot')}
        <span class="pc-pos ${LIGHTPOS[p.pos] ? 'light' : ''}">${p.pos}</span>
        <div class="pc-corner"><span class="pc-price tnum">$${p.price}</span>${byeChip}</div>
        <div class="pc-scrim"><div class="pc-name">${esc(p.fn)} ${esc(p.ln)}</div><div class="pc-sub">${esc(p.nfl)}</div></div>
      </div>
      <div class="pc-stats">${cells}</div>
    </div>`;
            });
            box.innerHTML = html;
        }
        function posBreak(items) { const c = {}; items.forEach(({ p }) => c[p.pos] = (c[p.pos] || 0) + 1); return c; }
        function renderRosterBye(box) {
            const weeks = {};
            curRoster.forEach((p, idx) => { const w = p.bye || 0; (weeks[w] = weeks[w] || []).push({ p, idx }); });
            const wkNums = Object.keys(weeks).map(Number).filter(w => w > 0).sort((a, b) => a - b);
            if (!wkNums.length) { box.innerHTML = '<div class="bye-empty">No bye-week data for this roster yet.</div>'; return; }
            let worst = null;
            wkNums.forEach(w => { const pb = posBreak(weeks[w]); const hot = Object.entries(pb).filter(([k, v]) => SKILL[k] && v >= 2); const max = Math.max(0, ...hot.map(([, v]) => v)); if (max && (!worst || max > worst.max)) worst = { w, max, hot }; });
            const cols = wkNums.map(w => {
                const items = weeks[w], pb = posBreak(weeks[w]);
                const hot = Object.entries(pb).filter(([k, v]) => SKILL[k] && v >= 2);
                const flag = hot.length ? hot.map(([k, v]) => `${v}× ${k}`).join(' · ') : '';
                const chips = items.sort((a, b) => POSORDER[a.p.pos] - POSORDER[b.p.pos]).map(({ p, idx }) =>
                    `<div class="bw-chip" style="--pc:${POSCOLOR[p.pos]};--tmc:${teamColor(p.nfl)}" data-idx="${idx}" onmouseenter="showTip(event,${idx})" onmousemove="moveTip(event)" onmouseleave="hideTip()"><span class="bw-pos">${p.pos}</span><span class="bw-nm">${esc(p.ln)}</span></div>`).join('');
                return `<div class="bye-wk ${hot.length ? 'exposed' : ''}">
                    <div class="bw-head"><span class="bw-num cond">WK ${w}</span><span class="bw-cnt">${items.length}</span></div>
                    ${flag ? `<div class="bw-flag">${flag}</div>` : '<div class="bw-flag ok">covered</div>'}
                    <div class="bw-chips">${chips}</div></div>`;
            }).join('');
            const summary = worst
                ? `<div class="bye-summary exposed"><span class="bs-ico">⚠</span>Toughest week: <b>WK ${worst.w}</b> — ${worst.hot.map(([k, v]) => `${v} ${k}`).join(', ')} on bye together</div>`
                : `<div class="bye-summary ok"><span class="bs-ico">✓</span>Byes are well spread — no week leaves you doubled-up at a position.</div>`;
            box.innerHTML = summary + `<div class="bye-track">${cols}</div>`;
        }
        function renderRosterList(box) {
            let html = '<div class="rl-head"><span class="rl-pos"></span><span class="rl-nm">Player</span><span class="rl-team">Team</span><span class="rl-c">Bye</span><span class="rl-c rl-stat">Key Stat</span><span class="rl-c rl-price">Price</span></div>';
            curRoster.forEach((p, idx) => {
                const key = statCells(p)[0];
                const byeCls = curRoster.filter(q => q.bye && q.bye === p.bye && SKILL[q.pos] && q.pos === p.pos).length >= 2 ? ' clash' : '';
                html += `<div class="rl-row" style="--tmc:${teamColor(p.nfl)}" data-idx="${idx}" onmouseenter="showTip(event,${idx})" onmousemove="moveTip(event)" onmouseleave="hideTip()">
                    <span class="rl-pos" style="background:${POSCOLOR[p.pos]}${LIGHTPOS[p.pos] ? ';color:#fff' : ''}">${p.pos}</span>
                    <span class="rl-nm">${esc(p.fn)} ${esc(p.ln)}</span>
                    <span class="rl-team">${esc(p.nfl)}</span>
                    <span class="rl-c rl-bye${byeCls}">${p.bye || '—'}</span>
                    <span class="rl-c rl-stat"><b class="tnum">${key[1]}</b><i>${key[0]}</i></span>
                    <span class="rl-c rl-price tnum">$${p.price}</span></div>`;
            });
            box.innerHTML = html;
        }
        function renderRail(){
          const counts={}; curRoster.forEach(p=>counts[p.pos]=(counts[p.pos]||0)+1);
          const newFrac=RADAR_ORDER.map(pos=>Math.min((counts[pos]||0)/POSMAX[pos],1));
          document.getElementById('radarwrap').innerHTML=renderRadar(counts,TEAMS[selected].color,prevFrac);
          animateRadarTo(prevFrac.slice(),newFrac);
          prevFrac=newFrac;
        }
        const RADAR_GEO={cx:120,cy:120,rO:82,n:6};
        function radarPoint(i,frac){const{cx,cy,rO,n}=RADAR_GEO;const a=-Math.PI/2+i/n*2*Math.PI;return[cx+Math.cos(a)*frac*rO,cy+Math.sin(a)*frac*rO];}
        function renderRadar(counts,color,shapeFrac){
          const{cx,cy,rO,n}=RADAR_GEO, size=240,rings=3;
          const pt=(a,r)=>[cx+Math.cos(a)*r,cy+Math.sin(a)*r];
          let s=`<svg class="radar" viewBox="0 0 ${size} ${size}" preserveAspectRatio="xMidYMid meet">`;
          for(let ring=1;ring<=rings;ring++){const rr=rO/rings*ring;let pts=[];for(let i=0;i<n;i++){const a=-Math.PI/2+i/n*2*Math.PI;const p=pt(a,rr);pts.push(p[0].toFixed(1)+','+p[1].toFixed(1));}s+=`<polygon class="r-grid ${ring===rings?'r-outer':''}" points="${pts.join(' ')}"/>`;}
          for(let i=0;i<n;i++){const a=-Math.PI/2+i/n*2*Math.PI;const p=pt(a,rO);s+=`<line class="r-axis" x1="${cx}" y1="${cy}" x2="${p[0].toFixed(1)}" y2="${p[1].toFixed(1)}"/>`;}
          let sp=[],dots='';
          for(let i=0;i<n;i++){const p=radarPoint(i,shapeFrac[i]);sp.push(p[0].toFixed(1)+','+p[1].toFixed(1));dots+=`<circle class="r-dot" cx="${p[0].toFixed(1)}" cy="${p[1].toFixed(1)}" r="3" fill="${color}"/>`;}
          s+=`<polygon class="r-shape" points="${sp.join(' ')}" style="fill:${hexA(color,.2)};stroke:${color};filter:drop-shadow(0 0 7px ${hexA(color,.55)})"/>`+dots;
          for(let i=0;i<n;i++){const pos=RADAR_ORDER[i];const a=-Math.PI/2+i/n*2*Math.PI;const p=pt(a,rO+16);let anc='middle';if(Math.cos(a)>0.4)anc='start';else if(Math.cos(a)<-0.4)anc='end';let dy=4;if(Math.sin(a)>0.5)dy=11;else if(Math.sin(a)<-0.5)dy=-3;
            s+=`<text class="r-label" x="${p[0].toFixed(1)}" y="${(p[1]+dy).toFixed(1)}" text-anchor="${anc}" fill="${POSCOLOR[pos]}">${pos}</text>`;
            s+=`<text class="r-cnt" x="${p[0].toFixed(1)}" y="${(p[1]+dy+11).toFixed(1)}" text-anchor="${anc}">${counts[pos]||0}/${POSMAX[pos]}</text>`;}
          return s+'</svg>';
        }
        function animateRadarTo(from,to){
          const svg=document.querySelector('#radarwrap .radar'); if(!svg)return;
          const shape=svg.querySelector('.r-shape'), dots=svg.querySelectorAll('.r-dot'), dur=480, t0=performance.now();
          function step(now){
            const tt=Math.min(1,(now-t0)/dur), e=1-Math.pow(1-tt,3);
            let pts=[];
            for(let i=0;i<RADAR_GEO.n;i++){const f=from[i]+(to[i]-from[i])*e;const p=radarPoint(i,f);pts.push(p[0].toFixed(1)+','+p[1].toFixed(1));if(dots[i]){dots[i].setAttribute('cx',p[0].toFixed(1));dots[i].setAttribute('cy',p[1].toFixed(1));}}
            shape.setAttribute('points',pts.join(' '));
            if(tt<1)requestAnimationFrame(step);
          }
          requestAnimationFrame(step);
        }
        function renderStatusView() {
            renderLiveAuction();
            renderBudgetCompact();
            renderLedger();
            renderAvailable();
        }
        function renderAnalysisView() {
            renderMarketStrips();
            renderBargain();
            renderBuying();
            renderMatrix();
            renderInsights();
            renderTopBuys();
            renderTempo();
        }
        // A "budget dump" is a completed team's FINAL pick where they emptied their wallet on
        // an over-market player — use-it-or-lose-it money, not a value signal. Deterministic:
        // last pick by pick_id + ≥2× the positional median + left them ≤$2. Positional medians
        // here come from ALL picks (median is robust to the handful of dumps we're detecting),
        // so this needs no dump-free MARKET and avoids a circular dependency.
        function budgetDumpIds() {
            const byPos = {};
            (lastDraftState ? lastDraftState.teams : []).forEach(t => t.picks.forEach(pk => {
                const pl = playersById[pk.player_id]; if (pl) (byPos[pl.position] = byPos[pl.position] || []).push(pk.price);
            }));
            const medOf = pos => { const a = byPos[pos]; return (a && a.length >= 3) ? median(a) : 1; };
            const dumps = new Set();
            (lastDraftState ? lastDraftState.teams : []).forEach(t => {
                const done = t.manually_done || t.picks.length >= TOTAL;
                if (!done || !t.picks.length) return;
                const final = t.picks.reduce((a, b) => (b.pick_id > a.pick_id ? b : a));
                const pl = playersById[final.player_id]; if (!pl) return;
                if (final.price >= 2 * medOf(pl.position) && final.price >= 5 && t.budget_remaining <= 2) dumps.add(final.pick_id);
            });
            return dumps;
        }
        function computeMarket() {
            DUMPS = budgetDumpIds();
            const log = buildDraftLog().filter(l => !DUMPS.has(l.pickId)); MARKET = {};   // baselines exclude dumps
            RADAR_ORDER.forEach(pos => {
                const a = log.filter(l => l.pos === pos).map(l => l.price);
                if (a.length) { const m = a.reduce((s, v) => s + v, 0) / a.length;
                    MARKET[pos] = { n: a.length, md: median(a), mean: m, sd: Math.sqrt(a.reduce((s, v) => s + (v - m) ** 2, 0) / a.length) || 1, min: Math.min(...a), max: Math.max(...a), total: a.reduce((s, v) => s + v, 0) }; }
            });
        }

        /* ── Live Auction ── */
        function renderLiveAuction() {
            const el = document.getElementById('liveAuction');
            const nom = lastDraftState && lastDraftState.nominated;
            if (!nom) { el.innerHTML = '<div class="la-empty">Awaiting nomination…</div>'; return; }
            const p = normPlayer({ player_id: nom.player_id, price: nom.current_bid });
            const bidder = ownersById[nom.current_bidder_id];
            if (!p) { el.innerHTML = '<div class="la-empty">Awaiting nomination…</div>'; return; }
            el.innerHTML = `<div class="la-body">
                <div class="la-photo"><span class="la-pos" style="background:${POSCOLOR[p.pos]}">${p.pos}</span>${shotImg(p, '')}</div>
                <div class="la-info"><div class="la-eyebrow">Now Auctioning <span class="la-live"><span class="d"></span>LIVE</span></div>
                  <div class="la-name cond">${esc(p.fn)} ${esc(p.ln)}</div><div class="la-sub">${esc(p.nfl)} · ${p.pos}</div></div>
                <div class="la-bid"><div class="k">Current Bid</div><div class="v tnum">$${nom.current_bid}</div>
                  <div class="la-bidder"><span class="dot" style="background:${bidder ? bidder.color : '#888'}"></span>${bidder ? esc(bidder.team_name) : '—'}</div></div>
            </div>`;
        }

        /* ── Draft Status: ledger · available · money ── */
        function buildLedger() {
            const rows = [];
            (lastDraftState ? lastDraftState.teams : []).forEach(t => {
                const tm = TEAMS.find(x => x.owner_id === t.owner_id);
                t.picks.forEach(pk => { const pl = playersById[pk.player_id]; if (pl && tm) rows.push({ pickId: pk.pick_id, id: pl.id, name: `${pl.first_name} ${pl.last_name}`, pos: pl.position, nfl: pl.team, team: tm.team, owner: tm.owner, color: tm.color, price: pk.price }); });
            });
            rows.sort((a, b) => a.pickId - b.pickId);
            rows.forEach((r, i) => r.ord = i + 1);
            return rows;
        }
        function ledgerPriceCls(pos, price) {
            const m = MARKET[pos]; if (!m || m.n < 3) return '';
            if (price <= 1) return 'lo';
            return (price >= 2 * m.md && price >= 8) ? 'hi' : '';
        }
        const arrow = dir => dir > 0 ? ' <i class="ar">▲</i>' : ' <i class="ar">▼</i>';
        function thCells(elId, cols, activeKey, dir, setter) {
            document.getElementById(elId).innerHTML = cols.map(c => {
                const isActive = activeKey === c.k;
                const ariaSort = isActive ? ` aria-sort="${dir > 0 ? 'ascending' : 'descending'}"` : '';
                return `<span class="th ${c.cls || ''} ${isActive ? 'active' : ''}" role="button" tabindex="0"${ariaSort} onclick="${setter}('${c.k}')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();${setter}('${c.k}')}">${c.lbl}${isActive ? arrow(dir) : ''}</span>`;
            }).join('');
        }
        function setLedgerSort(k) {
            if (ledgerSort === k) ledgerDir *= -1;
            else { ledgerSort = k; ledgerDir = (k === 'order' || k === 'price') ? -1 : 1; }
            renderLedger();
        }
        function ledgerCmp(a, b) {
            let r = 0;
            if (ledgerSort === 'price') r = a.price - b.price;
            else if (ledgerSort === 'team') r = a.team.localeCompare(b.team);
            else if (ledgerSort === 'pos') r = POSORDER[a.pos] - POSORDER[b.pos];
            else if (ledgerSort === 'name') r = a.name.localeCompare(b.name);
            else r = a.ord - b.ord;
            r *= ledgerDir;
            return r || (b.ord - a.ord);   // stable: newest first on ties
        }
        function renderLedger() {
            thCells('ldHead', [{ k: 'order', lbl: '#', cls: 'ct' }, { k: 'pos', lbl: 'Pos', cls: 'ct' }, { k: 'name', lbl: 'Player' }, { k: 'team', lbl: 'Team' }, { k: 'price', lbl: '$', cls: 'rt' }], ledgerSort, ledgerDir, 'setLedgerSort');
            let rows = buildLedger();
            const q = ledgerQuery.trim().toLowerCase();
            if (q) rows = rows.filter(r => r.name.toLowerCase().includes(q) || r.team.toLowerCase().includes(q) || r.owner.toLowerCase().includes(q));
            rows.sort(ledgerCmp);
            const box = document.getElementById('ledger');
            if (!rows.length) { box.innerHTML = '<div class="ld-empty">No picks match that search.</div>'; return; }
            box.innerHTML = rows.map(r => {
                const isNew = r.pickId > __recentSince;
                const pcls = ledgerPriceCls(r.pos, r.price);
                return `<div class="ld-row${isNew ? ' ld-new' : ''}" style="--tmc:${teamColor(r.nfl)}">
                    <span class="ld-no tnum">${r.ord}</span>
                    <span class="ld-pos" style="background:${POSCOLOR[r.pos]}${LIGHTPOS[r.pos] ? ';color:#fff' : ''}">${r.pos}</span>
                    <span class="ld-name">${esc(r.name)} <i>${esc(r.nfl)}</i></span>
                    <span class="ld-team"><span class="ld-dot" style="background:${r.color}"></span>${esc(r.team)}</span>
                    <span class="ld-price tnum ${pcls}">$${r.price}</span></div>`;
            }).join('');
        }
        // Production score -- intentionally distinct from booth's production_score
        // (src/booth/slice.py) and ledger price tiers (valueTier below).
        function prodScore(p) {
            const st = playerStats[p.id]; if (!st) return -1;
            const n = v => num(v) || 0;
            if (p.pos === 'QB' && st.passing) return n(st.passing.yards) + n(st.passing.tds) * 20 - n(st.passing.ints) * 10 + (st.rushing ? n(st.rushing.yards) : 0);
            if (p.pos === 'RB') return (st.rushing ? n(st.rushing.yards) : 0) + (st.receiving ? n(st.receiving.yards) : 0) + ((st.rushing ? n(st.rushing.tds) : 0) + (st.receiving ? n(st.receiving.tds) : 0)) * 60;
            if (p.pos === 'WR' || p.pos === 'TE') return st.receiving ? n(st.receiving.yards) + n(st.receiving.tds) * 60 + n(st.receiving.receptions) : 0;
            if (p.pos === 'K') return st.kicking ? n(st.kicking.points) : 0;
            return 0;
        }
        function prodShort(p) {
            const st = playerStats[p.id]; if (!st) return '';
            if (p.pos === 'QB' && st.passing) return `${st.passing.yards} yd`;
            if (p.pos === 'RB' && st.rushing) return `${st.rushing.yards} ru`;
            if ((p.pos === 'WR' || p.pos === 'TE') && st.receiving) return `${st.receiving.yards} yd`;
            if (p.pos === 'K' && st.kicking) return `${st.kicking.points} pt`;
            return '';
        }
        function byeOf(p) { const st = playerStats[p.id]; return p.pos === 'D/ST' ? defenseBye(p.nfl) : (st ? st.bye_week : null); }
        function setAvailPos(pos) { availPos = pos; renderAvailable(); }
        function setAvailSort(k) {
            if (availSort === k) availDir *= -1;
            else { availSort = k; availDir = (k === 'prod') ? -1 : 1; }
            renderAvailable();
        }
        function availCmp(a, b) {
            let r = 0;
            if (availSort === 'prod') r = prodScore(a) - prodScore(b);
            else if (availSort === 'bye') r = (byeOf(a) || 99) - (byeOf(b) || 99);
            else if (availSort === 'team') r = a.nfl.localeCompare(b.nfl);
            else if (availSort === 'name') r = (a.ln + a.fn).localeCompare(b.ln + b.fn);
            else r = POSORDER[a.pos] - POSORDER[b.pos];
            r *= availDir;
            return r || (prodScore(b) - prodScore(a));   // tie-break: most productive first
        }
        function renderAvailable() {
            const counts = {}; AVAILABLE.forEach(p => counts[p.pos] = (counts[p.pos] || 0) + 1);
            const order = RADAR_ORDER.filter(pos => counts[pos]);
            document.getElementById('availCount').textContent = `${AVAILABLE.length} left`;
            const chips = [`<button class="af-chip ${availPos === 'ALL' ? 'active' : ''}" aria-pressed="${availPos === 'ALL'}" onclick="setAvailPos('ALL')">All <i>${AVAILABLE.length}</i></button>`]
                .concat(order.map(pos => `<button class="af-chip ${availPos === pos ? 'active' : ''}" aria-pressed="${availPos === pos}" style="--pc:${POSCOLOR[pos]}" onclick="setAvailPos('${pos}')">${pos} <i>${counts[pos]}</i></button>`));
            document.getElementById('availFilter').innerHTML = chips.join('');
            thCells('avHead', [{ k: 'pos', lbl: 'Pos', cls: 'ct' }, { k: 'name', lbl: 'Player' }, { k: 'team', lbl: 'Tm' }, { k: 'bye', lbl: 'Bye', cls: 'rt' }, { k: 'prod', lbl: STATS_YR, cls: 'rt' }], availSort, availDir, 'setAvailSort');
            const list = AVAILABLE.filter(p => availPos === 'ALL' || p.pos === availPos).sort(availCmp);
            const box = document.getElementById('availList');
            if (!list.length) { box.innerHTML = '<div class="av-empty">No players left here.</div>'; return; }
            box.innerHTML = list.slice(0, 300).map(p => {
                const bye = byeOf(p);
                return `<div class="av-row">
                    <span class="av-pos" style="background:${POSCOLOR[p.pos]}${LIGHTPOS[p.pos] ? ';color:#fff' : ''}">${p.pos}</span>
                    <span class="av-nm">${esc(p.fn)} ${esc(p.ln)}</span>
                    <span class="av-team">${esc(p.nfl)}</span>
                    <span class="av-bye tnum">${bye || '—'}</span>
                    <span class="av-prod tnum">${prodShort(p)}</span></div>`;
            }).join('');
        }
        function renderBudgetCompact() {
            const ranked = [...TEAMS].sort((a, b) => b.budget - a.budget);
            const totalLeft = TEAMS.reduce((s, t) => s + t.budget, 0);
            document.getElementById('moneyNote').textContent = `$${totalLeft} left in the room`;
            document.getElementById('budgetPower').innerHTML = ranked.map((t, i) => {
                const mb = t.picks >= TOTAL ? '—' : '$' + maxBid(t);
                return `<div class="mn-row"><span class="mn-rank tnum">${i + 1}</span>
                    <span class="mn-name"><span class="mn-dot" style="background:${t.color}"></span><span class="nm">${esc(t.team)}</span></span>
                    <span class="mn-track"><span class="mn-fill" style="width:${t.budget / INITIAL * 100}%"></span></span>
                    <span class="mn-val tnum rt">$${t.budget}</span>
                    <span class="mn-max tnum rt" title="Max bid this team can still place">${mb}</span></div>`;
            }).join('');
        }
        function setupStatusControls() {
            const s = document.getElementById('ldSearch');
            if (s) s.addEventListener('input', () => { ledgerQuery = s.value; renderLedger(); });
        }

        /* ── Target Board ── */
        let targets = []; try { targets = JSON.parse(localStorage.getItem('ffdraft_targets') || '[]'); } catch (e) {}
        let dragId = null, dragSrc = null;
        function saveTargets() { try { localStorage.setItem('ffdraft_targets', JSON.stringify(targets)); } catch (e) {} }
        function pById(id) { return AVAILABLE.find(p => p.id === id); }
        function tbRow(p, cls, btn) {
            return `<div class="${cls}" draggable="true" data-id="${p.id}">
          <span class="tb-pos" style="background:${POSCOLOR[p.pos]}${LIGHTPOS[p.pos] ? ';color:#fff' : ''}">${p.pos}</span>
          <span class="tb-nm">${esc(p.fn)} ${esc(p.ln)}</span><span class="tb-meta">${esc(p.nfl)}</span>${btn}</div>`;
        }
        function renderResults() {
            const q = document.getElementById('tbSearch').value.trim().toLowerCase(), box = document.getElementById('tbResults');
            if (!q) { box.style.display = 'none'; box.innerHTML = ''; return; }
            const m = AVAILABLE.filter(p => !targets.includes(p.id) && (p.fn + ' ' + p.ln).toLowerCase().includes(q)).slice(0, 7);
            box.style.display = m.length ? 'block' : 'none';
            box.innerHTML = m.map(p => tbRow(p, 'tb-res', '<button class="tb-add" title="Add to targets">+</button>')).join('');
            box.querySelectorAll('.tb-res').forEach(el => {
                const id = +el.dataset.id;
                el.addEventListener('dragstart', e => { dragId = id; dragSrc = 'res'; e.dataTransfer.effectAllowed = 'copy'; e.dataTransfer.setData('text/plain', id); });
                el.querySelector('.tb-add').addEventListener('click', ev => { ev.stopPropagation(); addTarget(id); });
                el.addEventListener('click', () => addTarget(id));
            });
        }
        function addTarget(id) { if (!targets.includes(id)) { targets.push(id); saveTargets(); renderTargets(); } const s = document.getElementById('tbSearch'); s.value = ''; renderResults(); s.focus(); }
        function removeTarget(id) { targets = targets.filter(t => t !== id); saveTargets(); renderTargets(); }
        function renderTargets() {
            const box = document.getElementById('tbTargets');
            if (!targets.length) { box.innerHTML = '<div class="tb-empty">Search above and drag (or +) players here<br>to build your target list.</div>'; return; }
            box.innerHTML = targets.map((id, i) => { const p = pById(id); return p ? tbRow(p, 'tb-tgt', '<button class="tb-x" title="Remove">✕</button>').replace('<span class="tb-pos"', `<span class="tb-rank">${i + 1}</span><span class="tb-pos"`) : ''; }).join('');
            box.querySelectorAll('.tb-tgt').forEach(el => {
                const id = +el.dataset.id;
                el.addEventListener('dragstart', e => { dragId = id; dragSrc = 'tgt'; e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', id); });
                el.querySelector('.tb-x').addEventListener('click', () => removeTarget(id));
            });
        }
        function tgtAfter(box, y) { return [...box.querySelectorAll('.tb-tgt')].find(r => { const b = r.getBoundingClientRect(); return y < b.top + b.height / 2; }); }
        function setupTargetBoard() {
            document.getElementById('tbSearch').addEventListener('input', renderResults);
            const box = document.getElementById('tbTargets');
            box.addEventListener('dragover', e => { e.preventDefault(); box.classList.add('drag-over'); box.querySelectorAll('.tb-tgt').forEach(r => r.classList.remove('drop-before')); const a = tgtAfter(box, e.clientY); if (a) a.classList.add('drop-before'); });
            box.addEventListener('dragleave', () => box.classList.remove('drag-over'));
            box.addEventListener('drop', e => {
                e.preventDefault(); box.classList.remove('drag-over');
                if (dragSrc === 'res') { addTarget(dragId); }
                else if (dragSrc === 'tgt') { const a = tgtAfter(box, e.clientY); targets = targets.filter(t => t !== dragId); const idx = a ? targets.indexOf(+a.dataset.id) : targets.length; targets.splice(idx < 0 ? targets.length : idx, 0, dragId); saveTargets(); renderTargets(); }
                dragId = null; dragSrc = null;
            });
            renderTargets();
        }

        /* hover tooltip — full stat line + price-vs-market context (not a re-run of the card) */
        function num(v) { const n = parseFloat(String(v).replace(/,/g, '')); return isNaN(n) ? null : n; }
        function detailStats(pos, st) {
            if (!st) return [];
            const r = [];
            if (pos === 'QB') { if (st.passing) r.push(['Pass Yds', st.passing.yards, STATMAX.YDS], ['Pass TD', st.passing.tds, STATMAX.TD], ['Int', st.passing.ints, STATMAX.INT], ['Rating', st.passing.rating, 158.3]); if (st.rushing) r.push(['Rush Yds', st.rushing.yards, 900], ['Rush TD', st.rushing.tds, 15]); }
            else if (pos === 'RB') { if (st.rushing) r.push(['Rush Yds', st.rushing.yards, STATMAX.RUSH], ['Rush TD', st.rushing.tds, STATMAX.TD], ['Yds/Carry', st.rushing.avg, 6]); if (st.receiving) r.push(['Rec', st.receiving.receptions, STATMAX.REC], ['Rec Yds', st.receiving.yards, 1000], ['Rec TD', st.receiving.tds, 12]); }
            else if (pos === 'WR' || pos === 'TE') { if (st.receiving) r.push(['Rec', st.receiving.receptions, STATMAX.REC], ['Targets', st.receiving.targets, 180], ['Rec Yds', st.receiving.yards, STATMAX.YDS], ['Rec TD', st.receiving.tds, STATMAX.TD], ['Yds/Rec', st.receiving.avg, 20]); }
            else if (pos === 'K') { if (st.kicking) r.push(['FG Made', st.kicking.fgm, STATMAX.FG], ['FG%', st.kicking.fg_pct, 100], ['Long', st.kicking.long, 70], ['XP', st.kicking.xpm, STATMAX.XP], ['Points', st.kicking.points, STATMAX.PTS]); }
            return r;
        }
        // Price tiers -- intentionally distinct from booth's production_score
        // (src/booth/slice.py) and the viewer's prodScore above.
        // Plain-language read on a price vs the position's going rate. Uses the median
        // ratio (not spread): auction prices decay toward the $1 floor late, which wrecks
        // std-dev. $1 picks are treated as a neutral "minimum bid", never "below market".
        function valueTier(pos, price) {
            const m = MARKET[pos];
            if (!m || m.n < 3) return null;
            if (price <= 1) return { label: 'league-minimum bid', cls: 'mid', md: m.md, floor: true };
            // ratio for the headline + an absolute-$ gate so cheap positions (median ~$1)
            // don't flag a $2 pick as "well above market".
            const md = m.md || 1, ratio = price / md, over = price - md;
            let label, cls;
            if (ratio >= 2 && over >= 3) { label = 'well above market'; cls = 'hot'; }
            else if (ratio >= 1.35 && over >= 2) { label = 'above market'; cls = 'hot'; }
            else if (ratio >= 0.7) { label = 'around market'; cls = 'mid'; }
            else if (ratio >= 0.45) { label = 'below market'; cls = 'cold'; }
            else { label = 'well below market'; cls = 'cold'; }
            return { label, cls, md, floor: false };
        }
        function ctxHTML(pos, price, t) {
            if (!t) return '';
            const tail = t.floor ? '' : ` <span>typical ${pos} $${t.md}</span>`;
            return `<div class="tt-ctx ${t.cls}"><b>$${price}</b> · ${t.label}${tail}</div>`;
        }
        function priceCtx(pos, price) { return ctxHTML(pos, price, valueTier(pos, price)); }
        function showTip(e, i) {
            const p = curRoster[i], tip = document.getElementById('ptip');
            tip.style.setProperty('--pc', POSCOLOR[p.pos]);
            const det = detailStats(p.pos, playerStats[p.id]);
            const rows = det.length
                ? det.map(c => { const n = num(c[1]); return `<div class="tt-stat"><span class="l">${c[0]}</span><span class="bar"><i style="width:${n != null ? Math.min(n / c[2] * 100, 100) : 0}%"></i></span><span class="n tnum">${c[1] == null ? '–' : c[1]}</span></div>`; }).join('')
                : '<div class="tt-none">No box-score stats for this position.</div>';
            tip.innerHTML = `<div class="tt-head"><span class="tt-pos ${LIGHTPOS[p.pos] ? 'light' : ''}" style="background:${POSCOLOR[p.pos]}">${p.pos}</span><span class="tt-name">${esc(p.fn)} ${esc(p.ln)}</span></div>
                <div class="tt-sub">${esc(p.nfl)}${p.bye ? ' · Bye ' + p.bye : ''}</div>
                ${priceCtx(p.pos, p.price)}
                <div class="tt-stats">${rows}</div>`;
            tip.style.display = 'block'; moveTip(e);
        }
        function moveTip(e) {
            const tip = document.getElementById('ptip'); if (tip.style.display !== 'block') return;
            const w = tip.offsetWidth, h = tip.offsetHeight;
            let x = e.clientX + 18, y = e.clientY + 18;
            if (x + w > window.innerWidth - 8) x = e.clientX - w - 18;
            if (y + h > window.innerHeight - 8) y = window.innerHeight - h - 8;
            tip.style.left = x + 'px'; tip.style.top = Math.max(8, y) + 'px';
        }
        function hideTip() { document.getElementById('ptip').style.display = 'none'; }

        // Chronological pick log for the cost timeline: one entry per pick, x = pick order.
        function buildDraftLog() {
            const picks = [];
            (lastDraftState ? lastDraftState.teams : []).forEach(t => {
                const tm = TEAMS.find(x => x.owner_id === t.owner_id);
                t.picks.forEach(pk => {
                    const pl = playersById[pk.player_id];
                    if (pl && tm) picks.push({ pickId: pk.pick_id, pos: pl.position, price: pk.price,
                        name: `${pl.first_name} ${pl.last_name}`, teamName: tm.team, color: tm.color });
                });
            });
            picks.sort((a, b) => a.pickId - b.pickId);
            return picks.map((p, i) => ({ no: i + 1, pickId: p.pickId, pos: p.pos, price: p.price, name: p.name, teamName: p.teamName, color: p.color }));
        }
        /* ── Draft Analysis: market strips · roster matrix · insights · tempo ── */
        // Computes the data + geometry once per poll, then hands off to drawMarket(), which the
        // pan/zoom handlers also call. The x-axis is the only zoomable one (positions are rows).
        function renderMarketStrips() {
            const wrap = document.getElementById('market');
            const order = RADAR_ORDER.filter(pos => MARKET[pos]);
            if (!order.length) { wrap.innerHTML = '<div class="an-empty">No picks yet — the market opens with the first sale.</div>'; marketGeo = null; updateMarketZoomUI(); return; }
            const log = buildDraftLog();   // full log (incl dumps) so a dump dot still appears, marked
            const dataMax = Math.max(10, ...log.map(l => l.price));
            const W = 720, rowH = 48, padL = 52, padR = 20, padT = 10, padB = 26;
            marketGeo = { W, H: padT + padB + order.length * rowH, rowH, padL, padR, padT, padB, dataMax, order, log };
            if (marketView) {   // keep the zoom window valid as data grows; collapse to null at full range
                marketView.min = Math.max(0, Math.min(marketView.min, dataMax - 1));
                marketView.max = Math.min(dataMax, Math.max(marketView.max, marketView.min + 1));
                if (marketView.min <= 0 && marketView.max >= dataMax) marketView = null;
            }
            drawMarket();
            if (!marketWired) wireMarket();
        }
        function drawMarket() {
            const g = marketGeo; if (!g) return;
            const { W, H, rowH, padL, padR, padT, padB, dataMax, order, log } = g;
            const vMin = marketView ? marketView.min : 0, vMax = marketView ? marketView.max : dataMax, span = (vMax - vMin) || 1;
            const X = p => padL + ((p - vMin) / span) * (W - padL - padR);
            const inV = p => p >= vMin - 1e-6 && p <= vMax + 1e-6;
            let s = `<svg class="an-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">`;
            const step = Math.max(1, niceStep(span, 4));
            for (let gg = Math.ceil(vMin / step) * step; gg <= vMax + 1e-6; gg += step) { const xx = X(gg);
                s += `<line class="an-grid" x1="${xx.toFixed(1)}" y1="${padT}" x2="${xx.toFixed(1)}" y2="${H - padB}"/><text class="an-tick" x="${xx.toFixed(1)}" y="${H - padB + 16}" text-anchor="middle">$${gg}</text>`; }
            order.forEach((pos, ri) => {
                const m = MARKET[pos], cy = padT + ri * rowH + rowH / 2;
                const bx1 = X(Math.max(m.min, vMin)), bx2 = X(Math.min(m.max, vMax));   // range bar clamped to view
                if (bx2 > bx1) s += `<line class="an-base" x1="${bx1.toFixed(1)}" y1="${cy}" x2="${bx2.toFixed(1)}" y2="${cy}" style="stroke:${hexA(POSCOLOR[pos], .32)}"/>`;
                s += `<text class="an-rowlbl" x="${padL - 12}" y="${(cy + 4).toFixed(1)}" text-anchor="end" fill="${POSCOLOR[pos]}">${pos}</text>`;
                log.filter(l => l.pos === pos && inV(l.price)).forEach((l, i) => {
                    const jitter = ((i % 5) - 2) * 4.2;
                    const cx = X(l.price).toFixed(1), yy = (cy + jitter).toFixed(1);
                    const z = (l.price - m.md) / (m.sd || 1), isDump = DUMPS.has(l.pickId);
                    const data = `data-n="${esc(l.name)}" data-pos="${pos}" data-pr="${l.price}" data-tm="${esc(l.teamName)}" data-z="${z.toFixed(1)}" data-dump="${isDump ? 1 : ''}"`;
                    s += `<circle class="an-dot ${isDump ? 'an-dump' : ''}" cx="${cx}" cy="${yy}" r="${isDump ? 4.5 : 4}" style="--pc:${POSCOLOR[pos]};fill:${isDump ? 'none' : POSCOLOR[pos]};stroke:${isDump ? POSCOLOR[pos] : 'none'}"/><circle class="an-hit" cx="${cx}" cy="${yy}" r="9" ${data}/>`;
                });
                if (inV(m.md)) {
                    s += `<line class="an-med" x1="${X(m.md).toFixed(1)}" y1="${(cy - 16).toFixed(1)}" x2="${X(m.md).toFixed(1)}" y2="${(cy + 16).toFixed(1)}"/>`;
                    s += `<text class="an-medlbl" x="${X(m.md).toFixed(1)}" y="${(cy - 19).toFixed(1)}" text-anchor="middle">$${m.md}</text>`;
                }
            });
            s += '</svg>';
            const wrap = document.getElementById('market');
            wrap.innerHTML = s;
            wrap.querySelectorAll('.an-hit').forEach(c => {
                c.addEventListener('mouseenter', e => { if (!marketDragging) c.previousElementSibling.classList.add('an-hot'); showMarketTip(e, c); });
                c.addEventListener('mousemove', moveTip);
                c.addEventListener('mouseleave', () => { c.previousElementSibling.classList.remove('an-hot'); hideTip(); });
            });
            updateMarketZoomUI();
        }
        function scheduleDraw() { if (marketRAF) return; marketRAF = requestAnimationFrame(() => { marketRAF = 0; drawMarket(); }); }
        function zoomAround(dollar, factor) {   // factor<1 zooms in (shrinks the window around `dollar`)
            const g = marketGeo; if (!g) return;
            const vMin = marketView ? marketView.min : 0, vMax = marketView ? marketView.max : g.dataMax;
            let nMin = dollar - (dollar - vMin) * factor, nMax = dollar + (vMax - dollar) * factor;
            if (nMax - nMin < 4) return;   // floor the window at $4 wide
            nMin = Math.max(0, nMin); nMax = Math.min(g.dataMax, nMax);
            marketView = (nMin <= 0 && nMax >= g.dataMax) ? null : { min: nMin, max: nMax };
            scheduleDraw();
        }
        function marketZoom(factor) { const g = marketGeo; if (!g) return; const vMin = marketView ? marketView.min : 0, vMax = marketView ? marketView.max : g.dataMax; zoomAround((vMin + vMax) / 2, factor); }
        function marketReset() { marketView = null; drawMarket(); }
        function updateMarketZoomUI() { const r = document.getElementById('mkt-reset'); if (r) r.classList.toggle('active', !!marketView); }
        // Attach pan/zoom to the persistent #market container once (its inner SVG is replaced each draw).
        function wireMarket() {
            const wrap = document.getElementById('market'); marketWired = true;
            const svgX = clientX => {   // screen px → SVG-user x, correct under preserveAspectRatio letterboxing
                const svg = wrap.querySelector('svg'), ctm = svg && svg.getScreenCTM(); if (!ctm) return null;
                const pt = svg.createSVGPoint(); pt.x = clientX; pt.y = 0; return pt.matrixTransform(ctm.inverse()).x;
            };
            const toDollar = sx => { const g = marketGeo, vMin = marketView ? marketView.min : 0, vMax = marketView ? marketView.max : g.dataMax; return vMin + (sx - g.padL) / (g.W - g.padL - g.padR) * (vMax - vMin); };
            wrap.addEventListener('wheel', e => {
                if (!(e.ctrlKey || e.metaKey) || !marketGeo) return;   // plain wheel scrolls the page; modifier zooms
                e.preventDefault();
                const sx = svgX(e.clientX); if (sx != null) zoomAround(toDollar(sx), e.deltaY < 0 ? 0.82 : 1 / 0.82);
            }, { passive: false });
            let down = null;
            wrap.addEventListener('mousedown', e => {
                if (!marketGeo) return;
                marketDragging = false;
                down = { x: e.clientX, view: [marketView ? marketView.min : 0, marketView ? marketView.max : marketGeo.dataMax] };
                wrap.classList.add('grabbing');
            });
            window.addEventListener('mousemove', e => {
                if (!down || !marketGeo) return;
                const sx0 = svgX(down.x), sx1 = svgX(e.clientX); if (sx0 == null || sx1 == null) return;
                const g = marketGeo, [vMin0, vMax0] = down.view, w = vMax0 - vMin0;
                const dxData = (sx1 - sx0) / (g.W - g.padL - g.padR) * w;
                let nMin = vMin0 - dxData, nMax = vMax0 - dxData;
                if (nMin < 0) { nMin = 0; nMax = w; }
                if (nMax > g.dataMax) { nMax = g.dataMax; nMin = g.dataMax - w; }
                if (Math.abs(e.clientX - down.x) > 2) { marketDragging = true; hideTip(); }
                marketView = (nMin <= 0 && nMax >= g.dataMax) ? null : { min: nMin, max: nMax };
                scheduleDraw();
            });
            window.addEventListener('mouseup', () => { if (down) { down = null; wrap.classList.remove('grabbing'); setTimeout(() => { marketDragging = false; }, 0); } });
            wrap.addEventListener('dblclick', () => { marketView = null; drawMarket(); });
        }
        function showMarketTip(e, c) {
            if (marketDragging) return;   // suppress hover while panning
            const tip = document.getElementById('ptip'), pos = c.dataset.pos, pr = +c.dataset.pr;
            const t = valueTier(pos, pr);
            const ctx = c.dataset.dump
                ? `<div class="tt-ctx dump"><b>$${pr}</b> · final-pick budget dump · leftover money</div>`
                : (t ? ctxHTML(pos, pr, t) : `<div class="tt-ctx mid"><b>$${pr}</b></div>`);
            tip.style.setProperty('--pc', POSCOLOR[pos]);
            tip.innerHTML = `<div class="tt-head"><span class="tt-pos ${LIGHTPOS[pos] ? 'light' : ''}" style="background:${POSCOLOR[pos]}">${pos}</span><span class="tt-name">${esc(c.dataset.n)}</span></div>
                <div class="tt-sub">${esc(c.dataset.tm)}</div>${ctx}`;
            tip.style.display = 'block'; moveTip(e);
        }
        function setMatrixMode(m) {
            matrixMode = m;
            document.querySelectorAll('#mxmode button').forEach(b => {
                const on = b.id === 'mx-' + m;
                b.classList.toggle('active', on);
                b.setAttribute('aria-pressed', String(on));
            });
            renderMatrix();
        }
        // Per-team aggregate by position: how many filled, and how many dollars spent.
        function teamPosAgg(t) {
            const count = {}, spend = {};
            rosterFor(t).forEach(p => { count[p.pos] = (count[p.pos] || 0) + 1; spend[p.pos] = (spend[p.pos] || 0) + p.price; });
            return { count, spend };
        }
        function renderMatrix() {
            const order = RADAR_ORDER, dollars = matrixMode === 'dollars';
            const rows = TEAMS.map(t => ({ t, ...teamPosAgg(t) }));
            const maxCell = dollars ? Math.max(1, ...rows.flatMap(r => order.map(pos => r.spend[pos] || 0))) : 1;
            document.getElementById('matrixNote').textContent = dollars ? '$ spent by position · darker = more' : 'filled vs max · gaps glow';
            let html = `<div class="mx-grid" style="grid-template-columns:minmax(96px,1.3fr) repeat(${order.length},1fr)">`;
            html += `<div class="mx-corner"></div>` + order.map(pos => `<div class="mx-h" style="color:${POSCOLOR[pos]}">${pos}${dollars ? '' : `<i>/${POSMAX[pos]}</i>`}</div>`).join('');
            rows.forEach(({ t, count, spend }) => {
                html += `<div class="mx-team"><span class="mx-dot" style="background:${t.color}"></span><span class="nm">${esc(t.team)}</span></div>`;
                order.forEach(pos => {
                    const n = count[pos] || 0, dol = spend[pos] || 0;
                    const val = dollars ? dol : n, max = POSMAX[pos] || 1;
                    const frac = dollars ? dol / maxCell : Math.min(n / max, 1);
                    const full = !dollars && n >= max;
                    const bg = val === 0 ? 'transparent' : `color-mix(in srgb, ${POSCOLOR[pos]} ${Math.round(16 + frac * 64)}%, transparent)`;
                    const cls = 'mx-cell' + (val === 0 ? ' empty' : '') + (full ? ' full' : '');
                    const label = dollars ? (dol ? '$' + dol : '·') : (n || '·');
                    const title = dollars ? `${t.team} · ${pos} $${dol}` : `${t.team} · ${pos} ${n}/${max}`;
                    html += `<div class="${cls}" style="background:${bg}" title="${esc(title)}"><span class="mx-n">${label}</span></div>`;
                });
            });
            html += '</div>';
            document.getElementById('matrix').innerHTML = html;
        }
        function runsInfo(log) {
            let best = { pos: null, len: 0, start: 0, end: 0 }, cur = { pos: null, len: 0, start: 0 };
            log.forEach(l => {
                if (l.pos === cur.pos) cur.len++; else cur = { pos: l.pos, len: 1, start: l.no };
                if (cur.len > best.len) best = { pos: cur.pos, len: cur.len, start: cur.start, end: l.no };
            });
            return best;
        }
        function renderInsights() {
            const box = document.getElementById('insights'), log = buildDraftLog();
            if (log.length < 3) { box.innerHTML = '<div class="an-empty">Trends surface once a handful of players are sold.</div>'; return; }
            const cards = [];
            let splurge = null;
            log.forEach(l => { if (DUMPS.has(l.pickId)) return; const m = MARKET[l.pos]; if (!m || l.price <= 1) return; const over = l.price - m.md; if (!splurge || over > splurge.over) splurge = { ...l, over, md: m.md }; });
            if (splurge) cards.push({ accent: POSCOLOR[splurge.pos], eyebrow: 'Biggest Splurge', val: `$${splurge.price}`, sub: `${esc(splurge.name)} · $${splurge.over} over typical ${splurge.pos} ($${splurge.md})` });
            let topPos = null;
            RADAR_ORDER.forEach(pos => { const m = MARKET[pos]; if (m && (!topPos || m.total > topPos.total)) topPos = { pos, ...m }; });
            if (topPos) cards.push({ accent: POSCOLOR[topPos.pos], eyebrow: 'Where The Money Went', val: topPos.pos, sub: `$${topPos.total} over ${topPos.n} picks · median $${topPos.md}` });
            const run = runsInfo(log);
            if (run.len >= 2) cards.push({ accent: POSCOLOR[run.pos], eyebrow: 'Hottest Run', val: `${run.len}× ${run.pos}`, sub: `picks ${run.start}–${run.end} all went ${run.pos}` });
            let conc = null;
            TEAMS.forEach(t => { const ps = t._picks.filter(p => !DUMPS.has(p.pick_id)).map(p => p.price), spent = ps.reduce((s, v) => s + v, 0); if (spent < 10 || !ps.length) return; const top = Math.max(...ps), share = top / spent; if (!conc || share > conc.share) conc = { team: t.team, share, top, spent }; });
            if (conc) cards.push({ accent: 'var(--gold)', eyebrow: 'Stars & Scrubs', val: `${Math.round(conc.share * 100)}%`, sub: `${esc(conc.team)} — $${conc.top} of $${conc.spent} spent on one player` });
            box.innerHTML = cards.map(c => `<div class="insight" style="--ac:${c.accent}"><div class="in-eyebrow">${c.eyebrow}</div><div class="in-val cond">${c.val}</div><div class="in-sub">${c.sub}</div></div>`).join('');
        }
        function renderTempo() {
            const wrap = document.getElementById('tempo'), log = buildDraftLog();
            if (!log.length) { wrap.innerHTML = '<div class="an-empty">No picks yet.</div>'; return; }
            const W = 760, H = 152, padL = 32, padR = 12, padT = 10, padB = 22;
            const n = log.length, maxP = Math.max(...log.map(l => l.price)), bw = (W - padL - padR) / n, Y0 = H - padB;
            let s = `<svg class="an-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">`;
            s += `<line class="an-axis" x1="${padL}" y1="${Y0}" x2="${W - padR}" y2="${Y0}"/>`;
            log.forEach((l, i) => {
                const h = Math.max(2, (l.price / maxP) * (H - padT - padB)), x = padL + i * bw;
                const data = `data-n="${esc(l.name)}" data-pos="${l.pos}" data-pr="${l.price}" data-tm="${esc(l.teamName)}" data-no="${l.no}"`;
                s += `<rect class="tp-bar" x="${x.toFixed(1)}" y="${(Y0 - h).toFixed(1)}" width="${Math.max(1, bw - 0.7).toFixed(1)}" height="${h.toFixed(1)}" style="fill:${POSCOLOR[l.pos]}"/>`;
                // Full-height hit target so even tiny bars are easy to hover.
                s += `<rect class="tp-hit" x="${x.toFixed(1)}" y="${padT}" width="${bw.toFixed(2)}" height="${(Y0 - padT).toFixed(1)}" ${data}/>`;
            });
            s += '</svg>';
            wrap.innerHTML = s + `<div class="legend">${RADAR_ORDER.map(p => `<span class="lg-item"><span class="lg-dot" style="background:${POSCOLOR[p]}"></span>${p}</span>`).join('')}</div>`;
            wrap.querySelectorAll('.tp-hit').forEach(b => { b.addEventListener('mouseenter', e => showTempoTip(e, b)); b.addEventListener('mousemove', moveTip); b.addEventListener('mouseleave', hideTip); });
        }
        function showTempoTip(e, b) {
            const tip = document.getElementById('ptip'), pos = b.dataset.pos;
            tip.style.setProperty('--pc', POSCOLOR[pos]);
            tip.innerHTML = `<div class="tt-head"><span class="tt-pos ${LIGHTPOS[pos] ? 'light' : ''}" style="background:${POSCOLOR[pos]}">${pos}</span><span class="tt-name">${esc(b.dataset.n)}</span></div>
                <div class="tt-sub">Pick ${b.dataset.no} · ${esc(b.dataset.tm)}</div>
                <div class="tt-ctx mid"><b>$${b.dataset.pr}</b></div>`;
            tip.style.display = 'block'; moveTip(e);
        }
        // Shared player tooltip for the Bargain Board + Draft DNA: pos chip, name, owner,
        // and the price-vs-market read (reuses valueTier/ctxHTML).
        function showCtxTip(e, el) {
            const tip = document.getElementById('ptip'), pos = el.dataset.pos, pr = +el.dataset.pr;
            const t = valueTier(pos, pr);
            const ctx = t ? ctxHTML(pos, pr, t) : `<div class="tt-ctx mid"><b>$${pr}</b></div>`;
            tip.style.setProperty('--pc', POSCOLOR[pos]);
            tip.innerHTML = `<div class="tt-head"><span class="tt-pos ${LIGHTPOS[pos] ? 'light' : ''}" style="background:${POSCOLOR[pos]}">${pos}</span><span class="tt-name">${esc(el.dataset.n)}</span></div>
                <div class="tt-sub">${esc(el.dataset.tm)}</div>${ctx}`;
            tip.style.display = 'block'; moveTip(e);
        }

        /* ── Bargain Board (Task #2): price vs last-season production, ranked WITHIN position ──
           Deterministic + honest. We never claim "value" outright (no projections/ADP exist).
           For each position we percentile-rank price and prior-year production, then surface the
           biggest disagreements. Players with no prior-year line (rookies, D/ST, zero production)
           are excluded — a $1 unknown can't masquerade as a steal. */
        function pctRanker(vals) {                       // midpoint percentile in (0,1); ties-safe
            const n = vals.length;
            return v => { let lt = 0, eq = 0; for (const x of vals) { if (x < v) lt++; else if (x === v) eq++; } return n ? (lt + 0.5 * eq) / n : 0; };
        }
        function bargainData() {
            const POSSET = ['QB', 'RB', 'WR', 'TE'];     // skill spots with a real market + box score
            const byPos = {};
            (lastDraftState ? lastDraftState.teams : []).forEach(t => {
                const tm = TEAMS.find(x => x.owner_id === t.owner_id);
                t.picks.forEach(pk => {
                    const pl = playersById[pk.player_id]; if (!pl || !tm || !POSSET.includes(pl.position)) return;
                    if (DUMPS.has(pk.pick_id)) return;   // leftover-budget dump, not a reach
                    const prod = prodScore({ id: pl.id, pos: pl.position });
                    if (prod <= 0) return;               // no prior-year baseline → no verdict
                    (byPos[pl.position] = byPos[pl.position] || []).push({ id: pl.id, name: `${pl.first_name} ${pl.last_name}`, pos: pl.position, nfl: pl.team, price: pk.price, team: tm.team, prod });
                });
            });
            const flagged = [];
            Object.entries(byPos).forEach(([pos, arr]) => {
                if (arr.length < 4) return;              // ranks too noisy below four rated picks
                const md = MARKET[pos] ? MARKET[pos].md : median(arr.map(a => a.price));
                const pricePct = pctRanker(arr.map(a => a.price)), prodPct = pctRanker(arr.map(a => a.prod));
                const prodRank = {}; [...arr].map((a, i) => ({ i, p: a.prod })).sort((x, y) => y.p - x.p).forEach((o, r) => prodRank[o.i] = r + 1);
                arr.forEach((a, i) => {
                    const div = pricePct(a.price) - prodPct(a.prod);
                    if (Math.abs(div) < 0.25 || Math.abs(a.price - md) < 4) return;   // need rank AND $ gap
                    flagged.push({ ...a, div, md, prodRank: prodRank[i], n: arr.length });
                });
            });
            return {
                under: flagged.filter(f => f.div <= -0.25).sort((a, b) => a.div - b.div),   // cheap vs production
                over: flagged.filter(f => f.div >= 0.25).sort((a, b) => b.div - a.div)       // pricey vs production
            };
        }
        function renderBargain() {
            const wrap = document.getElementById('bargain'), { under, over } = bargainData();
            if (!under.length && !over.length) { wrap.innerHTML = '<div class="an-empty">Bargains surface once at least four players at a position are sold.</div>'; return; }
            const row = (f, kind) => {
                const delta = kind === 'under' ? `$${f.md - f.price} under typical` : `$${f.price - f.md} over typical`;
                return `<div class="bg-row ${kind}" data-n="${esc(f.name)}" data-pos="${f.pos}" data-pr="${f.price}" data-tm="${esc(f.team)}" onmouseenter="showCtxTip(event,this)" onmousemove="moveTip(event)" onmouseleave="hideTip()">
                    <span class="bg-pos" style="background:${POSCOLOR[f.pos]}${LIGHTPOS[f.pos] ? ';color:#fff' : ''}">${f.pos}</span>
                    <span class="bg-main"><span class="bg-nm">${esc(f.name)} <i>${esc(f.nfl)}</i></span><span class="bg-sub">${f.pos}#${f.prodRank} of ${f.n} by ${STATS_YR} production · to ${esc(f.team)}</span></span>
                    <span class="bg-right"><span class="bg-price">$${f.price}</span><span class="bg-delta">${delta}</span></span></div>`;
            };
            const grp = (label, kind, items, empty) => `<div class="bg-group"><div class="bg-glabel ${kind}">${label}</div>${items.length ? items.slice(0, 6).map(f => row(f, kind)).join('') : `<div class="bg-none">${empty}</div>`}</div>`;
            wrap.innerHTML = `<div class="bg-note">Where price and last-season production disagree most — a value buy, or the room knows something the box score doesn't (injury, role, holdout).</div>`
                + grp('Paid under the box score', 'under', under, 'Nothing notably cheap versus last year.')
                + grp('Paid over the box score', 'over', over, "No one paid up beyond last year's line.");
        }

        /* ── Buying Power (Task #3): dollars left × roster spots left ──
           Axes auto-scale to the field, so the $1/slot floor (y = x) becomes a real diagonal as
           budgets shrink late. Height above the floor ≈ the biggest single bid a team can still make. */
        function niceStep(max, target) { const raw = max / target, pow = Math.pow(10, Math.floor(Math.log10(raw || 1))), r = raw / pow, m = r >= 5 ? 5 : r >= 2 ? 2 : 1; return Math.max(1, m * pow); }
        function renderBuying() {
            const wrap = document.getElementById('buying');
            const pts = TEAMS.map((t, i) => ({ i, owner: t.owner, team: t.team, color: t.color, spots: Math.max(0, TOTAL - t.picks), budget: t.budget, mb: t.picks >= TOTAL ? 0 : maxBid(t) }));
            if (!pts.length) { wrap.innerHTML = '<div class="an-empty">No teams yet.</div>'; return; }
            const W = 720, H = 320, padL = 48, padR = 18, padT = 16, padB = 38;
            const maxSpots = Math.max(4, ...pts.map(p => p.spots)), maxBudget = Math.max(20, ...pts.map(p => p.budget));
            const X = s => padL + (s / maxSpots) * (W - padL - padR), Y = b => (H - padB) - (b / maxBudget) * (H - padT - padB);
            let s = `<svg class="an-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">`;
            const xStep = Math.max(1, Math.ceil(maxSpots / 6));
            for (let g = 0; g <= maxSpots; g += xStep) { const xx = X(g); s += `<line class="bp-grid" x1="${xx.toFixed(1)}" y1="${padT}" x2="${xx.toFixed(1)}" y2="${H - padB}"/><text class="bp-tick" x="${xx.toFixed(1)}" y="${H - padB + 15}" text-anchor="middle">${g}</text>`; }
            const yStep = niceStep(maxBudget, 5);
            for (let g = 0; g <= maxBudget; g += yStep) { const yy = Y(g); s += `<line class="bp-grid" x1="${padL}" y1="${yy.toFixed(1)}" x2="${W - padR}" y2="${yy.toFixed(1)}"/><text class="bp-tick" x="${padL - 7}" y="${(yy + 3).toFixed(1)}" text-anchor="end">$${g}</text>`; }
            const fx0 = X(0), fy0 = Y(0), fx1 = X(maxSpots), fy1 = Y(maxSpots);
            s += `<polygon class="bp-infeasible" points="${fx0},${fy0} ${fx1.toFixed(1)},${fy1.toFixed(1)} ${fx1.toFixed(1)},${fy0}"/>`;
            s += `<line class="bp-floor" x1="${fx0}" y1="${fy0}" x2="${fx1.toFixed(1)}" y2="${fy1.toFixed(1)}"/>`;
            s += `<text class="bp-floorlbl" x="${(fx1 - 4).toFixed(1)}" y="${(fy1 - 6).toFixed(1)}" text-anchor="end">min to fill roster · $1/slot</text>`;
            s += `<text class="bp-axlbl" x="${((padL + W - padR) / 2).toFixed(0)}" y="${H - 6}" text-anchor="middle">ROSTER SPOTS LEFT →</text>`;
            s += `<text class="bp-axlbl" transform="translate(12,${(padT + (H - padB - padT) / 2).toFixed(0)}) rotate(-90)" text-anchor="middle">← BUDGET LEFT</text>`;
            pts.forEach(p => {
                const cx = X(p.spots), cy = Y(p.budget), sel = p.i === selected;
                const data = `data-tm="${esc(p.team)}" data-ow="${esc(p.owner)}" data-bu="${p.budget}" data-sp="${p.spots}" data-mb="${p.mb}" data-cl="${p.color}"`;
                s += `<circle class="bp-dot ${sel ? 'sel' : ''}" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="${sel ? 7 : 5.5}" style="fill:${p.color}"/>`;
                s += `<circle class="bp-hit" cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="13" ${data}/>`;
                s += `<text class="bp-lbl ${sel ? 'sel' : ''}" x="${(cx + 9).toFixed(1)}" y="${(cy + 3.5).toFixed(1)}">${esc(p.owner)}</text>`;
            });
            s += '</svg>';
            wrap.innerHTML = s;
            wrap.querySelectorAll('.bp-hit').forEach(c => { c.addEventListener('mouseenter', e => showBuyingTip(e, c)); c.addEventListener('mousemove', moveTip); c.addEventListener('mouseleave', hideTip); });
        }
        function showBuyingTip(e, c) {
            const tip = document.getElementById('ptip');
            tip.style.setProperty('--pc', c.dataset.cl);
            tip.innerHTML = `<div class="tt-head"><span class="tt-name">${esc(c.dataset.tm)}</span></div>
                <div class="tt-sub">${esc(c.dataset.ow)}</div>
                <div class="bp-tt"><span>Budget left</span><b class="tnum">$${c.dataset.bu}</b></div>
                <div class="bp-tt"><span>Spots left</span><b class="tnum">${c.dataset.sp}</b></div>
                <div class="bp-tt"><span>Max single bid</span><b class="tnum gold">$${c.dataset.mb}</b></div>`;
            tip.style.display = 'block'; moveTip(e);
        }

        /* ── Top Buys (Task #4): each team's priciest picks as named, position-colored chips ──
           Ranked by biggest REAL buy (a budget dump never sets the ranking); dump chips are still
           shown but marked + dimmed so leftover-money picks aren't mistaken for a marquee target. */
        function renderTopBuys() {
            const wrap = document.getElementById('topbuys');
            const selOwner = TEAMS[selected] ? TEAMS[selected].owner_id : null;
            const rows = TEAMS.map(t => {
                const picks = t._picks.map(pk => {
                    const pl = playersById[pk.player_id];
                    return pl ? { fn: pl.first_name, ln: pl.last_name, pos: pl.position, nfl: pl.team, price: pk.price, dump: DUMPS.has(pk.pick_id) } : null;
                }).filter(Boolean).sort((a, b) => b.price - a.price);
                const spent = picks.reduce((s, p) => s + p.price, 0);
                const headline = Math.max(0, ...picks.filter(p => !p.dump).map(p => p.price));
                return { t, picks, spent, headline };
            }).filter(r => r.picks.length);
            if (!rows.length) { wrap.innerHTML = '<div class="an-empty">No picks yet — biggest buys appear as players sell.</div>'; return; }
            rows.sort((a, b) => b.headline - a.headline || b.spent - a.spent);
            wrap.innerHTML = rows.map(({ t, picks, spent }) => {
                const chips = picks.slice(0, 3).map(p => {
                    const tag = p.dump ? '<i class="tbuy-tag" title="Final-pick budget dump — leftover money, not a target">dump</i>' : '';
                    return `<span class="tbuy-chip ${p.dump ? 'is-dump' : ''}" style="--pc:${POSCOLOR[p.pos]}" data-n="${esc(p.fn + ' ' + p.ln)}" data-pos="${p.pos}" data-pr="${p.price}" data-tm="${esc(t.team)}" onmouseenter="showCtxTip(event,this)" onmousemove="moveTip(event)" onmouseleave="hideTip()"><span class="tbuy-cpos">${p.pos}</span><span class="tbuy-cnm">${esc(p.ln)}</span><span class="tbuy-cpr">$${p.price}</span>${tag}</span>`;
                }).join('');
                const more = picks.length > 3 ? `<span class="tbuy-more">+${picks.length - 3} more</span>` : '';
                return `<div class="tbuy-row ${t.owner_id === selOwner ? 'sel' : ''}">
                    <span class="tbuy-team"><span class="tbuy-dot" style="background:${t.color}"></span><span class="nm">${esc(t.team)}</span></span>
                    <span class="tbuy-chips">${chips}${more}</span>
                    <span class="tbuy-spent tnum">$${spent}</span></div>`;
            }).join('');
        }

        init();
