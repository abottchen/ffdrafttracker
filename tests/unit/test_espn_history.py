"""Tests for the ESPN league-history API parser."""

import pytest

from src.espn_history import season_api_to_season


def _api(season_id=2024):
    # Minimal ESPN leagueHistory-shaped response (a one-element list).
    return [
        {
            "seasonId": season_id,
            "members": [
                {"id": "{ADAM}", "firstName": "Adam"},
                {"id": "{JKL}", "firstName": "Jacqueline"},  # league calls her Jackie
                {"id": "{RGR}", "firstName": "Roger"},  # same person as Mitch
            ],
            "draftDetail": {"picks": [{"teamId": 1, "playerId": 100, "bidAmount": 54}]},
            "teams": [
                {
                    "id": 1,
                    "name": "Take Mahomes Tonight",
                    "primaryOwner": "{ADAM}",
                    "rankCalculatedFinal": 2,
                    "record": {
                        "overall": {
                            "wins": 9,
                            "losses": 5,
                            "ties": 0,
                            "pointsFor": 1755.4,
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
                                        "fullName": "Waiver Guy",
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
                    "name": "Blood Sweat Beers",
                    "primaryOwner": "{JKL}",
                    "rankCalculatedFinal": 1,
                    "record": {
                        "overall": {
                            "wins": 8,
                            "losses": 6,
                            "ties": 0,
                            "pointsFor": 1831,
                        }
                    },
                    "roster": {"entries": []},
                },
                {
                    "id": 3,
                    "name": "Don't Cook the Lamb",
                    "primaryOwner": "{RGR}",
                    "rankCalculatedFinal": 3,
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


def test_owner_names_resolved_from_members_with_overrides():
    season, unknown = season_api_to_season(_api())
    owners = {t.team_name: t.owner for t in season.standings}
    assert owners["Take Mahomes Tonight"] == "Adam"
    assert owners["Blood Sweat Beers"] == "Jackie"  # Jacqueline -> Jackie
    assert owners["Don't Cook the Lamb"] == "Mitch"  # Roger -> Mitch
    assert unknown == []


def test_headline_draft_join_and_pf_tiebreak():
    season, _ = season_api_to_season(_api())
    assert season.champion.owner == "Jackie"  # final_rank 1
    assert season.runner_up.owner == "Adam"  # final_rank 2
    # best record: two 9-5 teams, points-for breaks the tie (Adam 1755 > Mitch 1700)
    assert season.best_record.team_name == "Take Mahomes Tonight"
    assert season.best_record.record == "9-5"
    mcc = season.standings[0].roster[0]
    assert mcc.position == "RB" and mcc.nfl_team == "SF" and mcc.slot == "RB"
    assert mcc.acquisition == "DRAFTED" and mcc.draft_price == 54
    assert season.standings[0].points_for == 1755.4
    assert season.standings[0].roster[1].acquisition == "ADDED"  # waiver add


def test_2022_keeps_split_title():
    season, _ = season_api_to_season(_api(season_id=2022))
    assert season.shared_title is True
    assert season.note == "SPLIT TITLE"


def test_empty_teams_raises():
    with pytest.raises(ValueError):
        season_api_to_season([{"seasonId": 2030, "members": [], "teams": []}])
