"""Unit tests for the Analyst Booth comment log.

Schema validation, the single-write atomic append, and the defensive reader
that drops a deliberately-truncated trailing line. Themed (loosely) after the
booth's own personas riffing on a Rick and Morty draft.
"""

import json

import pytest
from pydantic import ValidationError

from src.booth.log import (
    AnalystComment,
    append_comment,
    read_comments,
)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
class TestSchema:
    def test_valid_comment(self):
        c = AnalystComment(
            ts="2026-06-20T03:42:55Z",
            state_version=147,
            persona="Kiper",
            text="Sanchez was my QB1 and he goes for $30 — highway robbery.",
        )
        assert c.persona == "Kiper"
        assert c.state_version == 147

    def test_host_persona_allowed(self):
        c = AnalystComment(
            ts="2026-06-20T03:42:55Z",
            state_version=1,
            persona="Eisen",
            text="Welcome to the booth.",
        )
        assert c.persona == "Eisen"

    def test_unknown_persona_rejected(self):
        with pytest.raises(ValidationError):
            AnalystComment(
                ts="2026-06-20T03:42:55Z",
                state_version=1,
                persona="Squanchy",
                text="schwifty take",
            )

    def test_empty_text_rejected(self):
        with pytest.raises(ValidationError):
            AnalystComment(
                ts="2026-06-20T03:42:55Z",
                state_version=1,
                persona="McAfee",
                text="   ",
            )


# ---------------------------------------------------------------------------
# Append
# ---------------------------------------------------------------------------
class TestAppend:
    def test_append_returns_validated_comment(self, tmp_path):
        path = tmp_path / "analyst-comments.jsonl"
        c = append_comment("Kimes", "Negative VOR, hard pass.", 50, path=path)
        assert c.persona == "Kimes"
        assert c.state_version == 50
        assert c.text == "Negative VOR, hard pass."

    def test_ts_stamped_by_writer_iso_utc(self, tmp_path):
        path = tmp_path / "log.jsonl"
        c = append_comment("Schefter", "Sources say it's a reach.", 7, path=path)
        # ISO-8601 UTC with trailing Z, second precision.
        assert c.ts.endswith("Z")
        assert "T" in c.ts
        assert len(c.ts) == len("2026-06-20T03:42:55Z")

    def test_append_writes_one_terminated_line(self, tmp_path):
        path = tmp_path / "log.jsonl"
        append_comment("Booger", "As a guy who played, I love the burst.", 9, path=path)
        text = path.read_text()
        assert text.endswith("\n")
        assert text.count("\n") == 1
        record = json.loads(text.strip())
        assert record["persona"] == "Booger"

    def test_appends_accumulate_in_order(self, tmp_path):
        path = tmp_path / "log.jsonl"
        append_comment("Kiper", "first", 1, path=path)
        append_comment("Kimes", "second", 1, path=path)
        append_comment("McAfee", "third", 2, path=path)
        lines = path.read_text().splitlines()
        assert [json.loads(line_)["text"] for line_ in lines] == [
            "first",
            "second",
            "third",
        ]

    def test_append_creates_parent_dir(self, tmp_path):
        path = tmp_path / "nested" / "deeper" / "log.jsonl"
        append_comment("Eisen", "Booth is live.", 1, path=path)
        assert path.exists()


# ---------------------------------------------------------------------------
# Read (defensive)
# ---------------------------------------------------------------------------
class TestRead:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "log.jsonl"
        append_comment("Kiper", "RB2 on my board.", 10, path=path)
        append_comment("Kimes", "Efficiency says otherwise.", 10, path=path)
        records = read_comments(path)
        assert [r.persona for r in records] == ["Kiper", "Kimes"]
        assert records[0].text == "RB2 on my board."

    def test_missing_file_returns_empty(self, tmp_path):
        assert read_comments(tmp_path / "nope.jsonl") == []

    def test_empty_file_returns_empty(self, tmp_path):
        path = tmp_path / "log.jsonl"
        path.write_text("")
        assert read_comments(path) == []

    def test_drops_unterminated_trailing_line(self, tmp_path):
        path = tmp_path / "log.jsonl"
        committed = json.dumps(
            {"ts": "t1", "state_version": 1, "persona": "Kiper", "text": "committed"}
        )
        partial = json.dumps(
            {"ts": "t2", "state_version": 2, "persona": "Kimes", "text": "torn"}
        )
        # Final line is NOT newline-terminated -> not yet committed.
        path.write_text(committed + "\n" + partial)
        records = read_comments(path)
        assert len(records) == 1
        assert records[0].text == "committed"

    def test_drops_truncated_partial_json(self, tmp_path):
        path = tmp_path / "log.jsonl"
        good = json.dumps(
            {"ts": "t1", "state_version": 1, "persona": "McAfee", "text": "HYPE"}
        )
        # A torn write: half a JSON object, no newline.
        path.write_text(good + '\n{"ts":"t2","state_versi')
        records = read_comments(path)
        assert len(records) == 1
        assert records[0].text == "HYPE"

    def test_keeps_terminated_last_line(self, tmp_path):
        path = tmp_path / "log.jsonl"
        a = json.dumps(
            {"ts": "t1", "state_version": 1, "persona": "Kiper", "text": "a"}
        )
        b = json.dumps(
            {"ts": "t2", "state_version": 1, "persona": "Kimes", "text": "b"}
        )
        path.write_text(a + "\n" + b + "\n")
        records = read_comments(path)
        assert [r.text for r in records] == ["a", "b"]

    def test_skips_invalid_persona_line(self, tmp_path):
        path = tmp_path / "log.jsonl"
        good = json.dumps(
            {"ts": "t1", "state_version": 1, "persona": "Kimes", "text": "valid"}
        )
        bad = json.dumps(
            {"ts": "t2", "state_version": 1, "persona": "Squanchy", "text": "nope"}
        )
        path.write_text(good + "\n" + bad + "\n")
        records = read_comments(path)
        assert [r.persona for r in records] == ["Kimes"]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
class TestCli:
    def test_append_via_cli(self, tmp_path, capsys):
        from src.booth.log import main

        path = tmp_path / "log.jsonl"
        rc = main(
            [
                "append",
                "--persona",
                "Kiper",
                "--state-version",
                "12",
                "--text",
                "Big board says value.",
                "--path",
                str(path),
            ]
        )
        assert rc == 0
        out = json.loads(capsys.readouterr().out.strip())
        assert out["persona"] == "Kiper"
        assert out["state_version"] == 12
        assert read_comments(path)[0].text == "Big board says value."

    def test_read_via_cli(self, tmp_path, capsys):
        from src.booth.log import main

        path = tmp_path / "log.jsonl"
        append_comment("Kimes", "line one", 1, path=path)
        append_comment("McAfee", "line two", 2, path=path)
        rc = main(["read", "--path", str(path)])
        assert rc == 0
        lines = capsys.readouterr().out.strip().splitlines()
        assert json.loads(lines[0])["text"] == "line one"
        assert json.loads(lines[1])["text"] == "line two"
