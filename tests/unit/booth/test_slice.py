"""Unit tests for the Analyst Booth slice builder.

A tiny self-contained universe in a tempfile data dir, themed (loosely) after
Rick and Morty so the fixtures are fun to read. Players are NFL caricatures of
the gang; owners are the families running fantasy teams.
"""

import json
from pathlib import Path

import pytest

from src.booth.slice import (
    _needs,
    build_slice,
    production_score,
    render_brief,
)


# ---------------------------------------------------------------------------
# Fixture universe
# ---------------------------------------------------------------------------
# Players: a QB, two RBs, two WRs, a TE, a kicker, plus a rookie WR with no
# prior production. ids are arbitrary.
def _player(pid, first, last, team, position):
    return {
        "id": pid,
        "first_name": first,
        "last_name": last,
        "team": team,
        "position": position,
    }


PLAYERS = [
    _player(10, "Rick", "Sanchez", "KC", "QB"),
    _player(20, "Morty", "Smith", "SF", "RB"),
    _player(21, "Summer", "Smith", "DAL", "RB"),
    _player(30, "Birdperson", "Phoenix", "PHI", "WR"),
    _player(31, "Squanchy", "Cat", "MIA", "WR"),
    _player(40, "Mr", "Poopybutthole", "BUF", "TE"),
    _player(50, "Tiny", "Rick", "GB", "K"),
    # Rookie WR: present in players.json, absent from player_stats.json.
    _player(99, "Noob", "Noob", "NYG", "WR"),
]

# Stats keyed by player_id string. The rookie (99) is deliberately ABSENT.
# Player 21 (Summer) is present but with an empty stat line -> also a rookie.
PLAYER_STATS = {
    "10": {
        "bye_week": 6,
        "position": "QB",
        "team": "KC",
        "passing": {
            "completions": "400",
            "attempts": "600",
            "pct": "66.7",
            "yards": "5000",
            "avg": "8.3",
            "tds": "40",
            "ints": "10",
            "sacks": "20",
            "rating": "110.0",
        },
        "stats_summary": "400/600 5000yds 40TD 10INT",
    },
    "20": {
        "bye_week": 9,
        "position": "RB",
        "team": "SF",
        "rushing": {
            "carries": "300",
            "yards": "1500",
            "avg": "5.0",
            "tds": "15",
            "long": "70",
            "fumbles": "1",
        },
        "receiving": {
            "receptions": "50",
            "targets": "60",
            "yards": "400",
            "avg": "8.0",
            "tds": "2",
            "long": "40",
            "fumbles": "0",
        },
        "stats_summary": "Rush: 1500yds 15TD | Rec: 50rec 400yds 2TD",
    },
    "21": {
        # Present but empty -> no production block -> treated as rookie.
        "bye_week": 7,
        "position": "RB",
        "team": "DAL",
        "stats_summary": None,
    },
    "30": {
        "bye_week": 5,
        "position": "WR",
        "team": "PHI",
        "receiving": {
            "receptions": "100",
            "targets": "140",
            "yards": "1400",
            "avg": "14.0",
            "tds": "12",
            "long": "60",
            "fumbles": "0",
        },
        "stats_summary": "100rec 1400yds 12TD",
    },
    "31": {
        "bye_week": 11,
        "position": "WR",
        "team": "MIA",
        "receiving": {
            "receptions": "40",
            "targets": "70",
            "yards": "500",
            "avg": "12.5",
            "tds": "3",
            "long": "45",
            "fumbles": "1",
        },
        "stats_summary": "40rec 500yds 3TD",
    },
    "40": {
        "bye_week": 12,
        "position": "TE",
        "team": "BUF",
        "receiving": {
            "receptions": "70",
            "targets": "90",
            "yards": "800",
            "avg": "11.4",
            "tds": "6",
            "long": "30",
            "fumbles": "0",
        },
        "stats_summary": "70rec 800yds 6TD",
    },
    "50": {
        "bye_week": 8,
        "position": "K",
        "team": "GB",
        "kicking": {
            "fgm": "35",
            "fga": "40",
            "fg_pct": "87.5",
            "long": "58",
            "xpm": "45",
            "xpa": "45",
            "points": "150",
        },
        "stats_summary": "35/40FG 150pts",
    },
}

