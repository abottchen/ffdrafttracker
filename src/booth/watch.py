"""Event detection for the booth watch loop.

The booth should run a commentary segment on *real* draft events — a new nominee
or a completed pick — but NOT on every bid. Bids bump the draft-state ``version``
(and ``nominated.current_bid`` / ``current_bidder_id``), so watching ``version``
alone thrashes during a bidding war and no segment ever finishes.

``event_key`` collapses bid-only changes: it changes only when the nominee or the
latest pick changes, so the watch loop stays quiet through a bidding war and fires
once when the nominee goes up and again when the pick completes.

Run as a module to print the current event key — or, with ``--tick``, the full
booth tick (event key + lull phase) — for the watch loop::

    python -m src.booth.watch [--data-dir DIR]  # -> "<nominee_id|none>:<max_pick_id>"
    python -m src.booth.watch --tick [--since EPOCH]  # -> "<event_key>#<lull_phase>"

``--since`` is the booth's arm time (epoch seconds); it floors the lull clock so
a booth started on an already-stale ``draft_state.json`` doesn't inherit dead air
it never watched.
"""

from __future__ import annotations

import argparse
import time
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


DEFAULT_IDLE_THRESHOLD = 120  # seconds of dead air before the first musing
DEFAULT_EASTER_THRESHOLD = 900  # 15 min of dead air -> the long-lull easter egg
DEFAULT_MUSING_CAP = 3  # retrospective musings per lull before going silent


def lull_phase(
    state: DraftState,
    dead_seconds: float,
    *,
    idle_threshold: int = DEFAULT_IDLE_THRESHOLD,
    easter_threshold: int = DEFAULT_EASTER_THRESHOLD,
    cap: int = DEFAULT_MUSING_CAP,
) -> str:
    """The lull phase for the booth tick.

    Returns ``"0"`` (no musing), ``"1"``..``"<cap>"`` (retrospective musing
    stages, one per ``idle_threshold`` seconds, saturating at ``cap``), or
    ``"eeN"`` (the off-topic long-lull easter egg, ``N`` = number of
    ``easter_threshold`` steps elapsed).

    ``dead_seconds`` is time since the last real draft event — the caller passes
    ``now - mtime(draft_state.json)``. A live nominee, too-little draft history
    (``picks_made < num_teams``), or too short a lull all pin the phase to
    ``"0"``. The easter egg is checked before the musing bucket so it wins once
    the draft has truly stalled.
    """
    if state.nominated is not None:
        return "0"
    picks_made = sum(len(team.picks) for team in state.teams)
    num_teams = max(len(state.teams), 1)
    if picks_made < num_teams:
        return "0"
    if dead_seconds < idle_threshold:
        return "0"
    if dead_seconds >= easter_threshold:
        return f"ee{int(dead_seconds // easter_threshold)}"
    return str(min(cap, int(dead_seconds // idle_threshold)))


def booth_tick(
    state: DraftState,
    dead_seconds: float,
    *,
    idle_threshold: int = DEFAULT_IDLE_THRESHOLD,
    easter_threshold: int = DEFAULT_EASTER_THRESHOLD,
    cap: int = DEFAULT_MUSING_CAP,
) -> str:
    """The watch signal: ``"<event_key>#<lull_phase>"``.

    The event-key half changes on a real draft event; the phase half changes as
    a lull deepens. The threshold args are forwarded to :func:`lull_phase`.
    """
    phase = lull_phase(
        state,
        dead_seconds,
        idle_threshold=idle_threshold,
        easter_threshold=easter_threshold,
        cap=cap,
    )
    return f"{event_key(state)}#{phase}"


def effective_dead(
    now: float, state_mtime: float, started_at: float | None = None
) -> float:
    """Lull-clock idle seconds: ``now - max(state_mtime, started_at)``.

    ``state_mtime`` is the mtime of ``draft_state.json`` (the last real draft
    event). Flooring at ``started_at`` — the booth's arm time — keeps a booth
    started on an already-stale file from inheriting dead air it never watched;
    without it, a fresh start could jump straight into the easter-egg band and
    skip the normal musing stages entirely.
    """
    floor = state_mtime if started_at is None else max(state_mtime, started_at)
    return now - floor


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print the booth watch event key.")
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory holding draft_state.json (default: data)",
    )
    parser.add_argument(
        "--tick",
        action="store_true",
        help="Print the booth tick (<event_key>#<lull_phase>) for lull detection.",
    )
    parser.add_argument(
        "--since",
        type=float,
        default=None,
        help=(
            "Booth arm time (epoch seconds). Floors the lull clock so a stale "
            "draft_state.json at startup doesn't inherit pre-start dead air."
        ),
    )
    args = parser.parse_args(argv)
    state_path = Path(args.data_dir) / "draft_state.json"
    state = DraftState.load_from_file(state_path)
    if args.tick:
        dead = effective_dead(time.time(), state_path.stat().st_mtime, args.since)
        print(booth_tick(state, dead))
    else:
        print(event_key(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
