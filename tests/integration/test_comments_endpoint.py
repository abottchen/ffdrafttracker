"""Integration tests for the GET /api/v1/comments endpoint.

The analyst booth appends JSON-Lines commentary to
``data/analyst-comments.jsonl``. This endpoint exposes those lines to the admin
and viewer pages, with a monotonic ``seq`` cursor and query-param filtering
(``since`` / ``before`` / ``limit``). Tests run against both the admin ``app``
and the read-only ``viewer_app`` mirror, using a real temp log file.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app, viewer_app


def _line(persona: str, text: str, state_version: int = 1) -> str:
    """One committed JSONL record (newline added by the writer of the file)."""
    return json.dumps(
        {
            "ts": "2026-06-20T07:34:39Z",
            "state_version": state_version,
            "persona": persona,
            "text": text,
        }
    )


def _write_log(path: Path, *records: str, terminated: bool = True) -> None:
    """Write committed records, one per line. ``terminated`` controls whether the
    final line ends in a newline (an un-terminated tail simulates a torn write)."""
    body = "\n".join(records)
    if terminated and records:
        body += "\n"
    path.write_text(body, encoding="utf-8")


@pytest.fixture(params=["admin", "viewer"])
def client(request):
    """A TestClient for each app, so every test asserts the mirror too."""
    return TestClient(app if request.param == "admin" else viewer_app)


@pytest.fixture
def log_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        path = Path(f.name)
    try:
        yield path
    finally:
        path.unlink(missing_ok=True)


def test_all_comments_returned_seq_ordered(client, log_file):
    _write_log(
        log_file,
        _line("Kiper", "first"),
        _line("Booger", "second"),
        _line("Eisen", "third"),
    )
    with patch("main.COMMENTS_FILE", log_file):
        resp = client.get("/api/v1/comments")

    assert resp.status_code == 200
    data = resp.json()
    assert [c["seq"] for c in data] == [1, 2, 3]
    assert [c["persona"] for c in data] == ["Kiper", "Booger", "Eisen"]
    assert data[0]["text"] == "first"
    assert data[0]["state_version"] == 1
    assert data[0]["ts"] == "2026-06-20T07:34:39Z"


def test_since_returns_only_newer(client, log_file):
    _write_log(
        log_file,
        _line("Kiper", "first"),
        _line("Booger", "second"),
        _line("Eisen", "third"),
    )
    with patch("main.COMMENTS_FILE", log_file):
        resp = client.get("/api/v1/comments", params={"since": 1})

    assert resp.status_code == 200
    assert [c["seq"] for c in resp.json()] == [2, 3]


def test_since_at_head_returns_empty(client, log_file):
    _write_log(log_file, _line("Kiper", "first"), _line("Booger", "second"))
    with patch("main.COMMENTS_FILE", log_file):
        resp = client.get("/api/v1/comments", params={"since": 2})

    assert resp.status_code == 200
    assert resp.json() == []


def test_limit_returns_most_recent(client, log_file):
    _write_log(
        log_file,
        _line("Kiper", "first"),
        _line("Booger", "second"),
        _line("Eisen", "third"),
    )
    with patch("main.COMMENTS_FILE", log_file):
        resp = client.get("/api/v1/comments", params={"limit": 2})

    assert resp.status_code == 200
    assert [c["seq"] for c in resp.json()] == [2, 3]


def test_before_returns_older(client, log_file):
    _write_log(
        log_file,
        _line("Kiper", "first"),
        _line("Booger", "second"),
        _line("Eisen", "third"),
    )
    with patch("main.COMMENTS_FILE", log_file):
        resp = client.get("/api/v1/comments", params={"before": 3})

    assert resp.status_code == 200
    assert [c["seq"] for c in resp.json()] == [1, 2]


def test_before_and_limit_returns_window(client, log_file):
    _write_log(log_file, *[_line("Kiper", str(i)) for i in range(1, 6)])
    with patch("main.COMMENTS_FILE", log_file):
        resp = client.get("/api/v1/comments", params={"before": 4, "limit": 2})

    assert resp.status_code == 200
    # seq < 4 -> [1,2,3]; most recent 2 -> [2,3]
    assert [c["seq"] for c in resp.json()] == [2, 3]


def test_missing_file_returns_empty_list(client):
    with patch("main.COMMENTS_FILE", Path("/tmp/does-not-exist-xyz.jsonl")):
        resp = client.get("/api/v1/comments")

    assert resp.status_code == 200
    assert resp.json() == []


def test_torn_tail_excluded_from_seq(client, log_file):
    # Two committed lines + an un-terminated partial tail (mid-write).
    _write_log(
        log_file,
        _line("Kiper", "first"),
        _line("Booger", "second"),
        '{"ts":"2026-06-20T07:35:00Z","state_version":1,"persona":"Eisen"',
        terminated=False,
    )
    with patch("main.COMMENTS_FILE", log_file):
        resp = client.get("/api/v1/comments")

    assert resp.status_code == 200
    data = resp.json()
    assert [c["seq"] for c in data] == [1, 2]


def test_limit_zero_rejected(client, log_file):
    _write_log(log_file, _line("Kiper", "first"))
    with patch("main.COMMENTS_FILE", log_file):
        resp = client.get("/api/v1/comments", params={"limit": 0})

    assert resp.status_code == 422