OWNERS = [
    {"id": 1, "owner_name": "Rick", "team_name": "Wubba Lubba Dub Dubs"},
    {"id": 2, "owner_name": "Jerry", "team_name": "Plumbuses United"},
    {"id": 3, "owner_name": "Beth", "team_name": "Space Beth Spacers"},
]

CONFIG = {
    "initial_budget": 200,
    "min_bid": 1,
    "position_maximums": {"QB": 3, "RB": 8, "WR": 8, "TE": 3, "K": 3, "D/ST": 3},
    "total_rounds": 17,
    "data_directory": "data",
    "draft_year": 2026,
}


def _base_state():
    """A state where Rick's team has drafted two players (one is the last pick).

    available: everyone not yet drafted. next_to_nominate = Beth (owner 3),
    who has an empty roster and a full budget.
    """
    drafted = {10, 30}  # Rick(QB) and Birdperson(WR) are off the board
    available = [p["id"] for p in PLAYERS if p["id"] not in drafted]
    return {
        "nominated": None,
        "available_player_ids": available,
        "teams": [
            {
                "owner_id": 1,
                "budget_remaining": 150,
                "picks": [
                    {"pick_id": 1, "player_id": 10, "owner_id": 1, "price": 30},
                    {"pick_id": 2, "player_id": 30, "owner_id": 1, "price": 45},
                ],
            },
            {"owner_id": 2, "budget_remaining": 200, "picks": []},
            {"owner_id": 3, "budget_remaining": 200, "picks": []},
        ],
        "next_to_nominate": 3,
        "version": 42,
    }


def _write_data(tmp: Path, state: dict):
    (tmp / "players.json").write_text(json.dumps(PLAYERS))
    (tmp / "owners.json").write_text(json.dumps(OWNERS))
    (tmp / "config.json").write_text(json.dumps(CONFIG))
    (tmp / "player_stats.json").write_text(json.dumps(PLAYER_STATS))
    (tmp / "draft_state.json").write_text(json.dumps(state))


@pytest.fixture
def data_dir(tmp_path):
    _write_data(tmp_path, _base_state())
    return tmp_path


# ---------------------------------------------------------------------------
# Production scoring
# ---------------------------------------------------------------------------
class TestProductionScore:
    def test_none_scores_zero(self):
        assert production_score(None) == 0.0

    def test_qb_score(self):
        from src.models.player_stats import PlayerStats

        stats = PlayerStats.model_validate(PLAYER_STATS["10"])
        # 5000/25 + 40*4 - 10*2 = 200 + 160 - 20 = 340
        assert production_score(stats) == 340.0

    def test_ppr_receiving_counts_receptions(self):
        from src.models.player_stats import PlayerStats

        stats = PlayerStats.model_validate(PLAYER_STATS["30"])
        # 100rec*1 + 1400/10 + 12*6 = 100 + 140 + 72 = 312
        assert production_score(stats) == 312.0


# ---------------------------------------------------------------------------
# Mode detection
# ---------------------------------------------------------------------------
class TestModeDetection:
    def test_no_nominee_mode(self, data_dir):
        slc = build_slice(data_dir)
        assert slc.mode == "NO-NOMINEE"
        assert slc.nominee is None
        assert slc.last_pick is not None

    def test_nominee_live_mode(self, tmp_path):
        state = _base_state()
        state["nominated"] = {
            "player_id": 31,  # Squanchy (WR), available
            "current_bid": 12,
            "current_bidder_id": 2,
            "nominating_owner_id": 1,
        }
        _write_data(tmp_path, state)
        slc = build_slice(tmp_path)
        assert slc.mode == "NOMINEE-LIVE"
        assert slc.nominee is not None
        assert slc.last_pick is None


