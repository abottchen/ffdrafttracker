"""Deterministic data slice for the Analyst Booth.

Loads the data dir, reuses the existing domain models and ``draft_rules``, and
emits BOTH a Pydantic-validated ``AnalystSlice`` (the tested source of truth)
and a compact rendered text brief the host forwards near-verbatim.

The builder emits **neutral facts only** — names, counts, prices, prior-season
stat lines, comparables, scarcity. It never labels a pick "overpay" or "reach";
valuation is the personas' job.

Run as a module to print the brief + JSON for the current data dir::

    python -m src.booth.slice [--data-dir DIR] [--json] [--recent-log N]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import BaseModel, Field

from src.booth.log import AnalystComment, read_comments
from src.draft_rules import max_bid, remaining_roster_spots
from src.models import Configuration, DraftState, Owner, Player, Team
from src.models.player_stats import PlayerStats, PlayerStatsCollection

# Skill positions we rank/scarcity-track. K and D/ST are rostered but not ranked
# by production here (kicking is a single points total; D/ST has no stat line).
SKILL_POSITIONS = ("QB", "RB", "WR", "TE")

# How many ranked players to surface per position in "best available".
TOP_N_PER_POSITION = 5

# How many recent same-position comparables to include for a nominee.
COMPARABLES_N = 5

# How many picks to surface at each end of the value board.
VALUE_BOARD_N = 3

# How many recent pick positions to surface for run-spotting.
RECENT_PICKS_N = 8


# ---------------------------------------------------------------------------
# Production scoring (market-derived, no ADP)
# ---------------------------------------------------------------------------
def _has_real_stats(stats: PlayerStats | None) -> bool:
    """True if the player has any prior-season production block recorded."""
    if stats is None:
        return False
    return any(
        block is not None
        for block in (stats.passing, stats.rushing, stats.receiving, stats.kicking)
    )


def production_score(stats: PlayerStats | None) -> float:
    """Fantasy-style production score from prior-season stats (PPR-ish).

    A deterministic, market-derived proxy for "how productive was this player
    last season" — used only to ORDER players within a position. Players with
    no recorded production score 0.0 (and are flagged as rookies elsewhere).
    """
    if stats is None:
        return 0.0
    score = 0.0
    if stats.passing is not None:
        score += stats.passing.yards / 25.0
        score += stats.passing.tds * 4.0
        score -= stats.passing.ints * 2.0
    if stats.rushing is not None:
        score += stats.rushing.yards / 10.0
        score += stats.rushing.tds * 6.0
        score -= stats.rushing.fumbles * 2.0
    if stats.receiving is not None:
        score += stats.receiving.receptions * 1.0  # PPR
        score += stats.receiving.yards / 10.0
        score += stats.receiving.tds * 6.0
        score -= stats.receiving.fumbles * 2.0
    if stats.kicking is not None:
        score += stats.kicking.points
    return round(score, 1)


# ---------------------------------------------------------------------------
# Slice sub-models
# ---------------------------------------------------------------------------
class RulesBlock(BaseModel):
    initial_budget: int
    min_bid: int
    total_rounds: int
    position_maximums: dict[str, int]


class StatLine(BaseModel):
    """A player's prior-season stat line, neutral facts only."""

    player_id: int
    name: str
    position: str
    nfl_team: str
    summary: str | None = None  # e.g. "1280rec ..." pre-formatted by the data set
    production_score: float = 0.0
    rookie: bool = False  # no prior-season production -> empty stat line


class RosterLine(BaseModel):
    player_id: int
    name: str
    position: str
    nfl_team: str
    price: int


class TeamSnapshot(BaseModel):
    """A team's current standing — budget, roster, needs, legal ceiling."""

    owner_id: int
    owner_name: str
    team_name: str
    budget_remaining: int
    max_legal_bid: int | None
    slots_filled: int
    slots_left: int
    position_counts: dict[str, int]
    roster: list[RosterLine] = Field(default_factory=list)
    # Positions still worth chasing, ordered RB>WR>QB>TE>D/ST>K. Threshold-based,
    # not "under position max": RB/WR need to 3 all draft; QB to 1 (2nd late);
    # TE gated on elite-TE availability / roster fill; D/ST & K only when nearly
    # full. Empty once the roster has no slots left.
    needs: list[str] = Field(default_factory=list)


