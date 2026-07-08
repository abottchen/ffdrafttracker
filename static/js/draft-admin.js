/* draft-admin.js — page-specific JS for the admin console (index.html).

   Loaded as a classic script after draft-shared.js, so shared globals
   (esc, getTeamLogoUrl, teamColor, headshotUrl, budgetClass, boothPersona,
   revealOnReady) are already in scope. Every function here stays a top-level
   global because the template wires them via inline onclick/onerror handlers.

   Server-injected data (config, draft-state version) arrives on window.APP,
   set inline in index.html before this file loads — a static .js can't use
   Jinja2 {{ }} interpolation. */
        // Server-injected (change F): config is authoritative; no hardcoded fallbacks.
        let config = window.APP.config;
        let currentVersion = window.APP.version;
        let players = [];
        let owners = [];
        let playerStats = {};
        let availablePlayerIds = [];
        let currentDraftState = null;
        let selectedPlayerId = null;
        let selectedPlayerName = null;
        let highlightedIndex = -1;
        let nominationTimerInterval = null;
        let nominationStartTime = null;
        let adminSelectedPlayerId = null;
        let adminSelectedPlayerName = null;
        let adminHighlightedIndex = -1;
        let cursorIndex = null;   // keyboard bid cursor: index into draftState.teams

        function openDrawer() {
            document.getElementById('scrim').classList.add('open');
            document.getElementById('drawer').classList.add('open');
            document.getElementById('drawer').setAttribute('aria-hidden', 'false');
        }
        function closeDrawer() {
            document.getElementById('scrim').classList.remove('open');
            document.getElementById('drawer').classList.remove('open');
            document.getElementById('drawer').setAttribute('aria-hidden', 'true');
        }
        document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });

        // esc(), getTeamLogoUrl(), teamColor(), headshotUrl(), budgetClass(),
        // BOOTH_PERSONAS/boothPersona(), revealOnReady() all come from
        // /static/js/draft-shared.js (loaded above) — shared with the team viewer.

        async function loadData() {
            try {
                players = await (await fetch('/api/v1/players')).json();
                try {
                    const statsResp = await fetch('/api/v1/player/stats');
                    if (statsResp.ok) playerStats = await statsResp.json();
                } catch (e) { playerStats = {}; }
                owners = await (await fetch('/api/v1/owners')).json();
                // config already injected; no fetch needed.
                await refreshData();
                setupPlayerSearch();
                setupAdminPlayerSearch();
                populateAdminOwnerSelect();
            } catch (error) {
                showMessage('Error loading data: ' + error.message, 'error');
            }
        }

        async function refreshData() {
            try {
                const draftState = await (await fetch('/api/v1/draft-state')).json();
                currentVersion = draftState.version;
                currentDraftState = draftState;
                availablePlayerIds = draftState.available_player_ids;

                updateNominationPanel(draftState);          // hero active/standby (Task 4/5)
                updateTeams(draftState);                    // rail (Task 3)
                updateDraftProgress(draftState.teams);      // top bar (Task 6)
                updateOnDeck(draftState);                   // nominate-bar hint (Task 5)
                updateTicker(draftState);                   // draft wire (Task 9)
                populateDrawerSelects(draftState);          // drawer selects (Task 8)
            } catch (error) {
                showMessage('Error refreshing data: ' + error.message, 'error');
            }
        }

        function startNominationTimer() {
            nominationStartTime = Date.now();
            if (nominationTimerInterval) clearInterval(nominationTimerInterval);
            const el = document.getElementById('hero-timer');
            const tick = () => {
                const secs = Math.floor((Date.now() - nominationStartTime) / 1000);
                const m = Math.floor(secs / 60), s = secs % 60;
                el.textContent = `${m}:${String(s).padStart(2, '0')}`;
            };
            tick();
            nominationTimerInterval = setInterval(tick, 1000);
        }

        function stopNominationTimer() {
            if (nominationTimerInterval) { clearInterval(nominationTimerInterval); nominationTimerInterval = null; }
            const el = document.getElementById('hero-timer');
            if (el) el.textContent = '0:00';
        }
        
        function updateDraftProgress(teams) {
            const drafted = teams.reduce((n, t) => n + t.picks.length, 0);
            const totalPossible = config.total_rounds * teams.length;
            const pct = totalPossible > 0 ? Math.round(drafted / totalPossible * 100) : 0;
            const fill = document.getElementById('progress-fill');
            fill.style.width = pct + '%';
            fill.style.setProperty('--pct', pct || 1);   // map the amber->green gradient to progress
            document.getElementById('progress-pct').textContent = pct + '%';
        }
        
        // Short, position-appropriate stat suffix for the hero meta line.
        function heroStatLine(playerId, position) {
            const s = playerStats[playerId];
            if (!s) return '';
            if (position === 'QB' && s.passing) return ` · ${s.passing.yards} yds · ${s.passing.tds} TD`;
            if (position === 'RB' && s.rushing) return ` · ${s.rushing.yards} yds · ${s.rushing.tds} TD`;
            if ((position === 'WR' || position === 'TE') && s.receiving) return ` · ${s.receiving.yards} yds · ${s.receiving.tds} TD`;
            if (position === 'K' && s.kicking) return ` · ${s.kicking.points} pts`;
            return s.stats_summary ? ` · ${esc(s.stats_summary)}` : '';   // free text -> escaped
        }

        // Bye week for the nominee. D/ST has no per-player stats row, so derive it from
        // any teammate's bye (parity with the team viewer's defenseBye).
        function playerByeWeek(player) {
            const s = playerStats[player.id];
            if (s && s.bye_week) return s.bye_week;
            for (const id in playerStats) {
                const st = playerStats[id];
                if (st && st.team === player.team && st.bye_week) return st.bye_week;
            }
            return null;
        }

        function updateNominationPanel(draftState) {
            const nominated = draftState.nominated;
            if (nominated) {
                document.body.classList.remove('standby');
                if (!nominationTimerInterval) startNominationTimer();
                const player = players.find(p => p.id === nominated.player_id);
                const bidder = owners.find(o => o.id === nominated.current_bidder_id);
                if (player) {
                    const logo = getTeamLogoUrl(player.team);
                    const heroActive = document.querySelector('.hero.active');
                    if (heroActive) heroActive.style.setProperty('--team-tint', teamColor(player.team));
                    const img = player.position === 'D/ST' ? logo : headshotUrl(player.id);
                    const name = player.position === 'D/ST'
                        ? `${player.first_name} ${player.last_name}`
                        : `${player.last_name}, ${player.first_name}`;
                    document.getElementById('hero-posbadge').textContent = player.position;
                    const photo = document.getElementById('hero-photo-img');
                    photo.style.display = ''; photo.src = img; photo.alt = player.last_name; photo.onerror = function(){ this.style.display='none'; };
                    // Un-hide first: the inline onerror hides the logo on a 404, and the
                    // element is reused for every nominee.
                    const logoEl = document.getElementById('hero-logo');
                    logoEl.style.display = ''; logoEl.src = logo;
                    document.getElementById('hero-name').textContent = name;
                    const bye = playerByeWeek(player);
                    const byeEl = document.getElementById('hero-bye');
                    if (bye) document.getElementById('hero-bye-num').textContent = bye;
                    byeEl.classList.toggle('is-hidden', !bye);
                    document.getElementById('hero-meta').innerHTML =
                        `${esc(player.position)} · <b>${esc(player.team)}</b>${heroStatLine(player.id, player.position)}`;
                    document.getElementById('bid-amt').textContent = `$${nominated.current_bid}`;
                    document.getElementById('bidder-chip').style.background = bidder ? bidder.color : '#8A9BB5';
                    document.getElementById('bidder-nm').textContent = bidder ? bidder.team_name : 'Unknown';
                }
            } else {
                stopNominationTimer();
                updateStandbyHero(draftState);   // Task 5
                document.body.classList.add('standby');
            }
        }

        function updateStandbyHero(draftState) {
            const team = owners.find(o => o.id === draftState.next_to_nominate);
            const color = team ? team.color : '#8A9BB5';
            const nameEl = document.getElementById('standby-name');
            nameEl.textContent = team ? team.team_name : '—';
            nameEl.style.color = color;
            document.getElementById('standby-meta').innerHTML =
                `${team ? esc(team.owner_name) : ''} · <b>awaiting nomination</b>`;
            const sil = document.getElementById('standby-sil');
            sil.querySelectorAll('[fill]').forEach(node => node.setAttribute('fill', color));
        }

        function updateOnDeck(draftState) {
            const onClock = owners.find(o => o.id === draftState.next_to_nominate);
            const upNext = draftState.up_next ? owners.find(o => o.id === draftState.up_next) : null;
            let html = '';
            if (onClock) html = `On the clock: <b>${esc(onClock.team_name)}</b>`;
            if (upNext) html += ` · Up Next <b>${esc(upNext.team_name)}</b>`;
            document.getElementById('ondeck').innerHTML = html;
        }

        function updateTicker(draftState) {
            const ticker = document.getElementById('ticker');
            const crawl = document.getElementById('ticker-crawl');
            // Flatten picks, newest first (pick_id is reliably chronological).
            const picks = [];
            draftState.teams.forEach(t => {
                const o = owners.find(ow => ow.id === t.owner_id);
                t.picks.forEach(pk => {
                    const p = players.find(pl => pl.id === pk.player_id);
                    if (p) picks.push({ id: pk.pick_id,
                        html: `<b>${esc(p.first_name)} ${esc(p.last_name)}</b> (${p.position}) → ${o ? esc(o.team_name) : '?'} <span class="amt">$${pk.price}</span>` });
                });
            });
            picks.sort((a, b) => b.id - a.id);
            const recent = picks.slice(0, 12);
            if (recent.length === 0) {
                crawl.innerHTML = '';
                ticker.classList.add('is-hidden');
                document.getElementById('showWire').style.display = 'none';
                return;
            }
            crawl.innerHTML = recent.map(r => r.html).join('<span class="sep">●</span>');
            // Respect a prior manual hide: only auto-reveal if neither ticker nor pill is showing.
            const pill = document.getElementById('showWire');
            if (ticker.classList.contains('is-hidden') && pill.style.display !== 'block') {
                ticker.classList.remove('is-hidden');
            }
        }

        // ---- Analyst booth chyron (live commentary from /api/v1/comments) ----
        // Persona identity (BOOTH_PERSONAS / boothPersona) lives in draft-shared.js.
        let boothBuffer = [];        // recent comments, ascending seq
        let boothLastSeq = 0;        // watermark
        let boothExpanded = false;

        function boothRow(c) {
            const meta = boothPersona(c.persona);
            const row = document.createElement('div');
            row.className = 'intel-row';
            row.style.setProperty('--pa', meta.accent);
            const mono = document.createElement('span');
            mono.className = 'intel-mono';
            mono.textContent = meta.initials;
            if (meta.img) {
                const img = document.createElement('img');
                img.className = 'intel-av'; img.src = meta.img; img.alt = ''; img.title = meta.fullName;
                img.onerror = () => { img.style.display = 'none'; mono.style.display = 'grid'; };
                row.append(img, mono);
            } else {
                mono.style.display = 'grid';
                row.append(mono);
            }
            const name = document.createElement('span');
            name.className = 'intel-name'; name.textContent = meta.label;
            const text = document.createElement('span');
            text.className = 'intel-text'; text.textContent = c.text;
            row.append(name, text);
            return row;
        }

        function renderBooth() {
            const feed = document.getElementById('intel-feed');
            if (!feed) return;
            // Oldest first, newest at the bottom — chronological top→down.
            const rows = boothExpanded ? boothBuffer.slice(-5) : boothBuffer.slice(-1);
            feed.replaceChildren(...rows.map(boothRow));
        }

        function toggleBooth() {
            boothExpanded = !boothExpanded;
            document.getElementById('intel').classList.toggle('expanded', boothExpanded);
            renderBooth();
        }

        async function pollBooth() {
            try {
                // First load seeds the buffer with the recent tail; after that, only deltas.
                const q = boothLastSeq ? `?since=${boothLastSeq}` : '?limit=8';
                const fresh = await (await fetch(`/api/v1/comments${q}`)).json();
                if (!Array.isArray(fresh) || fresh.length === 0) return;
                boothBuffer.push(...fresh);
                if (boothBuffer.length > 12) boothBuffer = boothBuffer.slice(-12);
                boothLastSeq = boothBuffer[boothBuffer.length - 1].seq;
                const intel = document.getElementById('intel');
                intel.hidden = false;
                renderBooth();
                // Fresh-line glow, then settle.
                intel.classList.remove('flash');
                void intel.offsetWidth;   // restart the animation
                intel.classList.add('flash');
            } catch (e) { /* booth may not be running; stay quiet */ }
        }

        function setupPlayerSearch() {
            const searchInput = document.getElementById('player-search');
            const dropdown = document.getElementById('player-dropdown');
            
            searchInput.addEventListener('input', handlePlayerSearch);
            searchInput.addEventListener('keydown', handleKeyDown);
            
            // Hide dropdown when clicking outside
            document.addEventListener('click', function(e) {
                if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
                    hideDropdown();
                }
            });
        }
        
        function handlePlayerSearch(e) {
            const query = e.target.value.toLowerCase().trim();
            const dropdown = document.getElementById('player-dropdown');
            
            if (query.length === 0) {
                hideDropdown();
                selectedPlayerId = null;
                selectedPlayerName = null;
                return;
            }
            
            // Filter available players by name
            const availablePlayers = players.filter(p => availablePlayerIds.includes(p.id));
            const matchingPlayers = availablePlayers.filter(player => {
                const fullName = `${player.first_name} ${player.last_name}`.toLowerCase();
                return fullName.includes(query);
            });
            
            if (matchingPlayers.length === 0) {
                hideDropdown();
                return;
            }
            
            // Show dropdown with matches (cap at 15 — parity with drawer search)
            dropdown.innerHTML = '';
            matchingPlayers.slice(0, 15).forEach((player, index) => {
                const option = document.createElement('div');
                option.className = 'player-option';
                option.dataset.playerId = player.id;
                option.innerHTML = `<strong>${esc(player.first_name)} ${esc(player.last_name)}</strong> - ${esc(player.position)} (${esc(player.team)})`;
                option.onclick = () => selectPlayerFromDropdown(player);
                dropdown.appendChild(option);
            });
            
            highlightedIndex = -1;
            dropdown.style.display = 'block';
        }
        
        function handleKeyDown(e) {
            const dropdown = document.getElementById('player-dropdown');
            const options = dropdown.querySelectorAll('.player-option');
            
            if (options.length === 0) return;
            
            switch(e.key) {
                case 'ArrowDown':
                    e.preventDefault();
                    highlightedIndex = Math.min(highlightedIndex + 1, options.length - 1);
                    updateHighlight(options);
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    highlightedIndex = Math.max(highlightedIndex - 1, -1);
                    updateHighlight(options);
                    break;
                case 'Enter':
                    e.preventDefault();
                    if (highlightedIndex >= 0 && highlightedIndex < options.length) {
                        const playerId = parseInt(options[highlightedIndex].dataset.playerId);
                        const player = players.find(p => p.id === playerId);
                        if (player) {
                            selectPlayerFromDropdown(player);
                            // Automatically nominate the selected player
                            nominateSelected();
                        }
                    }
                    break;
                case 'Escape':
                    hideDropdown();
                    e.target.blur();
                    break;
            }
        }
        
        function updateHighlight(options) {
            options.forEach((option, index) => {
                option.classList.toggle('highlighted', index === highlightedIndex);
            });
            
            // Auto-scroll the highlighted item into view
            if (highlightedIndex >= 0 && highlightedIndex < options.length) {
                const highlightedOption = options[highlightedIndex];
                const dropdown = document.getElementById('player-dropdown');
                
                // Get the position of the highlighted item relative to the dropdown
                const optionTop = highlightedOption.offsetTop;
                const optionBottom = optionTop + highlightedOption.offsetHeight;
                const dropdownTop = dropdown.scrollTop;
                const dropdownBottom = dropdownTop + dropdown.clientHeight;
                
                // Scroll if the highlighted item is outside the visible area
                if (optionTop < dropdownTop) {
                    // Item is above visible area, scroll up
                    dropdown.scrollTop = optionTop;
                } else if (optionBottom > dropdownBottom) {
                    // Item is below visible area, scroll down
                    dropdown.scrollTop = optionBottom - dropdown.clientHeight;
                }
            }
        }
        
        function selectPlayerFromDropdown(player) {
            selectedPlayerId = player.id;
            selectedPlayerName = `${player.first_name} ${player.last_name}`;
            document.getElementById('player-search').value = selectedPlayerName;
            hideDropdown();
        }
        
        function hideDropdown() {
            document.getElementById('player-dropdown').style.display = 'none';
            highlightedIndex = -1;
        }

        function teamPositionCount(team, position) {
            return team.picks.reduce((n, pick) => {
                const p = players.find(pl => pl.id === pick.player_id);
                return n + (p && p.position === position ? 1 : 0);
            }, 0);
        }
        function nominatedPosition(draftState) {
            if (!draftState.nominated) return null;
            const p = players.find(pl => pl.id === draftState.nominated.player_id);
            return p ? p.position : null;
        }
        // Can this team legally bid `amount` on the current nominee? (parity with
        // backend + updateBidButtonState): not done, within budget, within roster-safe
        // max bid, and not already at the position maximum for the nominee.
        function canTeamBid(team, amount, nomPos) {
            if (team.manually_done || team.picks.length >= config.total_rounds) return false;
            const maxBid = (team.max_bid === null || team.max_bid === undefined) ? -1 : team.max_bid;
            if (amount > team.budget_remaining) return false;
            if (amount > maxBid) return false;
            if (nomPos && config.position_maximums[nomPos] !== undefined) {
                if (teamPositionCount(team, nomPos) >= config.position_maximums[nomPos]) return false;
            }
            return true;
        }

        // Valid bid (parity with backend): min next bid <= amount <= max_bid (roster-safe
        // budget reservation), amount <= budget, and team not at position max for nominee.
        function updateBidButtonState(team, nextBid, nomPos, inp, btn) {
            const amt = parseInt(inp.value) || 0;
            const maxBid = (team.max_bid === null || team.max_bid === undefined) ? -1 : team.max_bid;
            const meetsMin = amt >= nextBid;
            const withinBudget = amt <= team.budget_remaining;
            const withinMax = amt <= maxBid;
            let posOk = true;
            if (nomPos && config.position_maximums[nomPos] !== undefined) {
                posOk = teamPositionCount(team, nomPos) < config.position_maximums[nomPos];
            }
            const valid = meetsMin && withinBudget && withinMax && posOk;
            btn.disabled = !valid;
            inp.classList.toggle('over-max', amt > maxBid);
            btn.title = !posOk ? `At position maximum for ${nomPos}`
                : (!withinMax && meetsMin && withinBudget) ? 'Bid would prevent completing roster' : '';
        }

        function updateTeams(draftState) {
            // Don't rebuild the rail while the operator is typing a manual bid — a rebuild
            // would blow away the focused box and their keystrokes would fall through to
            // team-selection. The rail refreshes on commit (we blur first) or next poll.
            const ae = document.activeElement;
            if (ae && ae.closest && ae.closest('.bidctl')) return;

            const teams = draftState.teams;
            const nominated = draftState.nominated;
            const rail = document.getElementById('rail');
            rail.innerHTML = '';

            const nextBid = nominated ? nominated.current_bid + 1 : config.min_bid;
            const nomPos = nominatedPosition(draftState);

            // Keep the keyboard cursor on an eligible team (or the first one).
            if (nominated) {
                const eligible = teams.map((t, i) => canTeamBid(t, nextBid, nomPos) ? i : -1).filter(i => i >= 0);
                if (!eligible.length) cursorIndex = null;
                else if (cursorIndex === null || !eligible.includes(cursorIndex)) cursorIndex = eligible[0];
            } else {
                cursorIndex = null;
            }

            teams.forEach((team, idx) => {
                const owner = owners.find(o => o.id === team.owner_id);
                const color = owner ? owner.color : '#8A9BB5';
                const total = config.total_rounds;
                const isRosterFull = team.picks.length >= total;
                const isDone = team.manually_done || isRosterFull;
                const isHigh = nominated && nominated.current_bidder_id === team.owner_id;
                const isClock = team.owner_id === draftState.next_to_nominate && !isDone;
                const canBid = nominated ? canTeamBid(team, nextBid, nomPos) : false;
                const hk = idx < 9 ? String(idx + 1) : (idx === 9 ? '0' : '');

                const pct = Math.round(team.picks.length / total * 100);
                const budgetPct = Math.round(team.budget_remaining / config.initial_budget * 100);
                const bcls = budgetClass(team.budget_remaining, config.initial_budget);
                const maxBid = team.max_bid;  // server: int | null
                const maxEl = (maxBid === null || maxBid === undefined)
                    ? '<span class="v max">—</span>'
                    : `<span class="v max tnum">$${maxBid}</span>`;

                let plateCls = 'plate';
                if (isClock) plateCls += ' is-clock';
                else if (isHigh) plateCls += ' is-high';
                if (isDone) plateCls += ' is-done';
                if (nominated && idx === cursorIndex) plateCls += ' is-cursor';
                if (nominated && !isDone && !canBid) plateCls += ' is-blocked';

                const statusEl = isDone ? '<span class="status done">Done</span>'
                    : isClock ? '<span class="status clock">On the Clock</span>'
                    : isHigh ? '<span class="status high">High Bid</span>' : '';

                // Bid control only when there is an active nomination and team isn't done.
                let bidEl = '';
                if (nominated && !isDone) {
                    bidEl = `<div class="bidctl" data-owner="${team.owner_id}">
                        <input class="tnum" id="bid-input-${team.owner_id}" value="${nextBid}" inputmode="numeric">
                        <button onclick="placeBidForOwner(${team.owner_id})">Bid</button>
                    </div>`;
                }

                rail.insertAdjacentHTML('beforeend', `
                    <div class="${plateCls}" id="plate-${team.owner_id}" style="--tc:${color}">
                        <div class="plate-top">
                            ${statusEl}
                            ${hk ? `<span class="hotkey" title="Press ${hk} to select this team">${hk}</span>` : ''}
                        </div>
                        <span class="tname">${owner ? esc(owner.team_name) : 'Unknown Team'}</span>
                        <span class="owner">${owner ? esc(owner.owner_name) : 'Unknown'}</span>
                        <span class="spacer"></span>
                        <div class="stat-row">
                            <div class="stat"><span class="k">Budget</span><span class="v money ${bcls} tnum">$${team.budget_remaining}</span></div>
                            <div class="stat right"><span class="k">Max Bid</span>${maxEl}</div>
                        </div>
                        <div class="budget-meter ${bcls}"><div class="fill" style="width:${budgetPct}%"></div></div>
                        <div class="picks-line">
                            <div class="picks-fill" style="width:${pct}%;--pct:${pct || 1}"></div>
                            <div class="picks-lbl"><span class="k">Picks</span><span class="v tnum">${team.picks.length}<span class="of">/${total}</span></span></div>
                        </div>
                        ${bidEl}
                    </div>`);
            });

            // Wire bid controls (validate, click-to-focus, Enter-to-submit) — parity.
            if (nominated) {
                teams.forEach(team => {
                    const plate = document.getElementById(`plate-${team.owner_id}`);
                    const ctl = plate ? plate.querySelector('.bidctl') : null;
                    if (!ctl) return;
                    const inp = ctl.querySelector('input');
                    const btn = ctl.querySelector('button');
                    if (team.owner_id === (nominated && nominated.current_bidder_id)) {
                        plate.classList.add('is-high');
                    }
                    const revalidate = () => updateBidButtonState(team, nextBid, nomPos, inp, btn);
                    inp.addEventListener('input', revalidate);
                    inp.addEventListener('keydown', e => {
                        if (e.key === 'Enter') { e.preventDefault(); if (!btn.disabled) placeBidForOwner(team.owner_id); return; }
                        // ↑/↓ nudge the manual bid by $1; never below current_bid + 1 (nextBid).
                        if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
                            e.preventDefault();
                            let v = parseInt(inp.value) || nextBid;
                            v += (e.key === 'ArrowUp') ? 1 : -1;
                            if (v < nextBid) v = nextBid;
                            inp.value = v;
                            revalidate();
                        }
                    });
                    plate.addEventListener('click', e => {
                        if (e.target.closest('button') || e.target.closest('input')) return;
                        cursorIndex = teams.indexOf(team);
                        applyCursor();
                        inp.focus(); inp.select();
                    });
                    revalidate();
                });
                // Keyboard-first: no auto-focus. Number keys select; Enter bids +1; the
                // cursor highlights the team Enter/↑ act on (re-applied after each re-render).
                applyCursor();
            }
        }

        async function nominateSelected() {
            if (!selectedPlayerId) {
                showMessage('Please select a player to nominate', 'error');
                return;
            }
            
            const bid = parseInt(document.getElementById('nomination-bid').value);
            if (!bid || bid < 1) {
                showMessage('Please enter a valid bid amount', 'error');
                return;
            }

            // Client-side max-bid guard: reject bids above the nominator's
            // legal maximum before hitting the server (parity with
            // updateBidButtonState / canTeamBid for the bidding rail).
            if (currentDraftState) {
                const nominatorTeam = currentDraftState.teams.find(
                    t => t.owner_id === currentDraftState.next_to_nominate
                );
                if (nominatorTeam) {
                    const maxBid = (nominatorTeam.max_bid === null || nominatorTeam.max_bid === undefined)
                        ? nominatorTeam.budget_remaining : nominatorTeam.max_bid;
                    const teamName = (owners.find(o => o.id === nominatorTeam.owner_id) || {}).team_name || 'team';
                    if (bid > nominatorTeam.budget_remaining) {
                        showMessage(`Bid $${bid} exceeds ${teamName}'s budget of $${nominatorTeam.budget_remaining}`, 'error');
                        return;
                    }
                    if (bid > maxBid) {
                        showMessage(`Bid $${bid} exceeds ${teamName}'s max bid of $${maxBid}`, 'error');
                        return;
                    }
                }
            }

            try {
                const response = await fetch('/api/v1/nominate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        owner_id: currentDraftState ? currentDraftState.next_to_nominate : 1,
                        player_id: selectedPlayerId,
                        initial_bid: bid,
                        expected_version: currentVersion
                    })
                });
                
                if (response.ok) {
                    const result = await response.json();
                    showMessage('Player nominated successfully!', 'success');
                    currentVersion = result.new_version;
                    await refreshData();
                    document.getElementById('nomination-bid').value = '1';
                    document.getElementById('player-search').value = '';
                    document.getElementById('player-search').blur();   // hand off to the bid console
                    selectedPlayerId = null;
                    selectedPlayerName = null;
                } else {
                    const error = await response.json();
                    showMessage('Nomination failed: ' + error.detail, 'error');
                }
            } catch (error) {
                showMessage('Error nominating player: ' + error.message, 'error');
            }
        }

        async function placeBidForOwner(ownerId, amountOverride) {
            // amountOverride is set for the Enter "+1" bid; otherwise read the box (manual bid).
            const ae = document.activeElement;   // capture before the await for the blur below
            const bid = (amountOverride !== undefined && amountOverride !== null)
                ? amountOverride
                : parseInt(document.getElementById(`bid-input-${ownerId}`).value);
            if (!bid) {
                showMessage('Please enter a bid amount', 'error');
                return;
            }

            try {
                const response = await fetch('/api/v1/bid', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        owner_id: ownerId,
                        bid_amount: bid,
                        expected_version: currentVersion
                    })
                });

                if (response.ok) {
                    const result = await response.json();
                    showMessage('Bid placed successfully!', 'success');
                    currentVersion = result.new_version;
                    // Blur the manual-bid box (if any) so the rail can rebuild post-commit.
                    if (ae && ae.closest && ae.closest('.bidctl')) ae.blur();
                    await refreshData();
                    flashBid(ownerId);   // confirm the bid landed (no modal — speed)
                } else {
                    const error = await response.json();
                    showMessage('Bid failed: ' + error.detail, 'error');
                }
            } catch (error) {
                showMessage('Error placing bid: ' + error.message, 'error');
            }
        }

        // ---------- Bid console: keyboard-driven live bidding ----------
        // Highlight the team the cursor is on (Enter/↑ act on it). Re-applied after
        // every rail re-render since updateTeams() rebuilds the plates.
        function applyCursor() {
            document.querySelectorAll('.plate.is-cursor').forEach(p => p.classList.remove('is-cursor'));
            if (cursorIndex === null || !currentDraftState || !currentDraftState.nominated) return;
            const team = currentDraftState.teams[cursorIndex];
            if (!team) return;
            const plate = document.getElementById(`plate-${team.owner_id}`);
            if (plate) plate.classList.add('is-cursor');
        }

        function flashBid(ownerId) {
            const plate = document.getElementById(`plate-${ownerId}`);
            if (!plate) return;
            plate.classList.add('bid-flash');
            setTimeout(() => plate.classList.remove('bid-flash'), 550);
        }
        function flashBlocked(ownerId) {
            const plate = document.getElementById(`plate-${ownerId}`);
            if (!plate) return;
            plate.classList.add('blocked-flash');
            setTimeout(() => plate.classList.remove('blocked-flash'), 380);
        }

        // Pull a 0–9 digit from a key event (top row OR numpad, shifted or not).
        function digitFromEvent(e) {
            if (/^(Digit|Numpad)\d$/.test(e.code)) return parseInt(e.code.slice(-1), 10);
            if (/^\d$/.test(e.key)) return parseInt(e.key, 10);
            return null;
        }
        // Keys 1–9 map to teams 1–9; key 0 maps to the 10th team.
        function indexForDigit(d, teamCount) {
            const idx = (d === 0) ? 9 : d - 1;
            return idx < teamCount ? idx : -1;
        }

        function moveCursor(dir) {
            const ds = currentDraftState;
            if (!ds || !ds.nominated) return;
            const nextBid = ds.nominated.current_bid + 1;
            const nomPos = nominatedPosition(ds);
            const eligible = ds.teams.map((t, i) => canTeamBid(t, nextBid, nomPos) ? i : -1).filter(i => i >= 0);
            if (!eligible.length) return;
            let pos = eligible.indexOf(cursorIndex);
            pos = (pos === -1) ? 0 : (pos + dir + eligible.length) % eligible.length;
            cursorIndex = eligible[pos];
            applyCursor();
        }

        // Number keys move the cursor to a team (no bid). Enter then bids +1.
        function selectCursor(index) {
            const ds = currentDraftState;
            if (!ds || !ds.nominated || index < 0 || index >= ds.teams.length) return;
            cursorIndex = index;
            applyCursor();
        }

        // Open the selected team's box to type a manual (jump) bid — via ↑ or click.
        // The box takes focus, so number-select is suspended until Enter/Esc returns to nav.
        function focusBidBox(index) {
            const ds = currentDraftState;
            if (!ds || !ds.nominated) return;
            const team = ds.teams[index];
            if (!team) return;
            cursorIndex = index;
            applyCursor();
            const inp = document.getElementById(`bid-input-${team.owner_id}`);
            if (inp) { inp.focus(); inp.select(); }
        }

        // Place a +1 bid for the selected team (Enter on the cursor team).
        function quickBidIndex(index) {
            const ds = currentDraftState;
            if (!ds || !ds.nominated) return;
            const team = ds.teams[index];
            if (!team) return;
            const nextBid = ds.nominated.current_bid + 1;
            const nomPos = nominatedPosition(ds);
            if (!canTeamBid(team, nextBid, nomPos)) { flashBlocked(team.owner_id); return; }
            cursorIndex = index;
            applyCursor();
            placeBidForOwner(team.owner_id, nextBid);
        }

        function handleConsoleKey(e) {
            if (document.getElementById('drawer').classList.contains('open')) return;
            const ae = document.activeElement;
            const typing = ae && (ae.tagName === 'INPUT' || ae.tagName === 'SELECT' || ae.tagName === 'TEXTAREA' || ae.isContentEditable);
            if (typing) {
                // Escape leaves a bid box and returns to keyboard-nav mode.
                if (e.key === 'Escape' && ae.closest && ae.closest('.bidctl')) { ae.blur(); e.preventDefault(); }
                return;
            }
            // 'N' jumps to the nominate search in any state.
            if (e.key === 'n' || e.key === 'N') { e.preventDefault(); document.getElementById('player-search').focus(); return; }

            const ds = currentDraftState;
            if (!ds || !ds.nominated) return;   // bidding keys only during a live auction

            // 'D' drafts the nominee to the current high bidder.
            if (e.key === 'd' || e.key === 'D') { e.preventDefault(); completeDraft(); return; }

            const digit = digitFromEvent(e);
            if (digit !== null) {
                const idx = indexForDigit(digit, ds.teams.length);
                if (idx < 0) return;
                e.preventDefault();
                selectCursor(idx);   // number selects the team; Enter then bids +1
                return;
            }
            switch (e.key) {
                case 'ArrowRight': e.preventDefault(); moveCursor(1); break;
                case 'ArrowLeft':  e.preventDefault(); moveCursor(-1); break;
                case 'ArrowUp':    e.preventDefault(); if (cursorIndex !== null) focusBidBox(cursorIndex); break;
                case 'Enter':      e.preventDefault(); if (cursorIndex !== null) quickBidIndex(cursorIndex); break;
                case 'Escape':     cursorIndex = null; applyCursor(); break;
            }
        }
        document.addEventListener('keydown', handleConsoleKey);

        async function completeDraft() {
            try {
                const draftState = await (await fetch('/api/v1/draft-state')).json();
                if (!draftState.nominated) {
                    showMessage('No player nominated', 'error');
                    return;
                }
                // Sync module-level state with the fresh fetch so the version
                // we send matches the data we read (prevents spurious 409s).
                currentVersion = draftState.version;
                currentDraftState = draftState;

                const response = await fetch('/api/v1/draft', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        owner_id: draftState.nominated.current_bidder_id,
                        player_id: draftState.nominated.player_id,
                        final_price: draftState.nominated.current_bid,
                        expected_version: draftState.version
                    })
                });
                
                if (response.ok) {
                    const result = await response.json();
                    showMessage('Player drafted successfully!', 'success');
                    currentVersion = result.new_version;
                    await refreshData();
                } else {
                    const error = await response.json();
                    showMessage('Draft failed: ' + error.detail, 'error');
                }
            } catch (error) {
                showMessage('Error completing draft: ' + error.message, 'error');
            }
        }

        async function cancelNomination() {
            try {
                const response = await fetch('/api/v1/nominate', {
                    method: 'DELETE',
                    headers: { 
                        'Content-Type': 'application/json',
                        'If-Match': `"${currentVersion}"`
                    }
                });
                
                if (response.ok) {
                    const result = await response.json();
                    showMessage('Nomination cancelled', 'success');
                    currentVersion = result.new_version;
                    await refreshData();
                } else {
                    const error = await response.json();
                    showMessage('Cancel failed: ' + error.detail, 'error');
                }
            } catch (error) {
                showMessage('Error cancelling nomination: ' + error.message, 'error');
            }
        }

        function setTickerSpeed(s) {
            document.documentElement.style.setProperty('--ticker-speed', s);
            localStorage.setItem('tickerSpeed', s);
            document.querySelectorAll('#ticker-speed-row [data-speed]').forEach(b => {
                b.classList.toggle('ghost', b.dataset.speed !== s);
            });
        }
        setTickerSpeed(localStorage.getItem('tickerSpeed') || '26s');

        (function setupResetHold() {
            const btn = document.getElementById('reset-btn');
            let timer = null, start = 0;
            const HOLD = 1200;
            const cancel = () => {
                if (timer) { clearInterval(timer); timer = null; }
                btn.classList.remove('holding'); btn.style.removeProperty('--hold');
            };
            const begin = () => {
                start = Date.now();
                btn.classList.add('holding');
                timer = setInterval(() => {
                    const pct = Math.min(100, (Date.now() - start) / HOLD * 100);
                    btn.style.setProperty('--hold', pct + '%');
                    if (pct >= 100) { cancel(); doReset(); }
                }, 40);
            };
            btn.addEventListener('mousedown', begin);
            btn.addEventListener('touchstart', e => { e.preventDefault(); begin(); });
            ['mouseup', 'mouseleave', 'touchend', 'touchcancel'].forEach(ev => btn.addEventListener(ev, cancel));
        })();

        async function doReset() {
            try {
                const resp = await fetch('/api/v1/reset', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ force: true })
                });
                if (resp.ok) { showMessage('Draft reset', 'success'); closeDrawer(); await refreshData(); }
                else { const e = await resp.json(); showMessage('Reset failed: ' + e.detail, 'error'); }
            } catch (err) { showMessage('Error resetting: ' + err.message, 'error'); }
        }

        function showMessage(text, type) {
            const el = document.getElementById('message');
            el.textContent = text;
            el.className = 'toast show ' + (type || '');
            clearTimeout(el._t);
            el._t = setTimeout(() => { el.className = 'toast ' + (type || ''); }, 4000);
        }

        function populateDrawerSelects(draftState) {
            const teams = draftState.teams;
            // Mark-done: teams not already done
            const doneSel = document.getElementById('done-select');
            doneSel.innerHTML = '<option value="">Select team…</option>';
            teams.forEach(t => {
                const o = owners.find(ow => ow.id === t.owner_id);
                if (o && !t.manually_done) doneSel.insertAdjacentHTML('beforeend', `<option value="${t.owner_id}">${esc(o.team_name)}</option>`);
            });
            // Transfer target: all teams
            const transferSel = document.getElementById('transfer-select');
            transferSel.innerHTML = '<option value="">Transfer to…</option>';
            teams.forEach(t => {
                const o = owners.find(ow => ow.id === t.owner_id);
                if (o) transferSel.insertAdjacentHTML('beforeend', `<option value="${t.owner_id}">${esc(o.team_name)}</option>`);
            });
            // Remove/Transfer source: every drafted pick, sorted by last name
            const removeSel = document.getElementById('remove-select');
            removeSel.innerHTML = '<option value="">Select drafted player…</option>';
            const picks = [];
            teams.forEach(t => {
                const o = owners.find(ow => ow.id === t.owner_id);
                t.picks.forEach(pk => {
                    const p = players.find(pl => pl.id === pk.player_id);
                    if (p) picks.push({ pickId: pk.pick_id, playerId: pk.player_id, price: pk.price,
                        label: `${p.last_name}, ${p.first_name} · ${o ? o.team_name : '?'} ($${pk.price})` });
                });
            });
            picks.sort((a, b) => a.label.localeCompare(b.label));   // sort on the raw label, escape at render
            picks.forEach(pk => removeSel.insertAdjacentHTML('beforeend',
                `<option value="${pk.pickId}" data-player="${pk.playerId}" data-price="${pk.price}">${esc(pk.label)}</option>`));
        }

        async function markTeamDone() {
            const ownerId = parseInt(document.getElementById('done-select').value);
            if (!ownerId) { showMessage('Please select a team first', 'error'); return; }
            await patchTeamDone(ownerId, true);
        }
        async function clearDoneTeams() {
            // Clear every currently-done team (server is the source of truth).
            const done = currentDraftState.teams.filter(t => t.manually_done);
            let ok = true;
            for (const t of done) { ok = (await patchTeamDone(t.owner_id, false)) && ok; }
            if (ok) showMessage('All done teams cleared', 'success');
        }
        async function patchTeamDone(ownerId, value) {
            try {
                const resp = await fetch(`/api/v1/teams/${ownerId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ manually_done: value, expected_version: currentVersion })
                });
                if (resp.ok) {
                    const r = await resp.json();
                    currentVersion = r.new_version;
                    if (value) showMessage('Team marked done', 'success');
                    await refreshData();
                    return true;
                } else {
                    const e = await resp.json();
                    showMessage('Update failed: ' + e.detail, 'error');
                    return false;
                }
            } catch (err) { showMessage('Error: ' + err.message, 'error'); return false; }
        }

        async function removeDraftedPlayer() {
            const sel = document.getElementById('remove-select');
            const pickId = parseInt(sel.value);
            if (!pickId) { showMessage('Please select a player to remove', 'error'); return; }
            try {
                const resp = await fetch(`/api/v1/draft/${pickId}`, {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json', 'If-Match': `"${currentVersion}"` }
                });
                if (resp.ok) { const r = await resp.json(); currentVersion = r.new_version; showMessage('Player removed', 'success'); await refreshData(); }
                else { const e = await resp.json(); showMessage('Remove failed: ' + e.detail, 'error'); }
            } catch (err) { showMessage('Error removing: ' + err.message, 'error'); }
        }

        // Atomic pick transfer via single server-side endpoint.
        async function transferSelectedPick() {
            const sel = document.getElementById('remove-select');
            const opt = sel.options[sel.selectedIndex];
            const pickId = parseInt(sel.value);
            const targetOwnerId = parseInt(document.getElementById('transfer-select').value);
            if (!pickId || !targetOwnerId) { showMessage('Select a player and a target team', 'error'); return; }
            const price = parseInt(opt.dataset.price);
            if (isNaN(price)) { showMessage('Unable to parse pick price — aborting transfer', 'error'); return; }
            try {
                const resp = await fetch('/api/v1/admin/transfer', {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ pick_id: pickId, to_owner_id: targetOwnerId, expected_version: currentVersion })
                });
                if (resp.ok) { currentVersion = (await resp.json()).new_version; showMessage('Player transferred', 'success'); await refreshData(); }
                else { const e = await resp.json(); showMessage('Transfer failed: ' + e.detail, 'error'); }
            } catch (err) { showMessage('Error transferring: ' + err.message, 'error'); }
        }

        // Admin draft functionality
        function setupAdminPlayerSearch() {
            const searchInput = document.getElementById('admin-player-search');
            const dropdown = document.getElementById('admin-player-dropdown');
            
            searchInput.addEventListener('input', function(e) {
                const searchTerm = e.target.value.toLowerCase();
                if (searchTerm.length === 0) {
                    dropdown.style.display = 'none';
                    return;
                }
                
                const availablePlayers = players.filter(player => 
                    availablePlayerIds.includes(player.id)
                );
                
                const filteredPlayers = availablePlayers.filter(player =>
                    `${player.first_name} ${player.last_name}`.toLowerCase().includes(searchTerm) ||
                    player.team.toLowerCase().includes(searchTerm) ||
                    player.position.toLowerCase().includes(searchTerm)
                ).slice(0, 10);
                
                if (filteredPlayers.length === 0) {
                    dropdown.style.display = 'none';
                    return;
                }
                
                dropdown.innerHTML = '';
                filteredPlayers.forEach((player, index) => {
                    const option = document.createElement('div');
                    option.className = `player-option ${index === adminHighlightedIndex ? 'highlighted' : ''}`;
                    option.dataset.index = index;
                    option.innerHTML = `
                        <div class="player-name">${esc(player.first_name)} ${esc(player.last_name)}</div>
                        <div class="player-meta">${esc(player.position)} - ${esc(player.team)}</div>
                    `;
                    option.onclick = () => selectAdminPlayer(player.id, `${player.first_name} ${player.last_name}`);
                    dropdown.appendChild(option);
                });
                dropdown.style.display = 'block';
            });
            
            // Handle keyboard navigation
            searchInput.addEventListener('keydown', function(e) {
                const options = dropdown.querySelectorAll('.player-option');
                if (options.length === 0) return;
                
                if (e.key === 'ArrowDown') {
                    e.preventDefault();
                    adminHighlightedIndex = Math.min(adminHighlightedIndex + 1, options.length - 1);
                    updateAdminHighlight();
                } else if (e.key === 'ArrowUp') {
                    e.preventDefault();
                    adminHighlightedIndex = Math.max(adminHighlightedIndex - 1, -1);
                    updateAdminHighlight();
                } else if (e.key === 'Enter' && adminHighlightedIndex >= 0) {
                    e.preventDefault();
                    const selectedOption = options[adminHighlightedIndex];
                    selectedOption.click();
                } else if (e.key === 'Escape') {
                    dropdown.style.display = 'none';
                    adminHighlightedIndex = -1;
                }
            });
            
            // Hide dropdown when clicking outside
            document.addEventListener('click', function(e) {
                if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
                    dropdown.style.display = 'none';
                    adminHighlightedIndex = -1;
                }
            });
        }
        
        function updateAdminHighlight() {
            const options = document.querySelectorAll('#admin-player-dropdown .player-option');
            options.forEach((option, index) => {
                option.classList.toggle('highlighted', index === adminHighlightedIndex);
            });
        }
        
        function selectAdminPlayer(playerId, playerName) {
            adminSelectedPlayerId = playerId;
            adminSelectedPlayerName = playerName;
            document.getElementById('admin-player-search').value = playerName;
            document.getElementById('admin-player-dropdown').style.display = 'none';
            adminHighlightedIndex = -1;
        }
        
        function populateAdminOwnerSelect() {
            const select = document.getElementById('admin-owner-select');
            select.innerHTML = '<option value="">Select owner...</option>';
            
            owners.forEach(owner => {
                const option = document.createElement('option');
                option.value = owner.id;
                option.textContent = owner.team_name;
                select.appendChild(option);
            });
        }
        
        async function adminDraftPlayer() {
            const ownerId = parseInt(document.getElementById('admin-owner-select').value);
            const price = parseInt(document.getElementById('admin-price-input').value);
            
            if (!adminSelectedPlayerId) {
                showMessage('Please select a player', 'error');
                return;
            }
            
            if (!ownerId) {
                showMessage('Please select an owner', 'error');
                return;
            }
            
            if (!price || price <= 0) {
                showMessage('Please enter a valid price', 'error');
                return;
            }
            
            try {
                const response = await fetch('/api/v1/admin/draft', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        owner_id: ownerId,
                        player_id: adminSelectedPlayerId,
                        price: price,
                        expected_version: currentVersion
                    })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    currentVersion = data.new_version;
                    
                    // Save player name for success message before clearing
                    const draftedPlayerName = adminSelectedPlayerName;
                    
                    // Clear the form
                    document.getElementById('admin-player-search').value = '';
                    document.getElementById('admin-owner-select').value = '';
                    document.getElementById('admin-price-input').value = '';
                    adminSelectedPlayerId = null;
                    adminSelectedPlayerName = null;
                    
                    showMessage(`Successfully drafted ${draftedPlayerName} for $${price}`, 'success');
                    
                    // Refresh data - this updates all UI components
                    console.log('Admin draft successful, refreshing data...');
                    await refreshData();
                    console.log('Data refresh complete');
                } else {
                    const errorData = await response.json();
                    if (response.status === 409) {
                        // Version mismatch, refresh and retry
                        await refreshData();
                        showMessage('Draft state changed, please try again', 'error');
                    } else {
                        showMessage(`Failed to draft player: ${errorData.detail}`, 'error');
                    }
                }
            } catch (error) {
                console.error('Error drafting player:', error);
                showMessage('Failed to draft player', 'error');
            }
        }

        // FOUT guard: reveal once webfonts are ready (--hu/cqw layout depends on metrics).
        revealOnReady(document.getElementById('stage'));

        // Hero height unit: --hu = 1% of the hero's rendered height, so calc(N*var(--hu))
        // in the CSS behaves like the old Ncqh — but works in Firefox, where cqh on a
        // size-container flex layout mis-resolves to min-height and squishes the photo.
        const heroSizer = new ResizeObserver(entries => {
            for (const entry of entries) {
                entry.target.style.setProperty('--hu', (entry.contentRect.height / 100) + 'px');
            }
        });
        document.querySelectorAll('.hero').forEach(hero => heroSizer.observe(hero));

        // Keyboard access for the booth chyron (role="button").
        document.getElementById('intel').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggleBooth(); }
        });

        loadData();
        setInterval(refreshData, 30000);
        pollBooth();
        setInterval(pollBooth, 5000);