# ---------------------------------------------------------------------------
# Shared header
# ---------------------------------------------------------------------------
class TestHeader:
    def test_header_facts(self, data_dir):
        slc = build_slice(data_dir)
        assert slc.state_version == 42
        assert slc.draft_year == 2026
        assert slc.picks_made == 2
        assert slc.total_rounds == 17
        assert slc.rules.initial_budget == 200
        assert slc.rules.min_bid == 1
        assert slc.rules.position_maximums["WR"] == 8


# ---------------------------------------------------------------------------
# Last pick (max pick_id) + id->name/stat resolution
# ---------------------------------------------------------------------------
class TestLastPick:
    def test_last_pick_is_max_pick_id(self, data_dir):
        slc = build_slice(data_dir)
        lp = slc.last_pick
        # pick_id 2 (Birdperson) beats pick_id 1 (Rick).
        assert lp.pick_id == 2
        assert lp.player.name == "Birdperson Phoenix"
        assert lp.player.position == "WR"
        assert lp.player.nfl_team == "PHI"
        assert lp.price == 45
        assert lp.player.summary == "100rec 1400yds 12TD"
        assert lp.player.rookie is False

    def test_drafter_snapshot(self, data_dir):
        slc = build_slice(data_dir)
        drafter = slc.last_pick.drafter
        assert drafter.owner_name == "Rick"
        assert drafter.team_name == "Wubba Lubba Dub Dubs"
        assert drafter.budget_remaining == 150
        assert drafter.position_counts == {"QB": 1, "WR": 1}
        assert drafter.slots_filled == 2
        assert drafter.slots_left == 15


# ---------------------------------------------------------------------------
# Next nominator: needs + max bid
# ---------------------------------------------------------------------------
class TestNextNominator:
    def test_next_nominator_resolved(self, data_dir):
        slc = build_slice(data_dir)
        nn = slc.next_nominator
        assert nn.owner_id == 3
        assert nn.owner_name == "Beth"
        assert nn.team_name == "Space Beth Spacers"

    def test_max_legal_bid_reserves_one_per_slot(self, data_dir):
        slc = build_slice(data_dir)
        # Empty roster, $200, 17 slots -> reserve $16 -> max 184.
        assert slc.next_nominator.max_legal_bid == 184

    def test_needs_empty_roster_early(self, data_dir):
        slc = build_slice(data_dir)
        # Empty roster, 17 slots left: RB/WR (<3), QB (no starter), and TE
        # (the league's only TE, #40, is still available -> elite TE on board).
        # D/ST & K are NOT needs this early (only at <=3 slots left).
        assert slc.next_nominator.needs == ["RB", "WR", "QB", "TE"]