class LastPick(BaseModel):
    pick_id: int
    price: int
    player: StatLine
    drafter: TeamSnapshot


class PositionBoard(BaseModel):
    """Best available at a position + how much depth remains behind them."""

    position: str
    top: list[StatLine] = Field(default_factory=list)
    depth_left: int = 0  # total remaining at this position


class BidBoardRow(BaseModel):
    owner_id: int
    owner_name: str
    team_name: str
    budget_remaining: int
    max_legal_bid: int | None
    needs_position: bool  # nominee's position is a real roster need (per _needs)


class Comparable(BaseModel):
    pick_id: int
    name: str
    nfl_team: str
    price: int


class ValuePick(BaseModel):
    """A completed pick with neutral price-vs-production facts.

    ``value_ratio`` is ``production_score / price`` — a neutral ordering signal,
    NOT a verdict. Personas decide what counts as a steal or an overpay.
    """

    pick_id: int
    name: str
    position: str
    nfl_team: str
    price: int
    production_score: float
    value_ratio: float
    drafter_team_name: str


class NomineeBlock(BaseModel):
    player: StatLine
    current_bid: int
    nominating_owner_id: int
    nominating_owner_name: str
    nominating_team_name: str
    current_bidder_id: int
    current_bidder_name: str
    current_bidder_team_name: str


# ---------------------------------------------------------------------------
# Top-level slice
# ---------------------------------------------------------------------------
class AnalystSlice(BaseModel):
    """Grounded, neutral facts for one draft-state event.

    ``mode`` is ``NO-NOMINEE`` (react to the pick that just landed / tee up the
    next nominator), ``NOMINEE-LIVE`` (who should be bidding, and at what), or
    ``RETROSPECTIVE`` (idle-lull musing — a draft-wide retrospective).
    """

    mode: str  # "NO-NOMINEE" | "NOMINEE-LIVE" | "RETROSPECTIVE"
    state_version: int
    draft_year: int
    picks_made: int
    total_rounds: int
    approx_round: int
    rules: RulesBlock
    recent_log: list[AnalystComment] = Field(default_factory=list)

    # Mode A — NO NOMINEE
    last_pick: LastPick | None = None
    next_nominator: TeamSnapshot | None = None
    best_available: list[PositionBoard] = Field(default_factory=list)

    # Mode B — NOMINEE LIVE
    nominee: NomineeBlock | None = None
    bid_board: list[BidBoardRow] = Field(default_factory=list)
    comparables: list[Comparable] = Field(default_factory=list)
    position_scarcity: int | None = None

    # Mode C — RETROSPECTIVE (idle musings; draft-wide retrospective)
    all_teams: list[TeamSnapshot] = Field(default_factory=list)
    value_board: list[ValuePick] = Field(default_factory=list)
    recent_pick_positions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
class BoothData(BaseModel):
    """Everything the builder needs, loaded once from the data dir."""

    model_config = {"arbitrary_types_allowed": True}

    state: DraftState
    config: Configuration
    players: dict[int, Player]
    owners: dict[int, Owner]
    stats: PlayerStatsCollection


def load_booth_data(data_dir: Path) -> BoothData:
    """Load draft state, config, players, owners and stats from ``data_dir``."""
    state = DraftState.load_from_file(data_dir / "draft_state.json")
    config = Configuration.load_from_file(data_dir / "config.json")

    players_raw = json.loads((data_dir / "players.json").read_text())
    players = {p["id"]: Player.model_validate(p) for p in players_raw}

    owners_raw = json.loads((data_dir / "owners.json").read_text())
    owners = {o["id"]: Owner.model_validate(o) for o in owners_raw}

    stats_path = data_dir / "player_stats.json"
    if stats_path.exists():
        stats = PlayerStatsCollection.model_validate_json(stats_path.read_text())
    else:
        stats = PlayerStatsCollection({})

    return BoothData(
        state=state, config=config, players=players, owners=owners, stats=stats
    )


