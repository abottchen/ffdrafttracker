"""Unit tests for PlayerStats model and stat-field coercion.

Covers the ``BeforeValidator`` coercion on ``StatInt`` and ``StatFloat``
annotated types: normal strings, comma-separated numbers, dashes, blank
strings, and already-numeric values.
"""

from src.models.player_stats import (
    KickingStats,
    PassingStats,
    PlayerStats,
    PlayerStatsCollection,
    ReceivingStats,
    RushingStats,
    _coerce_float,
    _coerce_int,
)


# ---------------------------------------------------------------------------
# Low-level coercion helpers
# ---------------------------------------------------------------------------
class TestCoerceInt:
    def test_normal_string(self):
        assert _coerce_int("400") == 400

    def test_comma_separated(self):
        assert _coerce_int("1,071") == 1071

    def test_dash(self):
        assert _coerce_int("-") == 0

    def test_blank(self):
        assert _coerce_int("") == 0

    def test_whitespace(self):
        assert _coerce_int("  ") == 0

    def test_already_int(self):
        assert _coerce_int(42) == 42

    def test_float_input(self):
        assert _coerce_int(4.9) == 4

    def test_junk(self):
        assert _coerce_int("N/A") == 0

    def test_none_like(self):
        assert _coerce_int(None) == 0


class TestCoerceFloat:
    def test_normal_string(self):
        assert _coerce_float("66.7") == 66.7

    def test_integer_string(self):
        assert _coerce_float("150") == 150.0

    def test_comma_separated(self):
        assert _coerce_float("1,500") == 1500.0

    def test_dash(self):
        assert _coerce_float("-") == 0.0

    def test_blank(self):
        assert _coerce_float("") == 0.0

    def test_already_float(self):
        assert _coerce_float(8.3) == 8.3

    def test_already_int(self):
        assert _coerce_float(8) == 8.0

    def test_junk(self):
        assert _coerce_float("N/A") == 0.0


# ---------------------------------------------------------------------------
# Stat sub-models accept string values and coerce to numeric
# ---------------------------------------------------------------------------
class TestPassingStatsCoercion:
    def test_from_string_values(self):
        stats = PassingStats(
            completions="400",
            attempts="600",
            pct="66.7",
            yards="5,000",
            avg="8.3",
            tds="40",
            ints="10",
            sacks="20",
            rating="110.0",
        )
        assert stats.completions == 400
        assert stats.yards == 5000
        assert stats.pct == 66.7
        assert stats.rating == 110.0

    def test_dash_values(self):
        stats = PassingStats(
            completions="-",
            attempts="-",
            pct="-",
            yards="-",
            avg="-",
            tds="-",
            ints="-",
            sacks="-",
            rating="-",
        )
        assert stats.completions == 0
        assert stats.yards == 0
        assert stats.pct == 0.0


class TestRushingStatsCoercion:
    def test_from_string_values(self):
        stats = RushingStats(
            carries="203",
            yards="1,431",
            avg="4.5",
            tds="6",
            long="61",
            fumbles="0",
        )
        assert stats.carries == 203
        assert stats.yards == 1431
        assert stats.avg == 4.5

    def test_all_dashes(self):
        stats = RushingStats(
            carries="-",
            yards="-",
            avg="-",
            tds="-",
            long="-",
            fumbles="-",
        )
        assert stats.carries == 0
        assert stats.yards == 0
        assert stats.avg == 0.0


class TestReceivingStatsCoercion:
    def test_from_string_values(self):
        stats = ReceivingStats(
            receptions="78",
            targets="87",
            yards="1,708",
            avg="7.6",
            tds="6",
            long="39",
            fumbles="1",
        )
        assert stats.receptions == 78
        assert stats.yards == 1708
        assert stats.avg == 7.6


class TestKickingStatsCoercion:
    def test_from_string_values(self):
        stats = KickingStats(
            fgm="35",
            fga="40",
            fg_pct="87.5",
            long="58",
            xpm="45",
            xpa="45",
            points="150",
        )
        assert stats.fgm == 35
        assert stats.fg_pct == 87.5
        assert stats.points == 150


# ---------------------------------------------------------------------------
# Full PlayerStats round-trip
# ---------------------------------------------------------------------------
class TestPlayerStatsRoundTrip:
    def test_validate_from_json_strings(self):
        """Mirrors the shape of data/player_stats.json entries."""
        raw = {
            "bye_week": 12,
            "position": "RB",
            "team": "MIA",
            "rushing": {
                "carries": "203",
                "yards": "907",
                "avg": "4.5",
                "tds": "6",
                "long": "61",
                "fumbles": "0",
            },
            "receiving": {
                "receptions": "78",
                "targets": "87",
                "yards": "592",
                "avg": "7.6",
                "tds": "6",
                "long": "39",
                "fumbles": "1",
            },
            "stats_summary": "Rush: 203att 907yds 6TD | Rec: 78rec 592yds 6TD",
        }
        ps = PlayerStats.model_validate(raw)
        assert ps.rushing.yards == 907
        assert ps.receiving.receptions == 78
        assert ps.stats_summary is not None

    def test_no_stat_blocks(self):
        raw = {"bye_week": 5, "position": "RB", "team": "GB"}
        ps = PlayerStats.model_validate(raw)
        assert ps.passing is None
        assert ps.rushing is None
        assert ps.stats_summary is None


class TestPlayerStatsCollection:
    def test_get_player_stats(self):
        raw = {
            "123": {
                "bye_week": 6,
                "position": "QB",
                "team": "KC",
                "passing": {
                    "completions": "10",
                    "attempts": "20",
                    "pct": "50.0",
                    "yards": "100",
                    "avg": "5.0",
                    "tds": "1",
                    "ints": "0",
                    "sacks": "2",
                    "rating": "80.0",
                },
            }
        }
        coll = PlayerStatsCollection.model_validate(raw)
        ps = coll.get_player_stats(123)
        assert ps is not None
        assert ps.passing.completions == 10
        assert coll.get_player_stats(999) is None
