"""Append-only commentary log for the Analyst Booth.

The log is JSON Lines (``data/analyst-comments.jsonl``): one self-contained
``AnalystComment`` per line. The write path appends the complete ``json + "\\n"``
in a single ``write()`` in ``"a"`` mode — the newline is the commit marker, so a
crash mid-write leaves an un-terminated (uncommitted) tail rather than a
corrupt record. The read path drops that tail defensively, keeping every
downstream consumer naive.

It assumes a single writer (no concurrent interleaving) and is run as a module
so every line is schema-checked and server-timestamped::

    python -m src.booth.log append --persona Kiper --state-version 147 \\
        --text "Bijan was RB2 on my board and he goes for $52 — that's a heist."
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, field_validator

DEFAULT_LOG_PATH = Path("data") / "analyst-comments.jsonl"


class AnalystComment(BaseModel):
    """One line of booth commentary.

    ``ts`` is stamped by the writer (never the LLM); ``state_version`` is the
    ``draft_state`` version the comment is about, so the UI can group a pick's
    segment and the slice's ``recent_log`` stays filterable.
    """

    ts: str  # ISO-8601 UTC, stamped by the writer
    state_version: int
    persona: str
    text: str

    @field_validator("persona", "text")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value


def _utc_now_iso() -> str:
    """Current UTC time as ISO-8601 with a trailing ``Z`` (no microseconds)."""
    return datetime.now(UTC).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_comment(
    persona: str,
    text: str,
    state_version: int,
    path: Path = DEFAULT_LOG_PATH,
) -> AnalystComment:
    """Build, validate, and atomically append a comment line.

    Stamps ``ts`` to now (UTC), validates the schema, then writes the complete
    ``json + "\\n"`` in a single ``write()`` in ``"a"`` mode. The newline is the
    commit marker; fsync is intentionally not used (durability, not atomicity).
    """
    comment = AnalystComment(
        ts=_utc_now_iso(),
        state_version=state_version,
        persona=persona,
        text=text,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    line = comment.model_dump_json() + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)  # single write; newline commits the line
    return comment


def read_comments(path: Path = DEFAULT_LOG_PATH) -> list[AnalystComment]:
    """Parse the log line-by-line, dropping the trailing-edge concern once.

    Returns clean, validated records. A non-newline-terminated trailing line is
    treated as "not yet committed" and dropped; any line that fails to parse or
    validate is also skipped, so every consumer stays naive.
    """
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8")
    if not text:
        return []

    lines = text.split("\n")
    # split on "\n": a terminated file ends with "" (drop it); an un-terminated
    # file ends with the partial line (drop it — not yet committed).
    if text.endswith("\n"):
        lines = lines[:-1]
    elif lines:
        lines = lines[:-1]

    records: list[AnalystComment] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            records.append(AnalystComment.model_validate_json(line))
        except Exception:
            # Unparseable / invalid line — skip it (defensive, never crash).
            continue
    return records


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyst Booth comment log.")
    sub = parser.add_subparsers(dest="command", required=True)

    ap = sub.add_parser("append", help="Append a validated comment line.")
    ap.add_argument("--persona", required=True, help="The speaker's name.")
    ap.add_argument(
        "--state-version",
        type=int,
        required=True,
        help="The draft_state version this comment is about.",
    )
    ap.add_argument("--text", required=True, help="The 1-2 sentence line.")
    ap.add_argument(
        "--path",
        default=str(DEFAULT_LOG_PATH),
        help=f"Log path (default: {DEFAULT_LOG_PATH}).",
    )

    rp = sub.add_parser("read", help="Print committed comments as JSON lines.")
    rp.add_argument(
        "--path",
        default=str(DEFAULT_LOG_PATH),
        help=f"Log path (default: {DEFAULT_LOG_PATH}).",
    )

    args = parser.parse_args(argv)

    if args.command == "append":
        comment = append_comment(
            persona=args.persona,
            text=args.text,
            state_version=args.state_version,
            path=Path(args.path),
        )
        print(comment.model_dump_json())
        return 0

    if args.command == "read":
        for comment in read_comments(Path(args.path)):
            print(comment.model_dump_json())
        return 0

    parser.error("unknown command")  # pragma: no cover
    return 2  # pragma: no cover


if __name__ == "__main__":
    raise SystemExit(main())