# ---------------------------------------------------------------------------
# Needs model (threshold-based, priority-ordered)
# ---------------------------------------------------------------------------
class TestNeeds:
    """Direct coverage of the `_needs` priority model.

    `_needs(counts, slots_left, *, elite_te_available)`. Ordering is always
    RB > WR > QB > TE > D/ST > K.
    """

    def test_rb_wr_need_until_three(self):
        # Below 3 at RB/WR is always a need, regardless of how late it is.
        needs = _needs({"RB": 2, "WR": 2}, 17, elite_te_available=False)
        assert "RB" in needs and "WR" in needs
        # At 3, the position drops off.
        needs = _needs({"RB": 3, "WR": 3, "QB": 1}, 17, elite_te_available=False)
        assert "RB" not in needs and "WR" not in needs

    def test_qb_starter_always_needed(self):
        needs = _needs({"RB": 3, "WR": 3}, 17, elite_te_available=False)
        assert "QB" in needs

    def test_qb_backup_only_late(self):
        # 1 QB, plenty of slots left -> no 2nd-QB need.
        needs = _needs({"QB": 1, "RB": 3, "WR": 3}, 6, elite_te_available=False)
        assert "QB" not in needs
        # 1 QB, <=5 slots left -> 2nd QB becomes a need.
        needs = _needs({"QB": 1, "RB": 3, "WR": 3}, 5, elite_te_available=False)
        assert "QB" in needs
        # 2 QBs already -> never a need.
        needs = _needs({"QB": 2, "RB": 3, "WR": 3}, 3, elite_te_available=False)
        assert "QB" not in needs

    def test_te_zero_elite_available(self):
        # No TE, lots of slots, but an elite TE is on the board -> need.
        needs = _needs({"RB": 3, "WR": 3, "QB": 1}, 12, elite_te_available=True)
        assert "TE" in needs

    def test_te_zero_no_elite_uses_slot_fallback(self):
        # No TE, no elite available, slots > 8 -> not yet a need.
        needs = _needs({"RB": 3, "WR": 3, "QB": 1}, 9, elite_te_available=False)
        assert "TE" not in needs
        # Same, but <=8 slots left -> the fallback kicks in.
        needs = _needs({"RB": 3, "WR": 3, "QB": 1}, 8, elite_te_available=False)
        assert "TE" in needs

    def test_te_one_only_late(self):
        # 1 TE, plenty of room -> satisfied.
        needs = _needs({"TE": 1, "RB": 3, "WR": 3, "QB": 1}, 6, elite_te_available=True)
        assert "TE" not in needs
        # 1 TE, <=5 slots -> a 2nd TE becomes a need.
        needs = _needs(
            {"TE": 1, "RB": 3, "WR": 3, "QB": 1}, 5, elite_te_available=False
        )
        assert "TE" in needs

    def test_te_two_never_a_need(self):
        needs = _needs({"TE": 2, "RB": 3, "WR": 3, "QB": 1}, 2, elite_te_available=True)
        assert "TE" not in needs

    def test_dst_and_k_only_when_nearly_full(self):
        # 4 slots left -> not yet.
        needs = _needs({"RB": 3, "WR": 3, "QB": 1}, 4, elite_te_available=False)
        assert "D/ST" not in needs and "K" not in needs
        # 3 slots left -> both become needs.
        needs = _needs({"RB": 3, "WR": 3, "QB": 1}, 3, elite_te_available=False)
        assert "D/ST" in needs and "K" in needs
        # Already rostered -> never a need even when nearly full.
        needs = _needs(
            {"RB": 3, "WR": 3, "QB": 1, "D/ST": 1, "K": 1},
            3,
            elite_te_available=False,
        )
        assert "D/ST" not in needs and "K" not in needs

    def test_priority_ordering(self):
        # Everything is a need at once; assert the canonical order.
        needs = _needs({}, 3, elite_te_available=True)
        assert needs == ["RB", "WR", "QB", "TE", "D/ST", "K"]

    def test_full_roster_has_no_needs(self):
        # slots_left <= 0 -> empty, regardless of counts.
        assert _needs({}, 0, elite_te_available=True) == []
        assert _needs({"RB": 1}, -1, elite_te_available=True) == []


