"""Build data/league_history.json from the raw ESPN/Yahoo captures.

Usage: uv run python utils/build_league_history.py
"""

from __future__ import annotations

from pathlib import Path

from src.league_history_build import build, reconcile

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw_history"
OUT = BASE / "data" / "league_history.json"


def main() -> int:
    history, unresolved = build(RAW)

    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(history.model_dump_json(indent=2))
    tmp.replace(OUT)

    print(f"Wrote {OUT} ({len(history.seasons)} seasons)")
    print()
    print("Most Championships (derived):")
    for c in history.championship_counts():
        print(f"  {c.owner:<8} {c.titles}  (last {c.last_title_year})")
    print()

    disagreements = reconcile(history)
    print(
        f"Pre-2012 reconciliation vs manual table: {len(disagreements)} difference(s)"
    )
    for m in disagreements:
        print(f"  - {m}")
    print()

    print(f"Unresolved Yahoo owners ({len(unresolved)}) -- need confirmation:")
    for u in unresolved:
        print(f"  - {u}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
