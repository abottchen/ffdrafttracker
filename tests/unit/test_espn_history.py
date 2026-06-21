"""Tests for the ESPN league-history API parser."""

from src.espn_history import season_api_to_raw

OWNER_MAP = {"{AAA}": "Adam", "{BBB}": "Greg"}


def _api():
    # Minimal ESPN leagueHistory-shaped response (a one-element list).
    return [
        {
            "seasonId": 2026,
            "draftDetail": {
                "picks": [
                    {"teamId": 1, "playerId": 100, "bidAmount": 41},
                ]
            },
            "teams": [
                {
                    "id": 1,
                    "name": "Take Mahomes Tonight",
                    "primaryOwner": "{AAA}",
                    "rankCalculatedFinal": 1,
                    "record": {
                        "overall": {
                            "wins": 11,
                            "losses": 3,
                            "ties": 0,
                            "pointsFor": 1800.456,
                        }
                    },
                    "roster": {
                        "entries": [
                            {
                                "lineupSlotId": 2,
                                "acquisitionType": "DRAFT",
                                "playerPoolEntry": {
                                    "player": {
                                        "id": 100,
                                        "fullName": "Christian McCaffrey",
                                        "defaultPositionId": 2,
                                        "proTeamId": 25,
                                    }
                                },
                            },
                            {
                                "lineupSlotId": 20,
                                "acquisitionType": "ADD",
                                "playerPoolEntry": {
                                    "player": {
                                        "id": 200,
                                        "fullName": "Some Waiver Guy",
                                        "defaultPositionId": 4,
                                        "proTeamId": 17,
                                    }
                                },
                            },
                        ]
                    },
                },
                {
                    "id": 2,
                    "name": "Mystery Team",
                    "primaryOwner": "{ZZZ}",  # not in owner map
                    "rankCalculatedFinal": 2,
                    "record": {
                        "overall": {
                            "wins": 9,
                            "losses": 5,
                            "ties": 0,
                            "pointsFor": 1700,
                        }
                    },
                    "roster": {"entries": []},
                },
            ],
        }
    ]


def test_parses_teams_records_and_draft_join():
    raw, unknown = season_api_to_raw(_api(), OWNER_MAP)
    assert raw["year"] == 2026
    assert raw["source"] == "espn"
    t1 = raw["teams"][0]
    assert t1["owner"] == "Adam"
    assert t1["final_rank"] == 1
    assert t1["points_for"] == 1800.46  # rounded
    mcc = t1["roster"][0]
    assert mcc["player_name"] == "Christian McCaffrey"
    assert mcc["position"] == "RB"
    assert mcc["nfl_team"] == "SF"
    assert mcc["slot"] == "RB"
    assert mcc["acquisition"] == "DRAFTED"
    assert mcc["draft_price"] == 41
    # waiver add: no draft price, bench slot
    waiver = t1["roster"][1]
    assert waiver["acquisition"] == "ADDED"
    assert waiver["draft_price"] is None
    assert waiver["slot"] == "Bench"


def test_unknown_owner_reported_not_invented():
    raw, unknown = season_api_to_raw(_api(), OWNER_MAP)
    assert raw["teams"][1]["owner"] == "UNKNOWN"
    assert unknown == ["{ZZZ}"]
