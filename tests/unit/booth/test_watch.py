"""Tests for the booth watch event-key (bid-insensitive event detection)."""

from src.booth.watch import booth_tick, event_key, lull_phase
from src.models.draft_pick import DraftPick
from src.models.draft_state import DraftState
from src.models.nominated import Nominated
from src.models.team import Team


def _nominee(player_id: int, bid: int, bidder: int) -> Nominated:
    return Nominated(
        player_id=player_id,
        current_bid=bid,
        current_bidder_id=bidder,
        nominating_owner_id=1,
    )


def _state(nominated=None, teams=None) -> DraftState:
    return DraftState(nominated=nominated, teams=teams or [], next_to_nominate=1)


def test_bid_change_does_not_change_key():
    """A higher bid from a new bidder on the same nominee -> same key."""
    before = _state(nominated=_nominee(99, bid=1, bidder=1))
    after = _state(nominated=_nominee(99, bid=5, bidder=2))
    assert event_key(before) == event_key(after)


def test_new_nominee_changes_key():
    before = _state(nominated=_nominee(99, bid=1, bidder=1))
    after = _state(nominated=_nominee(100, bid=1, bidder=1))
    assert event_key(before) != event_key(after)


def test_nominee_cleared_changes_key():
    before = _state(nominated=_nominee(99, bid=1, bidder=1))
    after = _state(nominated=None)
    assert event_key(before) != event_key(after)


def test_new_pick_changes_key():
    """Awarding a player (new max pick_id) changes the key."""
    pick = DraftPick(pick_id=5, player_id=1, owner_id=1, price=3)
    new_pick = DraftPick(pick_id=6, player_id=2, owner_id=1, price=1)
    before = _state(teams=[Team(owner_id=1, budget_remaining=10, picks=[pick])])
    after = _state(teams=[Team(owner_id=1, budget_remaining=9, picks=[pick, new_pick])])
    assert event_key(before) != event_key(after)


def _team_with_picks(owner_id: int, n_picks: int) -> Team:
    picks = [
        DraftPick(pick_id=owner_id * 100 + i, player_id=i, owner_id=owner_id, price=1)
        for i in range(1, n_picks + 1)
    ]
    return Team(owner_id=owner_id, budget_remaining=10, picks=picks)


def _stocked_state(nominated=None) -> DraftState:
    """Two teams, two picks total -> picks_made (2) >= num_teams (2): floor met."""
    return _state(
        nominated=nominated,
        teams=[_team_with_picks(1, 1), _team_with_picks(2, 1)],
    )


class TestLullPhase:
    def test_live_nominee_pins_phase_zero(self):
        state = _stocked_state(nominated=_nominee(99, bid=1, bidder=1))
        assert lull_phase(state, dead_seconds=10_000) == "0"

    def test_below_history_floor_is_zero(self):
        # Two teams, one pick total -> picks_made (1) < num_teams (2).
        state = _state(teams=[_team_with_picks(1, 1), _team_with_picks(2, 0)])
        assert lull_phase(state, dead_seconds=10_000) == "0"

    def test_short_lull_is_zero(self):
        assert lull_phase(_stocked_state(), dead_seconds=119) == "0"

    def test_musing_stages_step_every_two_minutes(self):
        assert lull_phase(_stocked_state(), dead_seconds=120) == "1"
        assert lull_phase(_stocked_state(), dead_seconds=240) == "2"
        assert lull_phase(_stocked_state(), dead_seconds=360) == "3"

    def test_musing_stage_saturates_at_cap(self):
        # 8 min in but below the 15-min easter threshold -> still capped at 3.
        assert lull_phase(_stocked_state(), dead_seconds=480) == "3"
        assert lull_phase(_stocked_state(), dead_seconds=899) == "3"

    def test_easter_egg_steps_every_fifteen_minutes(self):
        assert lull_phase(_stocked_state(), dead_seconds=900) == "ee1"
        assert lull_phase(_stocked_state(), dead_seconds=1800) == "ee2"
        assert lull_phase(_stocked_state(), dead_seconds=2700) == "ee3"


class TestBoothTick:
    def test_tick_combines_event_key_and_phase(self):
        state = _stocked_state()
        assert booth_tick(state, dead_seconds=240) == f"{event_key(state)}#2"

    def test_tick_phase_zero_when_short_lull(self):
        state = _stocked_state()
        assert booth_tick(state, dead_seconds=5) == f"{event_key(state)}#0"
