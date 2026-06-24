"""Add (or update) one completed ESPN season in the league-history archive.

Run at the end of each season:

    PYTHONPATH=. uv run python utils/add_espn_season.py 2026

It fetches that season from ESPN's read API and splices it directly into
``docs/data/league_history.json`` (adding the year, or replacing it if already
present), the copy published to GitHub Pages. Members are stored by first name
only.

Private leagues require your ESPN auth cookies. Grab them from a logged-in
browser (DevTools -> Application -> Cookies -> fantasy.espn.com) and export:

    export ESPN_S2='AEB...long...'
    export ESPN_SWID='{XXXXXXXX-XXXX-...}'

Owners come from each member's ESPN first name. If the league calls someone by a
different name, add an override to ``ESPN_NAME_OVERRIDES`` in
``src/espn_history.py``.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from src.espn_history import season_api_to_season
from src.models.league_history import LeagueHistory

BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "docs" / "data" / "league_history.json"
DEFAULT_LEAGUE_ID = 577910


def fetch_season(year: int, league_id: int) -> list | dict:
    url = (
        "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/leagueHistory/"
        f"{league_id}?seasonId={year}&view=mTeam&view=mRoster&view=mDraftDetail"
    )
    headers = {
        "x-fantasy-platform": "kona",
        "User-Agent": "Mozilla/5.0 league-history-updater",
    }
    s2, swid = os.environ.get("ESPN_S2"), os.environ.get("ESPN_SWID")
    if s2 and swid:
        headers["Cookie"] = f"espn_s2={s2}; SWID={swid}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("year", type=int, help="season year to add/update")
    ap.add_argument("--league-id", type=int, default=DEFAULT_LEAGUE_ID)
    args = ap.parse_args(argv)

    try:
        api = fetch_season(args.year, args.league_id)
    except urllib.error.HTTPError as e:
        raise SystemExit(
            f"ESPN API returned HTTP {e.code}. If this is a private league, set "
            "ESPN_S2 and ESPN_SWID (see this script's header)."
        )
    except urllib.error.URLError as e:
        raise SystemExit(f"Could not reach ESPN: {e.reason}")

    try:
        season = season_api_to_season(api)
    except ValueError as e:
        raise SystemExit(str(e))

    history = (
        LeagueHistory.model_validate_json(OUT.read_text())
        if OUT.exists()
        else LeagueHistory()
    )
    existed = any(s.year == season.year for s in history.seasons)
    seasons = [s for s in history.seasons if s.year != season.year]
    seasons.append(season)
    seasons.sort(key=lambda s: s.year, reverse=True)
    history = LeagueHistory(seasons=seasons)

    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(history.model_dump_json(indent=2))
    try:  # validate the temp file by reloading it before the atomic swap
        LeagueHistory.model_validate_json(tmp.read_text())
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(OUT)

    print(
        f"{'Updated' if existed else 'Added'} {season.year} in {OUT} "
        f"({len(history.seasons)} seasons total)"
    )
    print(f"  champion: {season.champion.team_name} ({season.champion.owner})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
