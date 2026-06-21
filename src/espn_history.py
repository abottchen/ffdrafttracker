"""ESPN fantasy league-history API -> raw season dict.

Pure parsing of an ESPN ``leagueHistory`` API response into the same per-season
shape stored under ``data/raw_history/espn/<year>.json`` (the input the
league-history build consumes). The network fetch lives in
``utils/add_espn_season.py``; this module is import-only and unit-testable.
"""

from __future__ import annotations

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


def season_api_to_raw(
    api_json: list | dict, owner_map: dict[str, str]
) -> tuple[dict, list[str]]:
    """Convert one ESPN season API response into the raw per-season dict.

    ``api_json`` is the decoded response from ``leagueHistory`` (a one-element
    list) or ``seasons`` (a single object). ``owner_map`` maps ESPN member GUIDs
    to first names. Returns ``(raw_season, unknown_guids)``; any team whose owner
    GUID is missing from the map gets owner ``"UNKNOWN"`` and is reported.
    """
    season = api_json[0] if isinstance(api_json, list) else api_json

    picks = (season.get("draftDetail") or {}).get("picks") or []
    price_by: dict[tuple[int, int], int | None] = {}
    for p in picks:
        if p.get("teamId") is not None and p.get("playerId") is not None:
            price_by[(p["teamId"], p["playerId"])] = p.get("bidAmount")

    unknown: set[str] = set()
    teams_out = []
    for t in season.get("teams", []):
        rec = (t.get("record") or {}).get("overall") or {}
        guid = t.get("primaryOwner") or (t.get("owners") or [None])[0]
        owner = owner_map.get(guid, "UNKNOWN")
        if owner == "UNKNOWN" and guid:
            unknown.add(guid)

        roster = []
        for e in (t.get("roster") or {}).get("entries") or []:
            pl = (e.get("playerPoolEntry") or {}).get("player") or {}
            price = price_by.get((t.get("id"), pl.get("id")))
            roster.append(
                {
                    "player_name": pl.get("fullName", ""),
                    "position": ESPN_POSITION.get(
                        pl.get("defaultPositionId"), str(pl.get("defaultPositionId"))
                    ),
                    "nfl_team": ESPN_PRO_TEAM.get(
                        pl.get("proTeamId"), str(pl.get("proTeamId"))
                    ),
                    "slot": ESPN_SLOT.get(
                        e.get("lineupSlotId"), str(e.get("lineupSlotId"))
                    ),
                    "acquisition": "DRAFTED"
                    if price is not None
                    else _acquisition(e.get("acquisitionType")),
                    "draft_price": price if price is not None else None,
                    "draft_pick": None,
                }
            )

        name = (
            t.get("name") or f"{t.get('location', '')} {t.get('nickname', '')}"
        ).strip()
        pf = rec.get("pointsFor")
        teams_out.append(
            {
                "source_team_id": t.get("id"),
                "team_name": name,
                "owner": owner,
                "wins": rec.get("wins", 0),
                "losses": rec.get("losses", 0),
                "ties": rec.get("ties", 0),
                "points_for": round(pf, 2) if pf is not None else None,
                "final_rank": t.get("rankCalculatedFinal"),
                "roster": roster,
            }
        )

    return (
        {
            "year": season.get("seasonId"),
            "source": "espn",
            "draft_type": "auction",
            "teams": teams_out,
        },
        sorted(unknown),
    )