# ---------------------------------------------------------------------------
# Available ranking, depth, rookie flag
# ---------------------------------------------------------------------------
class TestBestAvailable:
    def test_positions_present(self, data_dir):
        slc = build_slice(data_dir)
        positions = {b.position for b in slc.best_available}
        assert positions == {"QB", "RB", "WR", "TE"}

    def test_wr_ranked_by_production_rookie_last(self, data_dir):
        slc = build_slice(data_dir)
        wr_board = next(b for b in slc.best_available if b.position == "WR")
        names = [s.name for s in wr_board.top]
        # Birdperson(30) is drafted, so among available WRs: Squanchy(31, has
        # stats) ranks above the rookie Noob Noob(99, no stats).
        assert names == ["Squanchy Cat", "Noob Noob"]
        assert wr_board.depth_left == 2

    def test_rookie_flag_for_missing_stats(self, data_dir):
        slc = build_slice(data_dir)
        wr_board = next(b for b in slc.best_available if b.position == "WR")
        rookie = next(s for s in wr_board.top if s.name == "Noob Noob")
        assert rookie.rookie is True
        assert rookie.summary is None
        assert rookie.production_score == 0.0

    def test_rookie_flag_for_empty_statline(self, data_dir):
        # Summer (21) is in the stats file but has no production block.
        slc = build_slice(data_dir)
        rb_board = next(b for b in slc.best_available if b.position == "RB")
        summer = next(s for s in rb_board.top if s.name == "Summer Smith")
        assert summer.rookie is True
        assert summer.production_score == 0.0
        # Morty has real stats and outranks the empty-line Summer.
        assert rb_board.top[0].name == "Morty Smith"


# ---------------------------------------------------------------------------
# NOMINEE-LIVE specifics
# ---------------------------------------------------------------------------
def _nominee_state(player_id=31, bid=12, bidder=2, nominator=1):
    state = _base_state()
    state["nominated"] = {
        "player_id": player_id,
        "current_bid": bid,
        "current_bidder_id": bidder,
        "nominating_owner_id": nominator,
    }
    return state


class TestNomineeLive:
    def test_nominee_resolution(self, tmp_path):
        _write_data(tmp_path, _nominee_state())
        slc = build_slice(tmp_path)
        n = slc.nominee
        assert n.player.name == "Squanchy Cat"
        assert n.player.position == "WR"
        assert n.current_bid == 12
        assert n.nominating_owner_name == "Rick"
        assert n.nominating_team_name == "Wubba Lubba Dub Dubs"
        assert n.current_bidder_name == "Jerry"
        assert n.current_bidder_team_name == "Plumbuses United"

    def test_bid_board_every_team(self, tmp_path):
        _write_data(tmp_path, _nominee_state())
        slc = build_slice(tmp_path)
        assert len(slc.bid_board) == 3
        beth = next(r for r in slc.bid_board if r.owner_id == 3)
        # Beth empty roster -> needs WR; max bid 184.
        assert beth.needs_position is True
        assert beth.max_legal_bid == 184

    def test_bid_board_needs_position_false_when_full(self, tmp_path):
        state = _nominee_state(player_id=31)  # nominee is a WR
        # Fill Jerry to the WR max (8) so he no longer needs WR.
        state["teams"][1]["picks"] = [
            {"pick_id": 100 + i, "player_id": 30, "owner_id": 2, "price": 1}
            for i in range(8)
        ]
        _write_data(tmp_path, state)
        slc = build_slice(tmp_path)
        jerry = next(r for r in slc.bid_board if r.owner_id == 2)
        assert jerry.needs_position is False

    def test_comparables_same_position_recent_first(self, tmp_path):
        # Draft a couple WRs first so there are same-position comparables.
        state = _nominee_state(player_id=31)
        state["teams"][1]["picks"] = [
            {"pick_id": 5, "player_id": 30, "owner_id": 2, "price": 40},
        ]
        # Remove drafted WR from available to keep state consistent.
        state["available_player_ids"] = [
            pid for pid in state["available_player_ids"] if pid != 30
        ]
        _write_data(tmp_path, state)
        slc = build_slice(tmp_path)
        # Comparable WR picks: Birdperson (pick 5) and... only Birdperson here.
        assert any(
            c.name == "Birdperson Phoenix" and c.price == 40 for c in slc.comparables
        )

    def test_position_scarcity(self, tmp_path):
        _write_data(tmp_path, _nominee_state(player_id=31))
        slc = build_slice(tmp_path)
        # Available WRs: Squanchy(31) + rookie Noob(99) = 2.
        assert slc.position_scarcity == 2


