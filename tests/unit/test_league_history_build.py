"""Tests for the league-history transform/build."""

import re
from pathlib import Path

import pytest

from src.league_history_build import (
    _best_record_team,
    _season_from_standings,
    _team_seasons_espn,
    _team_seasons_yahoo,
)
from src.models.league_history import LeagueHistory

DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "league_history.json"


def _espn_raw():
    return {
        "year": 2022,
        "teams": [
            {
                "source_team_id": 2,
                "team_name": "Take Mahomes Tonight",
                "owner": "Adam",
                "wins": 9,
                "losses": 5,
                "ties": 0,
                "final_rank": 1,
                "roster": [
                    {
                        "player_name": "Josh Jacobs",
                        "position": "RB",
                        "nfl_team": "LV",
                        "slot": "RB",
                        "acquisition": "DRAFTED",
                        "draft_price": 41,
                        "draft_pick": None,
                    }
                ],
            },
            {
                "source_team_id": 5,
                "team_name": "My Kupp Runnith Over",
                "owner": "Mitch",
                "wins": 10,
                "losses": 4,
                "ties": 0,
                "final_rank": 2,
                "roster": [],
            },
        ],
    }


def test_espn_headline_and_2022_shared_title():
    teams = _team_seasons_espn(_espn_raw())
    season = _season_from_standings(
        year=2022, source="espn", draft_type="auction", teams=teams
    )
    assert season.champion.owner == "Adam"
    assert season.runner_up.owner == "Mitch"
    assert season.shared_title is True
    assert season.note == "SPLIT TITLE"
    # roster draft price preserved
    assert season.standings[0].roster[0].draft_price == 41


def test_best_record_uses_win_pct():
    raw = {
        "year": 2009,
        "teams": [
            {
                "source_team_id": 1,
                "team_name": "Dwarf Tossers",
                "wins": 9,
                "losses": 5,
                "ties": 0,
                "final_rank": None,
                "roster": [],
            },
            {
                "source_team_id": 2,
                "team_name": "Blood Sweat & Beers",
                "wins": 9,
                "losses": 4,
                "ties": 0,
                "final_rank": 1,
                "roster": [],
            },
        ],
    }
    unresolved = set()
    teams = _team_seasons_yahoo(raw, unresolved)
    best = _best_record_team(teams)
    assert best.team_name == "Blood Sweat & Beers"  # 9-4 beats 9-5


def test_yahoo_owner_mapping_and_unresolved():
    raw = {
        "year": 2011,
        "teams": [
            {
                "source_team_id": 10,
                "team_name": "Mjr. Bwl. Mvmnet",
                "manager_hint": "Steve",
                "wins": 10,
                "losses": 3,
                "ties": 0,
                "final_rank": 1,
                "roster": [],
            },
            {
                "source_team_id": 6,
                "team_name": "Totally Unmapped Team FC",
                "manager_hint": "--hidden--",
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "final_rank": 3,
                "roster": [],
            },
        ],
    }
    unresolved = set()
    teams = _team_seasons_yahoo(raw, unresolved)
    owners = {t.team_name: t.owner for t in teams}
    assert owners["Mjr. Bwl. Mvmnet"] == "Steve"
    assert owners["Totally Unmapped Team FC"] == "UNKNOWN"
    assert any("Totally Unmapped Team FC" in u for u in unresolved)


@pytest.mark.skipif(not DATA_FILE.exists(), reason="archive not built")
def test_built_archive_leaderboard_and_pii_clean():
    history = LeagueHistory.model_validate_json(DATA_FILE.read_text())
    counts = {c.owner: c.titles for c in history.championship_counts()}
    assert counts["Greg"] == 6
    assert counts["Adam"] == 4
    assert counts["Steve"] == 4
    assert counts["Raman"] == 3
    assert counts["Mitch"] == 1  # 2022 split-title credit
    # Privacy: no emails or ESPN GUIDs leaked into the committed file
    blob = DATA_FILE.read_text()
    assert "@" not in blob
    assert not re.search(r"\{[0-9A-F]{8}-[0-9A-F]{4}-", blob)
