"""Event detection for the booth watch loop.

The booth should run a commentary segment on *real* draft events — a new nominee
or a completed pick — but NOT on every bid. Bids bump the draft-state ``version``
(and ``nominated.current_bid`` / ``current_bidder_id``), so watching ``version``
alone thrashes during a bidding war and no segment ever finishes.

``event_key`` collapses bid-only changes: it changes only when the nominee or the
latest pick changes, so the watch loop stays quiet through a bidding war and fires
once when the nominee goes up and again when the pick completes.

Run as a module to print the current event key for the watch loop::

    python -m src.booth.watch [--data-dir DIR]   # -> "<nominee_id|none>:<max_pick_id>"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.models import DraftState


def event_key(state: DraftState) -> str:
    """Signature that changes on a new nominee or completed pick, but NOT on a bid.

    A bid only moves ``nominated.current_bid`` / ``current_bidder_id`` — both
    deliberately excluded — so a bidding war does not change the key.
    """
    nominee = state.nominated.player_id if state.nominated else "none"
    last_pick = max(
        (pick.pick_id for team in state.teams for pick in team.picks),
        default=0,
    )
    return f"{nominee}:{last_pick}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print the booth watch event key.")
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory holding draft_state.json (default: data)",
    )
    args = parser.parse_args(argv)
    state = DraftState.load_from_file(Path(args.data_dir) / "draft_state.json")
    print(event_key(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
