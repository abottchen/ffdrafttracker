"""ESPN fantasy league-history API -> SeasonResult.

Parses one ESPN season API response (``leagueHistory`` or ``seasons`` view) into
a validated :class:`SeasonResult` for the league-history archive. Owners are
resolved straight from each ESPN member's first name, with a small override for
league nicknames. Pure / import-only; the network fetch lives in
``utils/add_espn_season.py``.
"""

from __future__ import annotations

from src.models.league_history import (
    BestRecord,
    Finisher,
    RosterEntry,
    SeasonResult,
    TeamSeason,
)

# ESPN id -> label maps. ``defaultPositionId`` is the player's position;
# ``lineupSlotId`` is the roster slot they occupied; ``proTeamId`` is the NFL team
# (abbreviations are current-franchise, e.g. id 13 renders as LV even for an
# OAK-era season).
ESPN_POSITION = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "D/ST"}

ESPN_PRO_TEAM = {
    0: "FA",
    1: "ATL",
    2: "BUF",
    3: "CHI",
    4: "CIN",
    5: "CLE",
    6: "DAL",
    7: "DEN",
    8: "DET",
    9: "GB",
    10: "TEN",
    11: "IND",
    12: "KC",
    13: "LV",
    14: "LAR",
    15: "MIA",
    16: "MIN",
    17: "NE",
    18: "NO",
    19: "NYG",
    20: "NYJ",
    21: "PHI",
    22: "ARI",
    23: "PIT",
    24: "LAC",
    25: "SF",
    26: "SEA",
    27: "TB",
    28: "WSH",
    29: "CAR",
    30: "JAX",
    33: "BAL",
    34: "HOU",
}

ESPN_SLOT = {
    0: "QB",
    2: "RB",
    4: "WR",
    6: "TE",
    16: "D/ST",
    17: "K",
    23: "FLEX",
    20: "Bench",
    21: "IR",
}

# ESPN stores given/legal first names; the league refers to these people
# differently. (Roger and Mitch are the same person, who goes by Mitch.)
ESPN_NAME_OVERRIDES = {"Jacqueline": "Jackie", "Roger": "Mitch"}

_ACQUISITION = {
    "DRAFT": "DRAFTED",
    "ADD": "ADDED",
    "TRADE": "TRADED",
    "DRAFTED": "DRAFTED",
    "ADDED": "ADDED",
    "TRADED": "TRADED",
}


def _acquisition(value: str | None) -> str:
    return _ACQUISITION.get(value or "", value or "ADDED")


def _record_str(t: TeamSeason) -> str:
    return f"{t.wins}-{t.losses}-{t.ties}" if t.ties else f"{t.wins}-{t.losses}"


def _best_record(teams: list[TeamSeason]) -> TeamSeason:
    """Best regular-season record: win pct, then wins, then points-for (the
    league's standings tiebreaker)."""

    def key(t: TeamSeason):
        games = t.wins + t.losses + t.ties
        pct = (t.wins + 0.5 * t.ties) / games if games else 0.0
        return (pct, t.wins, t.points_for or 0.0)

    return max(teams, key=key)


def _owner_names(season: dict) -> dict[str, str]:
    """ESPN member GUID -> league first name (applying nickname overrides)."""
    names: dict[str, str] = {}
    for m in season.get("members") or []:
        first = (m.get("firstName") or "").strip()
        if m.get("id") and first:
            names[m["id"]] = ESPN_NAME_OVERRIDES.get(first, first)
    return names


def season_api_to_season(api_json: list | dict) -> tuple[SeasonResult, list[str]]:
    """Convert one ESPN season API response into a validated SeasonResult.

    ``api_json`` is the decoded response from ``leagueHistory`` (a one-element
    list) or ``seasons`` (a single object). Returns ``(season, unknown_guids)``;
    a team whose owner GUID has no member entry gets owner ``"UNKNOWN"`` and is
    reported.
    """
    season = api_json[0] if isinstance(api_json, list) else api_json
    names = _owner_names(season)

    picks = (season.get("draftDetail") or {}).get("picks") or []
    price_by: dict[tuple[int, int], int | None] = {}
    for p in picks:
        if p.get("teamId") is not None and p.get("playerId") is not None:
            price_by[(p["teamId"], p["playerId"])] = p.get("bidAmount")

    unknown: set[str] = set()
    teams: list[TeamSeason] = []
    for t in season.get("teams", []):
        rec = (t.get("record") or {}).get("overall") or {}
        guid = t.get("primaryOwner") or (t.get("owners") or [None])[0]
        owner = names.get(guid, "UNKNOWN")
        if owner == "UNKNOWN" and guid:
            unknown.add(guid)

        roster = []
        for e in (t.get("roster") or {}).get("entries") or []:
            pl = (e.get("playerPoolEntry") or {}).get("player") or {}
            price = price_by.get((t.get("id"), pl.get("id")))
            roster.append(
                RosterEntry(
                    player_name=pl.get("fullName", ""),
                    position=ESPN_POSITION.get(
                        pl.get("defaultPositionId"), str(pl.get("defaultPositionId"))
                    ),
                    nfl_team=ESPN_PRO_TEAM.get(
                        pl.get("proTeamId"), str(pl.get("proTeamId"))
                    ),
                    slot=ESPN_SLOT.get(
                        e.get("lineupSlotId"), str(e.get("lineupSlotId"))
                    ),
                    acquisition="DRAFTED"
                    if price is not None
                    else _acquisition(e.get("acquisitionType")),
                    draft_price=price if price is not None else None,
                )
            )

        pf = rec.get("pointsFor")
        name = (
            t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}"
        ).strip()
        teams.append(
            TeamSeason(
                source_team_id=t.get("id"),
                team_name=name,
                owner=owner,
                wins=rec.get("wins", 0),
                losses=rec.get("losses", 0),
                ties=rec.get("ties", 0),
                points_for=round(pf, 2) if pf is not None else None,
                final_rank=t.get("rankCalculatedFinal"),
                roster=roster,
            )
        )

    if not teams:
        raise ValueError(
            f"No teams in the ESPN response for season {season.get('seasonId')}."
        )

    by_rank = {t.final_rank: t for t in teams if t.final_rank}
    champ = by_rank.get(1) or teams[0]
    runner = by_rank.get(2) or teams[0]
    best = _best_record(teams)
    year = season.get("seasonId")

    result = SeasonResult(
        year=year,
        champion=Finisher(owner=champ.owner, team_name=champ.team_name),
        runner_up=Finisher(owner=runner.owner, team_name=runner.team_name),
        best_record=BestRecord(
            owner=best.owner, team_name=best.team_name, record=_record_str(best)
        ),
        source="espn",
        draft_type="auction",
        standings=teams,
    )
    if year == 2022:  # league-side co-championship (credits the runner-up)
        result.shared_title = True
        result.note = "SPLIT TITLE"
    return result, sorted(unknown)
