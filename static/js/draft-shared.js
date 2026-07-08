/* draft-shared.js — code shared by the admin console (index.html) and the
   read-only team viewer (team_viewer.html).

   Loaded as a classic script before each template's inline <script>, so every
   declaration below is a plain global. Nothing here may be re-declared inline:
   a top-level `const` in one script and another in a second script share the
   global lexical environment and collide with a SyntaxError.

   These constructs used to be copy-pasted into both templates and had already
   drifted apart (Washington's logo slug, the team-color fallback, budgetClass's
   signature). One copy, one behavior. */

/* ── HTML escaping ────────────────────────────────────────────────────────
   Every owner/team/player name that reaches innerHTML or an interpolated
   attribute goes through esc(). Names are free text: a `"` or `<` in one
   ("D'Amato \"The Hammer\"") otherwise corrupts the surrounding markup.

   Numbers, IDs, position enums, and CSS color values are safe by construction
   and are left alone. Booth comment text uses createElement/textContent and
   never needs this. */
function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g,
        c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ── NFL team logos (ESPN CDN) ────────────────────────────────────────────
   Washington's slug is `wsh`, not `was` — the admin console had `was.png`
   (404) while the viewer had it right. The unknown-team fallback is the
   generic shield rather than an interpolated abbreviation, so nothing
   attacker-shaped can be spliced into an <img src>. */
const NFL_TEAM_LOGOS = {
    'ARI': 'https://a.espncdn.com/i/teamlogos/nfl/500/ari.png',
    'ATL': 'https://a.espncdn.com/i/teamlogos/nfl/500/atl.png',
    'BAL': 'https://a.espncdn.com/i/teamlogos/nfl/500/bal.png',
    'BUF': 'https://a.espncdn.com/i/teamlogos/nfl/500/buf.png',
    'CAR': 'https://a.espncdn.com/i/teamlogos/nfl/500/car.png',
    'CHI': 'https://a.espncdn.com/i/teamlogos/nfl/500/chi.png',
    'CIN': 'https://a.espncdn.com/i/teamlogos/nfl/500/cin.png',
    'CLE': 'https://a.espncdn.com/i/teamlogos/nfl/500/cle.png',
    'DAL': 'https://a.espncdn.com/i/teamlogos/nfl/500/dal.png',
    'DEN': 'https://a.espncdn.com/i/teamlogos/nfl/500/den.png',
    'DET': 'https://a.espncdn.com/i/teamlogos/nfl/500/det.png',
    'GB': 'https://a.espncdn.com/i/teamlogos/nfl/500/gb.png',
    'HOU': 'https://a.espncdn.com/i/teamlogos/nfl/500/hou.png',
    'IND': 'https://a.espncdn.com/i/teamlogos/nfl/500/ind.png',
    'JAX': 'https://a.espncdn.com/i/teamlogos/nfl/500/jax.png',
    'KC': 'https://a.espncdn.com/i/teamlogos/nfl/500/kc.png',
    'LV': 'https://a.espncdn.com/i/teamlogos/nfl/500/lv.png',
    'LAC': 'https://a.espncdn.com/i/teamlogos/nfl/500/lac.png',
    'LAR': 'https://a.espncdn.com/i/teamlogos/nfl/500/lar.png',
    'MIA': 'https://a.espncdn.com/i/teamlogos/nfl/500/mia.png',
    'MIN': 'https://a.espncdn.com/i/teamlogos/nfl/500/min.png',
    'NE': 'https://a.espncdn.com/i/teamlogos/nfl/500/ne.png',
    'NO': 'https://a.espncdn.com/i/teamlogos/nfl/500/no.png',
    'NYG': 'https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png',
    'NYJ': 'https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png',
    'PHI': 'https://a.espncdn.com/i/teamlogos/nfl/500/phi.png',
    'PIT': 'https://a.espncdn.com/i/teamlogos/nfl/500/pit.png',
    'SEA': 'https://a.espncdn.com/i/teamlogos/nfl/500/sea.png',
    'SF': 'https://a.espncdn.com/i/teamlogos/nfl/500/sf.png',
    'TB': 'https://a.espncdn.com/i/teamlogos/nfl/500/tb.png',
    'TEN': 'https://a.espncdn.com/i/teamlogos/nfl/500/ten.png',
    'WAS': 'https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png'
};
function getTeamLogoUrl(teamAbbr) {
    return NFL_TEAM_LOGOS[teamAbbr] || 'https://a.espncdn.com/i/teamlogos/nfl/500/nfl.png';
}