def _read_recent_log(data_dir: Path, limit: int) -> list[AnalystComment]:
    """Tail of analyst-comments.jsonl (committed lines only), for callbacks.

    Delegates to ``log.read_comments`` so the defensive trailing-tail handling
    lives in exactly one place. (The duplicated copy that used to live here
    parsed first and then dropped the last *record*, which discarded a good
    committed line whenever the torn final line was unparseable.)
    """
    if limit <= 0:
        return []
    records = read_comments(data_dir / "analyst-comments.jsonl")
    return records[-limit:]


# ---------------------------------------------------------------------------
# Resolution helpers
# ---------------------------------------------------------------------------
def _stat_line(player: Player, stats: PlayerStats | None) -> StatLine:
    """Resolve a player + their prior-season stats into a neutral StatLine."""
    rookie = not _has_real_stats(stats)
    return StatLine(
        player_id=player.id,
        name=player.full_name,
        position=str(player.position),
        nfl_team=str(player.team),
        summary=None if rookie else (stats.stats_summary if stats else None),
        production_score=production_score(stats),
        rookie=rookie,
    )


def _position_counts(team: Team, players: dict[int, Player]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for pick in team.picks:
        player = players.get(pick.player_id)
        if player is None:
            continue
        pos = str(player.position)
        counts[pos] = counts.get(pos, 0) + 1
    return counts


def _elite_te_available(data: BoothData) -> bool:
    """True if any of the league's top-3 TEs (by production) is still available.

    Ranks ALL TEs (drafted + available) by ``production_score`` of their prior
    season, takes the top 3, and reports whether any sits in the available pool.
    Global — same for every team — so compute it once per slice.
    """
    te_scores: list[tuple[int, float]] = []
    for pid, player in data.players.items():
        if str(player.position) != "TE":
            continue
        score = production_score(data.stats.get_player_stats(pid))
        te_scores.append((pid, score))
    te_scores.sort(key=lambda ps: ps[1], reverse=True)
    top3_ids = {pid for pid, _ in te_scores[:3]}
    available = set(data.state.available_player_ids)
    return bool(top3_ids & available)


def _needs(
    counts: dict[str, int], slots_left: int, *, elite_te_available: bool
) -> list[str]:
    """Positions still worth chasing, ordered RB>WR>QB>TE>D/ST>K.

    Threshold-based rather than "under position max". A team with no roster
    slots left returns no needs.
    """
    if slots_left <= 0:
        return []

    needs: list[str] = []

    # RB / WR: need a real stable (2 starters + flex/backup) the whole draft.
    if counts.get("RB", 0) < 3:
        needs.append("RB")
    if counts.get("WR", 0) < 3:
        needs.append("WR")

    # QB: always need a starter; a 2nd QB only becomes a need late.
    qb = counts.get("QB", 0)
    if qb < 1 or (qb < 2 and slots_left <= 5):
        needs.append("QB")

    # TE: gated on elite-TE availability and how full the roster is.
    te = counts.get("TE", 0)
    if te == 0:
        if elite_te_available or slots_left <= 8:
            needs.append("TE")
    elif te == 1:
        if slots_left <= 5:
            needs.append("TE")
    # te >= 2: not a need.

    # D/ST and K: never backups, and only once the roster is nearly full.
    if counts.get("D/ST", 0) < 1 and slots_left <= 3:
        needs.append("D/ST")
    if counts.get("K", 0) < 1 and slots_left <= 3:
        needs.append("K")

    return needs


def _roster_entries(team: Team, players: dict[int, Player]) -> list[RosterLine]:
    entries: list[RosterLine] = []
    for pick in team.picks:
        player = players.get(pick.player_id)
        if player is None:
            continue
        entries.append(
            RosterLine(
                player_id=player.id,
                name=player.full_name,
                position=str(player.position),
                nfl_team=str(player.team),
                price=pick.price,
            )
        )
    # Group by position for readability, then by price descending.
    pos_order = {p: i for i, p in enumerate(["QB", "RB", "WR", "TE", "K", "D/ST"])}
    entries.sort(key=lambda e: (pos_order.get(e.position, 99), -e.price))
    return entries


def _team_snapshot(
    team: Team, data: BoothData, *, elite_te_available: bool
) -> TeamSnapshot:
    owner = data.owners.get(team.owner_id)
    counts = _position_counts(team, data.players)
    slots_left = remaining_roster_spots(team, data.config)
    return TeamSnapshot(
        owner_id=team.owner_id,
        owner_name=owner.owner_name if owner else f"Owner {team.owner_id}",
        team_name=owner.team_name if owner else f"Team {team.owner_id}",
        budget_remaining=team.budget_remaining,
        max_legal_bid=max_bid(team, data.config),
        slots_filled=len(team.picks),
        slots_left=slots_left,
        position_counts=counts,
        roster=_roster_entries(team, data.players),
        needs=_needs(counts, slots_left, elite_te_available=elite_te_available),
    )


def _ranked_available(data: BoothData) -> dict[str, list[StatLine]]:
    """All available players grouped by position, sorted by production desc.

    Rookies (no prior production) sort to the back within their position.
    """
    by_pos: dict[str, list[StatLine]] = {}
    for pid in data.state.available_player_ids:
        player = data.players.get(pid)
        if player is None:
            continue
        stats = data.stats.get_player_stats(pid)
        line = _stat_line(player, stats)
        by_pos.setdefault(line.position, []).append(line)
    for lines in by_pos.values():
        # Non-rookies first (by production desc), rookies last (by name).
        lines.sort(key=lambda s: (s.rookie, -s.production_score, s.name))
    return by_pos


# ---------------------------------------------------------------------------
# Mode builders
# ---------------------------------------------------------------------------
def _build_no_nominee(data: BoothData, slc: AnalystSlice) -> None:
    teams_by_owner = {t.owner_id: t for t in data.state.teams}
    elite_te = _elite_te_available(data)

    # Last pick = the DraftPick with the max pick_id across all teams.
    last_pick_obj = None
    drafter_team = None
    for team in data.state.teams:
        for pick in team.picks:
            if last_pick_obj is None or pick.pick_id > last_pick_obj.pick_id:
                last_pick_obj = pick
                drafter_team = team
    if last_pick_obj is not None and drafter_team is not None:
        player = data.players.get(last_pick_obj.player_id)
        if player is not None:
            slc.last_pick = LastPick(
                pick_id=last_pick_obj.pick_id,
                price=last_pick_obj.price,
                player=_stat_line(player, data.stats.get_player_stats(player.id)),
                drafter=_team_snapshot(drafter_team, data, elite_te_available=elite_te),
            )

    # Next to nominate.
    next_team = teams_by_owner.get(data.state.next_to_nominate)
    if next_team is not None:
        slc.next_nominator = _team_snapshot(
            next_team, data, elite_te_available=elite_te
        )

    # Best available per skill position + depth-left.
    ranked = _ranked_available(data)
    boards: list[PositionBoard] = []
    for pos in SKILL_POSITIONS:
        lines = ranked.get(pos, [])
        boards.append(
            PositionBoard(
                position=pos,
                top=lines[:TOP_N_PER_POSITION],
                depth_left=len(lines),
            )
        )
    slc.best_available = boards


def _build_nominee_live(data: BoothData, slc: AnalystSlice) -> None:
    nominated = data.state.nominated
    assert nominated is not None  # caller guarantees mode
    player = data.players.get(nominated.player_id)

    nominating = data.owners.get(nominated.nominating_owner_id)
    bidder = data.owners.get(nominated.current_bidder_id)
    if player is not None:
        slc.nominee = NomineeBlock(
            player=_stat_line(player, data.stats.get_player_stats(player.id)),
            current_bid=nominated.current_bid,
            nominating_owner_id=nominated.nominating_owner_id,
            nominating_owner_name=(nominating.owner_name if nominating else "Unknown"),
            nominating_team_name=(nominating.team_name if nominating else "Unknown"),
            current_bidder_id=nominated.current_bidder_id,
            current_bidder_name=bidder.owner_name if bidder else "Unknown",
            current_bidder_team_name=bidder.team_name if bidder else "Unknown",
        )

    nominee_pos = str(player.position) if player is not None else None
    elite_te = _elite_te_available(data)

    # Bid board: every team's budget, legal ceiling, and whether the nominee's
    # position is a real roster NEED for them. "Need" (not raw position-max
    # capacity) is what tells the booth who should be bidding — it excludes
    # wasteful over-builds (a 3rd QB/TE, a 2nd K/D-ST, a 6th-7th RB/WR are never
    # needs) and a full roster (no needs at all).
    rows: list[BidBoardRow] = []
    for team in data.state.teams:
        owner = data.owners.get(team.owner_id)
        counts = _position_counts(team, data.players)
        slots_left = remaining_roster_spots(team, data.config)
        team_needs = _needs(counts, slots_left, elite_te_available=elite_te)
        needs_pos = nominee_pos is not None and nominee_pos in team_needs
        rows.append(
            BidBoardRow(
                owner_id=team.owner_id,
                owner_name=owner.owner_name if owner else f"Owner {team.owner_id}",
                team_name=owner.team_name if owner else f"Team {team.owner_id}",
                budget_remaining=team.budget_remaining,
                max_legal_bid=max_bid(team, data.config),
                needs_position=needs_pos,
            )
        )
    slc.bid_board = rows

    # Comparables: recent picks at the SAME position + their prices.
    if nominee_pos is not None:
        same_pos_picks = []
        for team in data.state.teams:
            for pick in team.picks:
                p = data.players.get(pick.player_id)
                if p is not None and str(p.position) == nominee_pos:
                    same_pos_picks.append((pick, p))
        same_pos_picks.sort(key=lambda pp: pp[0].pick_id, reverse=True)
        slc.comparables = [
            Comparable(
                pick_id=pick.pick_id,
                name=p.full_name,
                nfl_team=str(p.team),
                price=pick.price,
            )
            for pick, p in same_pos_picks[:COMPARABLES_N]
        ]

        # Position scarcity: comparable players still available at this position.
        ranked = _ranked_available(data)
        slc.position_scarcity = len(ranked.get(nominee_pos, []))


def _build_retrospective(data: BoothData, slc: AnalystSlice) -> None:
    elite_te = _elite_te_available(data)

    # All teams, ordered by cash on hand (budget remaining) descending — who is
    # loaded and who is broke is the spine of most retrospective takes.
    snaps = [
        _team_snapshot(team, data, elite_te_available=elite_te)
        for team in data.state.teams
    ]
    snaps.sort(key=lambda s: -s.budget_remaining)
    slc.all_teams = snaps

    team_name_by_owner = {
        team.owner_id: (
            data.owners[team.owner_id].team_name
            if team.owner_id in data.owners
            else f"Team {team.owner_id}"
        )
        for team in data.state.teams
    }

    # Value board: every completed pick with neutral price-vs-production facts,
    # best production-per-dollar first. Ties (e.g. rookies at ratio 0) order the
    # priciest last, so the tail surfaces expensive-for-the-production picks.
    value: list[ValuePick] = []
    for team in data.state.teams:
        for pick in team.picks:
            player = data.players.get(pick.player_id)
            if player is None:
                continue
            score = production_score(data.stats.get_player_stats(pick.player_id))
            ratio = round(score / pick.price, 2) if pick.price > 0 else 0.0
            value.append(
                ValuePick(
                    pick_id=pick.pick_id,
                    name=player.full_name,
                    position=str(player.position),
                    nfl_team=str(player.team),
                    price=pick.price,
                    production_score=score,
                    value_ratio=ratio,
                    drafter_team_name=team_name_by_owner[team.owner_id],
                )
            )
    value.sort(key=lambda v: (v.value_ratio, -v.price), reverse=True)
    slc.value_board = value

    # Best available + depth (scarcity) per skill position — same board the
    # NO-NOMINEE mode builds.
    ranked = _ranked_available(data)
    slc.best_available = [
        PositionBoard(
            position=pos,
            top=ranked.get(pos, [])[:TOP_N_PER_POSITION],
            depth_left=len(ranked.get(pos, [])),
        )
        for pos in SKILL_POSITIONS
    ]

    # Recent pick positions (chronological) for spotting a positional run.
    # Filter unresolved players out BEFORE windowing, so a missing-player pick
    # in the tail can't shrink or misalign the last-N view.
    resolved_picks = [
        (pick, player)
        for team in data.state.teams
        for pick in team.picks
        if (player := data.players.get(pick.player_id)) is not None
    ]
    resolved_picks.sort(key=lambda pp: pp[0].pick_id)
    slc.recent_pick_positions = [
        str(player.position) for _, player in resolved_picks[-RECENT_PICKS_N:]
    ]


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------
def build_slice(
    data_dir: Path, *, recent_log_limit: int = 0, retrospective: bool = False
) -> AnalystSlice:
    """Build the validated ``AnalystSlice`` for the data dir's current state.

    ``retrospective=True`` (only meaningful with no live nominee) builds the
    draft-wide RETROSPECTIVE payload for an idle-lull musing.
    """
    data = load_booth_data(data_dir)
    picks_made = sum(len(t.picks) for t in data.state.teams)
    total_rounds = data.config.total_rounds
    num_teams = max(len(data.state.teams), 1)
    # Approx round: 1-based, derived from picks per "round" across all teams.
    approx_round = min(total_rounds, picks_made // num_teams + 1)

    if data.state.nominated is not None:
        mode = "NOMINEE-LIVE"
    elif retrospective:
        mode = "RETROSPECTIVE"
    else:
        mode = "NO-NOMINEE"

    slc = AnalystSlice(
        mode=mode,
        state_version=data.state.version,
        draft_year=data.config.draft_year,
        picks_made=picks_made,
        total_rounds=total_rounds,
        approx_round=approx_round,
        rules=RulesBlock(
            initial_budget=data.config.initial_budget,
            min_bid=data.config.min_bid,
            total_rounds=total_rounds,
            position_maximums=data.config.position_maximums,
        ),
        recent_log=_read_recent_log(data_dir, recent_log_limit),
    )

    if mode == "NO-NOMINEE":
        _build_no_nominee(data, slc)
    elif mode == "NOMINEE-LIVE":
        _build_nominee_live(data, slc)
    else:  # RETROSPECTIVE
        _build_retrospective(data, slc)
    return slc


# ---------------------------------------------------------------------------
# Brief rendering (compact text Eisen forwards near-verbatim)
# ---------------------------------------------------------------------------
def _fmt_stat_line(line: StatLine) -> str:
    if line.rookie:
        tag = " [ROOKIE — no prior stats]"
        stat = ""
    else:
        tag = ""
        stat = f" — {line.summary}" if line.summary else ""
    return f"{line.name} ({line.position}, {line.nfl_team}){stat}{tag}"


def _fmt_bid(max_legal_bid: int | None) -> str:
    """Render a legal-bid ceiling; a full roster (``None``) shows as a dash."""
    return f"${max_legal_bid}" if max_legal_bid is not None else "— (full)"


def _fmt_team_snapshot(snap: TeamSnapshot) -> list[str]:
    lines = [
        f"{snap.team_name} ({snap.owner_name}) — "
        f"${snap.budget_remaining} left, "
        f"max legal bid {_fmt_bid(snap.max_legal_bid)}, "
        f"{snap.slots_filled} filled / {snap.slots_left} open",
    ]
    counts = ", ".join(f"{pos}:{n}" for pos, n in sorted(snap.position_counts.items()))
    lines.append(f"  positions: {counts or '(none)'}")
    lines.append(f"  needs: {', '.join(snap.needs) if snap.needs else '(roster full)'}")
    return lines


def render_brief(slc: AnalystSlice) -> str:
    """Render the slice into a compact text brief for the booth host."""
    out: list[str] = []
    out.append(f"=== ANALYST BRIEF [{slc.mode}] ===")
    out.append(
        f"{slc.draft_year} draft | round ~{slc.approx_round}/{slc.total_rounds} | "
        f"{slc.picks_made} picks made | state v{slc.state_version}"
    )
    r = slc.rules
    out.append(
        f"rules: budget ${r.initial_budget}, min bid ${r.min_bid}, "
        f"position max {r.position_maximums}"
    )

    if slc.mode == "NO-NOMINEE":
        if slc.last_pick is not None:
            lp = slc.last_pick
            out.append("")
            out.append(
                f"LAST PICK: {_fmt_stat_line(lp.player)} for ${lp.price} "
                f"to {lp.drafter.team_name} ({lp.drafter.owner_name})"
            )
            out.append("Drafter now:")
            out.extend(_fmt_team_snapshot(lp.drafter))
        if slc.next_nominator is not None:
            out.append("")
            out.append("NEXT TO NOMINATE:")
            out.extend(_fmt_team_snapshot(slc.next_nominator))
        if slc.best_available:
            out.append("")
            out.append("BEST AVAILABLE:")
            for board in slc.best_available:
                names = "; ".join(_fmt_stat_line(s) for s in board.top) or "(none)"
                out.append(f"  {board.position} ({board.depth_left} left): {names}")
    elif slc.mode == "NOMINEE-LIVE":
        if slc.nominee is not None:
            n = slc.nominee
            out.append("")
            out.append(f"NOMINEE: {_fmt_stat_line(n.player)}")
            out.append(
                f"  nominated by {n.nominating_team_name} ({n.nominating_owner_name}); "
                f"current bid ${n.current_bid} from {n.current_bidder_team_name} "
                f"({n.current_bidder_name})"
            )
        if slc.position_scarcity is not None and slc.nominee is not None:
            out.append(
                f"  scarcity: {slc.position_scarcity} comparable "
                f"{slc.nominee.player.position}s still available"
            )
        if slc.comparables:
            out.append("")
            out.append("COMPARABLES (recent picks, same position):")
            for c in slc.comparables:
                out.append(f"  {c.name} ({c.nfl_team}) — ${c.price}")
        if slc.bid_board:
            out.append("")
            out.append("BID BOARD (budget / max legal bid / needs the position?):")
            for row in slc.bid_board:
                flag = "need" if row.needs_position else "no need"
                out.append(
                    f"  {row.team_name} ({row.owner_name}): "
                    f"${row.budget_remaining} / max {_fmt_bid(row.max_legal_bid)} "
                    f"/ {flag}"
                )
    elif slc.mode == "RETROSPECTIVE":
        if slc.all_teams:
            out.append("")
            out.append("STATE OF THE DRAFT (teams by cash on hand):")
            for snap in slc.all_teams:
                out.extend(_fmt_team_snapshot(snap))
        if slc.value_board:
            out.append("")
            out.append(
                "VALUE BOARD (production per $ — personas judge steal vs overpay):"
            )
            out.append("  Most production per $:")
            for v in slc.value_board[:VALUE_BOARD_N]:
                out.append(
                    f"    {v.name} ({v.position}, {v.nfl_team}) — ${v.price}, "
                    f"score {v.production_score}, ratio {v.value_ratio} "
                    f"[{v.drafter_team_name}]"
                )
            if len(slc.value_board) > VALUE_BOARD_N:
                out.append("  Priciest vs production:")
                for v in reversed(slc.value_board[-VALUE_BOARD_N:]):
                    out.append(
                        f"    {v.name} ({v.position}, {v.nfl_team}) — ${v.price}, "
                        f"score {v.production_score}, ratio {v.value_ratio} "
                        f"[{v.drafter_team_name}]"
                    )
        if slc.recent_pick_positions:
            out.append("")
            out.append(
                "RECENT PICK POSITIONS (oldest->newest): "
                + " ".join(slc.recent_pick_positions)
            )
        if slc.best_available:
            out.append("")
            out.append("BEST AVAILABLE / DEPTH:")
            for board in slc.best_available:
                names = "; ".join(_fmt_stat_line(s) for s in board.top) or "(none)"
                out.append(f"  {board.position} ({board.depth_left} left): {names}")

    if slc.recent_log:
        out.append("")
        out.append("RECENT COMMENTARY:")
        for rec in slc.recent_log:
            out.append(f"  [{rec.persona}] {rec.text}")

    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the Analyst Booth slice.")
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory holding draft_state.json etc. (default: data)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the validated JSON slice instead of the rendered brief.",
    )
    parser.add_argument(
        "--recent-log",
        type=int,
        default=0,
        help="Include the last N committed analyst-comments lines.",
    )
    parser.add_argument(
        "--retrospective",
        action="store_true",
        help="Build the draft-wide RETROSPECTIVE slice (idle-lull musing).",
    )
    args = parser.parse_args(argv)

    slc = build_slice(
        Path(args.data_dir),
        recent_log_limit=args.recent_log,
        retrospective=args.retrospective,
    )
    if args.json:
        print(slc.model_dump_json(indent=2))
    else:
        print(render_brief(slc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
