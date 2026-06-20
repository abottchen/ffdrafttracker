"""Tests for the booth watch event-key (bid-insensitive event detection)."""

from src.booth.watch import event_key
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
