"""Guard: published league-history archives must never leak owner last names.

The archives in ``docs/data/`` are served publicly via GitHub Pages. Owner
identifiers are first-name/handle only (e.g. "Adam", "th3", "unk1"); a value
containing a space implies a "First Last" leak. NFL player names (full names in
rosters) are public data and intentionally not checked.
"""

import json
from pathlib import Path

import pytest

DOCS_DATA = Path(__file__).resolve().parents[2] / "docs" / "data"


def _league_history_owners() -> set[str]:
    data = json.loads((DOCS_DATA / "league_history.json").read_text())
    owners: set[str] = set()
    for season in data.get("seasons", []):
        for team in season.get("standings", []):
            owners.add(team.get("owner"))
        for key in ("champion", "runner_up", "best_record"):
            entry = season.get(key)
            if entry:
                owners.add(entry.get("owner"))
    return {o for o in owners if o}


def _auction_owners() -> set[str]:
    data = json.loads((DOCS_DATA / "auction_prices.json").read_text())
    owners: set[str] = set()
    for season in data.get("seasons", {}).values():
        owners.update((season.get("owners") or {}).keys())
    return owners


@pytest.mark.parametrize("owner", sorted(_league_history_owners() | _auction_owners()))
def test_owner_identifier_has_no_last_name(owner: str) -> None:
    assert " " not in owner, (
        f"Owner identifier {owner!r} contains a space — possible last-name leak "
        f"into the publicly-served docs/data archives."
    )
