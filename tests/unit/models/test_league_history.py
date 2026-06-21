"""Unit tests for the league history archive models."""

import re
from pathlib import Path

import pytest

from src.models.league_history import (
    BestRecord,
    Finisher,
    LeagueHistory,
    RosterEntry,
    SeasonResult,
    TeamSeason,
)

DATA_FILE = Path(__file__).resolve().parents[3] / "data" / "league_history.json"


def _season(year, champ, ru, *, shared=False, source="manual"):
    return SeasonResult(
        year=year,
        source=source,
        champion=Finisher(owner=champ, team_name=f"{champ} team"),
        runner_up=Finisher(owner=ru, team_name=f"{ru} team"),
        best_record=BestRecord(owner=champ, team_name=f"{champ} team", record="10-3"),
        shared_title=shared,
        note=("SPLIT TITLE" if shared else None),
    )


def test_championship_counts_credits_split_title_runner_up():
    hist = LeagueHistory(
        seasons=[
            _season(2025, "Raman", "Adam"),
            _season(2022, "Adam", "Mitch", shared=True),
        ]
    )
    counts = {c.owner: c.titles for c in hist.championship_counts()}
    assert counts["Raman"] == 1
    assert counts["Adam"] == 1
    assert counts["Mitch"] == 1  # credited via shared_title


def test_championship_counts_sorted_titles_then_recency():
    hist = LeagueHistory(
        seasons=[
            _season(2024, "Greg", "Adam"),
            _season(2023, "Greg", "Adam"),
            _season(2025, "Adam", "Greg"),
        ]
    )
    ordered = [(c.owner, c.titles) for c in hist.championship_counts()]
    assert ordered[0] == ("Greg", 2)
    assert ("Adam", 1) in ordered
    # Greg's most recent title year is recorded
    greg = next(c for c in hist.championship_counts() if c.owner == "Greg")
    assert greg.last_title_year == 2024


def test_season_field_coverage():
    # Reflection guard mirroring the DraftState serialization test, so a new
    # field can't be added without updating tests.
    expected = {
        "year",
        "champion",
        "runner_up",
        "best_record",
        "shared_title",
        "note",
        "source",
        "draft_type",
        "standings",
    }
    assert set(SeasonResult.model_fields.keys()) == expected


def test_team_season_roster_round_trip():
    ts = TeamSeason(
        source_team_id=8,
        team_name="THE NIGHTMARE",
        owner="Raman",
        wins=12,
        losses=2,
        ties=0,
        final_rank=1,
        roster=[
            RosterEntry(
                player_name="Christian McCaffrey",
                position="RB",
                nfl_team="SF",
                slot="RB",
                acquisition="DRAFTED",
                draft_price=54,
            )
        ],
    )
    again = TeamSeason.model_validate_json(ts.model_dump_json())
    assert again.roster[0].draft_price == 54
    assert again.owner == "Raman"


@pytest.mark.skipif(not DATA_FILE.exists(), reason="archive not present")
def test_committed_archive_leaderboard_and_pii_clean():
    history = LeagueHistory.model_validate_json(DATA_FILE.read_text())
    counts = {c.owner: c.titles for c in history.championship_counts()}
    assert counts["Greg"] == 6
    assert counts["Adam"] == 4
    assert counts["Steve"] == 4
    assert counts["Raman"] == 3
    assert counts["Mitch"] == 1  # 2022 split-title credit
    # Privacy: no emails or ESPN GUIDs leaked into the committed file.
    blob = DATA_FILE.read_text()
    assert "@" not in blob
    assert not re.search(r"\{[0-9A-F]{8}-[0-9A-F]{4}-", blob)