/* ── Per-team signature colors ────────────────────────────────────────────
   Each team's brand color, shifted brighter where the primary is too dark to
   read on the steel/dark backgrounds. Used for the auction backdrop tint
   (admin) and subtle card tints (viewer).

   Exposed two ways because the templates reach for it differently: the map
   directly, or the accessor with its gold fallback. Every caller passes a
   validated NFLTeam enum value, so the fallback is belt-and-braces. */
const NFL_COLORS = {
    ARI: '#C8102E', ATL: '#E31837', BAL: '#5E48A8', BUF: '#1A6DD6', CAR: '#0085CA', CHI: '#E0541C',
    CIN: '#FB4F14', CLE: '#FF6A2B', DAL: '#2A5BD0', DEN: '#FB4F14', DET: '#1B8FD6', GB: '#3A8C52',
    HOU: '#C8324B', IND: '#2A74C4', JAX: '#13909E', KC: '#E31837', LV: '#B9C0C4', LAC: '#0FA0E0',
    LAR: '#2A63E0', MIA: '#00B6C0', MIN: '#6A3CB0', NE: '#D33C50', NO: '#D3BC8D', NYG: '#2A52C9',
    NYJ: '#2E8C5E', PHI: '#1A8579', PIT: '#FFB612', SEA: '#69BE28', SF: '#C8102E', TB: '#D50A0A',
    TEN: '#4B92DB', WAS: '#9A3550'
};
function teamColor(teamAbbr) {
    return NFL_COLORS[teamAbbr] || '#E8A33D';
}

/* ── ESPN player headshot ─────────────────────────────────────────────────
   D/ST has no headshot; callers substitute the team logo.
   IMPORTANT: playerId must be an ESPN player ID — players.json IDs are ESPN
   IDs by convention. If the data is ever sourced from a non-ESPN provider,
   these URLs will 404. See DESIGN.md "Data Models > Player" for details. */
function headshotUrl(playerId) {
    return `https://a.espncdn.com/combiner/i?img=/i/headshots/nfl/players/full/${playerId}.png&w=350&h=254`;
}

/* ── Analyst booth personas ───────────────────────────────────────────────
   Accent ring + headshot file, with an initials monogram for unknowns. */
const BOOTH_PERSONAS = {
    eisen: { accent: '#E8A33D', slug: 'eisen', name: 'Rich Eisen' },
    kiper: { accent: '#56C5D0', slug: 'kiper', name: 'Mel Kiper Jr.' },
    schefter: { accent: '#E2574C', slug: 'schefter', name: 'Adam Schefter' },
    booger: { accent: '#5BBF7B', slug: 'booger', name: 'Booger McFarland' },
    kimes: { accent: '#9B8CEF', slug: 'kimes', name: 'Mina Kimes' },
    mcafee: { accent: '#F0913E', slug: 'mcafee', name: 'Pat McAfee' },
};
const BOOTH_LINEUP = ['eisen', 'kiper', 'schefter', 'booger', 'kimes', 'mcafee'];
function boothPersona(name) {
    const key = (name || '').toLowerCase().replace(/[^a-z]/g, '');
    const m = BOOTH_PERSONAS[key];
    const label = (name || '?').toUpperCase();
    const initials = (name || '?').replace(/[^A-Za-z]/g, '').slice(0, 2).toUpperCase() || '?';
    return m
        ? { key, label, fullName: m.name, accent: m.accent, img: `/static/img/personas/${m.slug}.jpg`, initials }
        : { key, label, fullName: (name || ''), accent: 'var(--slate)', img: '', initials };  // unknown -> monogram
}

/* ── Budget health class ──────────────────────────────────────────────────
   Takes the raw remaining/initial dollars rather than a team object, since
   the two templates model a team differently. */
function budgetClass(remaining, initialBudget) {
    const pct = (remaining / initialBudget) * 100;
    if (pct <= 15) return 'crit';
    if (pct <= 35) return 'warn';
    return 'ok';
}

/* ── FOUT guard ───────────────────────────────────────────────────────────
   Both layouts size themselves off webfont metrics, so the page stays hidden
   until the fonts land — with a timeout so a font CDN outage can't strand it. */
function revealOnReady(el, delayMs = 1500) {
    if (!el) return;
    const reveal = () => el.classList.add('ready');
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(reveal);
    setTimeout(reveal, delayMs);
}
