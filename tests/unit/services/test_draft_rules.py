from src.models import Configuration, DraftPick, Team
from src.services.draft_rules import max_bid, remaining_roster_spots


def _config(total_rounds=17):
    return Configuration(
        initial_budget=200,
        min_bid=1,
        position_maximums={"QB": 3, "RB": 8, "WR": 8, "TE": 3, "K": 3, "D/ST": 3},
        total_rounds=total_rounds,
    )


def _team(budget, n_picks, owner_id=1):
    picks = [
        DraftPick(pick_id=i + 1, player_id=100 + i, owner_id=owner_id, price=1)
        for i in range(n_picks)
    ]
    return Team(owner_id=owner_id, budget_remaining=budget, picks=picks)


class TestRemainingRosterSpots:
    def test_counts_unfilled_slots(self):
        assert remaining_roster_spots(_team(200, 0), _config(17)) == 17
        assert remaining_roster_spots(_team(200, 5), _config(17)) == 12


class TestMaxBid:
    def test_reserves_one_dollar_per_remaining_slot(self):
        # 16 spots left -> reserve $15 -> max_bid = 200 - 15 = 185
        assert max_bid(_team(200, 1), _config(17)) == 185

    def test_last_slot_allows_entire_budget(self):
        # 1 spot left -> reserve $0 -> max_bid = full budget
        assert max_bid(_team(50, 16), _config(17)) == 50

    def test_full_roster_returns_none(self):
        assert max_bid(_team(50, 17), _config(17)) is None

    def test_does_not_use_min_bid_for_reserve(self):
        # Even if min_bid were larger, reserve stays $1/slot.
        cfg = Configuration(
            initial_budget=200, min_bid=5,
            position_maximums={"QB": 3}, total_rounds=17,
        )
        assert max_bid(_team(200, 1), cfg) == 185
