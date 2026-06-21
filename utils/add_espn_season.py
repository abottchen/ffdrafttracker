"""Add (or refresh) one completed ESPN season in the league-history archive.

Run at the end of each season:

    PYTHONPATH=. uv run python utils/add_espn_season.py 2026

It fetches that season from ESPN's read API, writes the scrubbed raw capture to
``data/raw_history/espn/<year>.json`` (first names only), and rebuilds
``data/league_history.json``. Re-running a year overwrites it (also handy for
back-filling points-for into older ESPN seasons).

Private leagues require your ESPN auth cookies. Grab them from a logged-in
browser (DevTools -> Application -> Cookies -> fantasy.espn.com) and export:

    export ESPN_S2='AEB...long...'
    export ESPN_SWID='{XXXXXXXX-XXXX-...}'

If a new manager joined, the script prints their ESPN member GUID -- add it to
``data/history_owner_map.json`` under ``"espn"`` (GUID -> first name) and re-run.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from src.espn_history import season_api_to_raw
from src.league_history_build import build

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw_history"
OWNER_MAP = BASE / "data" / "history_owner_map.json"
OUT = BASE / "data" / "league_history.json"
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
    ap.add_argument("year", type=int, help="season year to add/refresh")
    ap.add_argument("--league-id", type=int, default=DEFAULT_LEAGUE_ID)
    ap.add_argument(
        "--no-rebuild",
        action="store_true",
        help="only write the raw capture; skip rebuilding league_history.json",
    )
    args = ap.parse_args(argv)

    if not OWNER_MAP.exists():
        raise SystemExit(
            f"Owner map not found: {OWNER_MAP}\n"
            "It maps ESPN member GUIDs to first names (gitignored)."
        )
    owner_map = json.loads(OWNER_MAP.read_text()).get("espn", {})

    try:
        api = fetch_season(args.year, args.league_id)
    except urllib.error.HTTPError as e:
        raise SystemExit(
            f"ESPN API returned HTTP {e.code}. If this is a private league, set "
            "ESPN_S2 and ESPN_SWID (see this script's header)."
        )
    except urllib.error.URLError as e:
        raise SystemExit(f"Could not reach ESPN: {e.reason}")

    raw, unknown = season_api_to_raw(api, owner_map)
    if not raw["teams"]:
        raise SystemExit(
            f"No teams returned for {args.year}. Is the season complete and the "
            f"league id ({args.league_id}) correct?"
        )

    dest = RAW / "espn" / f"{args.year}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(raw, indent=2))
    print(f"Wrote {dest} ({len(raw['teams'])} teams)")
    champ = next((t for t in raw["teams"] if t.get("final_rank") == 1), None)
    if champ:
        print(f"  champion: {champ['team_name']} ({champ['owner']})")
    if unknown:
        print(
            "  NEW unmapped ESPN member GUID(s) — add to "
            "data/history_owner_map.json['espn']:"
        )
        for g in unknown:
            print(f"    {g}")

    if args.no_rebuild:
        return 0

    history, unresolved = build(RAW)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(history.model_dump_json(indent=2))
    tmp.replace(OUT)
    print(f"Rebuilt {OUT} ({len(history.seasons)} seasons)")
    if unresolved:
        print(f"  note: {len(unresolved)} unresolved Yahoo owner(s) still present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