# ---------------------------------------------------------------------------
# Brief rendering
# ---------------------------------------------------------------------------
class TestBriefRendering:
    def test_no_nominee_brief(self, data_dir):
        brief = render_brief(build_slice(data_dir))
        assert "[NO-NOMINEE]" in brief
        assert "LAST PICK:" in brief
        assert "Birdperson Phoenix" in brief
        assert "NEXT TO NOMINATE:" in brief
        assert "BEST AVAILABLE:" in brief
        # Rookie is flagged in the rendered text.
        assert "ROOKIE" in brief

    def test_nominee_live_brief(self, tmp_path):
        _write_data(tmp_path, _nominee_state())
        brief = render_brief(build_slice(tmp_path))
        assert "[NOMINEE-LIVE]" in brief
        assert "NOMINEE: Squanchy Cat" in brief
        assert "BID BOARD" in brief
        assert "scarcity:" in brief

    def test_full_roster_renders_dash_not_dollar_none(self, tmp_path):
        # Fill Rick's roster to total_rounds (17) so max_legal_bid is None.
        state = _base_state()
        state["teams"][0]["picks"] = [
            {"pick_id": i, "player_id": 10, "owner_id": 1, "price": 1}
            for i in range(1, 18)
        ]
        _write_data(tmp_path, state)
        slc = build_slice(tmp_path)
        # The JSON slice keeps the literal None.
        assert slc.last_pick.drafter.max_legal_bid is None
        brief = render_brief(slc)
        # The rendered text must NOT contain the literal "$None".
        assert "$None" not in brief
        assert "max legal bid — (full)" in brief

    def test_full_roster_bid_board_renders_dash(self, tmp_path):
        # A full-roster team appears on the live bid board with a dash, not None.
        state = _nominee_state(player_id=31)
        state["teams"][0]["picks"] = [
            {"pick_id": i, "player_id": 10, "owner_id": 1, "price": 1}
            for i in range(1, 18)
        ]
        _write_data(tmp_path, state)
        slc = build_slice(tmp_path)
        rick = next(r for r in slc.bid_board if r.owner_id == 1)
        assert rick.max_legal_bid is None
        brief = render_brief(slc)
        assert "$None" not in brief
        assert "max — (full)" in brief


# ---------------------------------------------------------------------------
# recent_log injection
# ---------------------------------------------------------------------------
class TestRecentLog:
    def test_recent_log_tail_injected(self, data_dir):
        log = data_dir / "analyst-comments.jsonl"
        lines = [
            json.dumps(
                {"ts": "t1", "state_version": 41, "persona": "Kiper", "text": "one"}
            ),
            json.dumps(
                {"ts": "t2", "state_version": 42, "persona": "Kimes", "text": "two"}
            ),
        ]
        log.write_text("\n".join(lines) + "\n")
        slc = build_slice(data_dir, recent_log_limit=1)
        assert len(slc.recent_log) == 1
        assert slc.recent_log[0]["persona"] == "Kimes"

    def test_recent_log_drops_uncommitted_tail(self, data_dir):
        log = data_dir / "analyst-comments.jsonl"
        committed = json.dumps(
            {"ts": "t1", "state_version": 41, "persona": "Kiper", "text": "one"}
        )
        # Second line has no trailing newline -> not yet committed.
        partial = json.dumps(
            {"ts": "t2", "state_version": 42, "persona": "Kimes", "text": "two"}
        )
        log.write_text(committed + "\n" + partial)
        slc = build_slice(data_dir, recent_log_limit=5)
        assert len(slc.recent_log) == 1
        assert slc.recent_log[0]["text"] == "one"

    def test_no_log_means_empty(self, data_dir):
        slc = build_slice(data_dir, recent_log_limit=5)
        assert slc.recent_log == []
