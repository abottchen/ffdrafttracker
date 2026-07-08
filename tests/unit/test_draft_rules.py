from src.draft_rules import (
    check_position_limit,
    max_bid,
    next_eligible_nominator,
    next_pick_id,
    position_count,
    remaining_roster_spots,
)
from src.models import Configuration, DraftPick, DraftState, Player, Team


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


def _state(teams, next_to_nominate=1):
    return DraftState(
        nominated=None,
        available_player_ids=[],
        teams=teams,
        next_to_nominate=next_to_nominate,
        version=1,
    )


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
            initial_budget=200,
            min_bid=5,
            position_maximums={"QB": 3},
            total_rounds=17,
        )
        assert max_bid(_team(200, 1), cfg) == 185


class TestPositionCount:
    def test_counts_only_matching_position(self):
        team = Team(
            owner_id=1,
            budget_remaining=100,
            picks=[
                DraftPick(pick_id=1, player_id=10, owner_id=1, price=5),
                DraftPick(pick_id=2, player_id=11, owner_id=1, price=5),
                DraftPick(pick_id=3, player_id=12, owner_id=1, price=5),
            ],
        )
        positions = {10: "RB", 11: "RB", 12: "WR"}
        assert position_count(team, "RB", positions) == 2
        assert position_count(team, "WR", positions) == 1
        assert position_count(team, "QB", positions) == 0

    def test_unknown_player_ignored(self):
        team = Team(
            owner_id=1,
            budget_remaining=100,
            picks=[DraftPick(pick_id=1, player_id=99, owner_id=1, price=5)],
        )
        assert position_count(team, "RB", {}) == 0


class TestNextEligibleNominator:
    def test_advance_to_next_owner(self):
        state = _state([_team(200, 0, 1), _team(200, 0, 2), _team(200, 0, 3)])
        nxt = next_eligible_nominator(state, _config(17), from_id=1, inclusive=False)
        assert nxt == 2

    def test_advance_wraps_around(self):
        state = _state([_team(200, 0, 1), _team(200, 0, 2)])
        nxt = next_eligible_nominator(state, _config(17), from_id=2, inclusive=False)
        assert nxt == 1

    def test_advance_wraps_from_last_owner_across_many_teams(self):
        # From the highest owner_id, advance must wrap to the lowest.
        state = _state(
            [_team(200, 0, 1), _team(200, 0, 2), _team(200, 0, 3), _team(200, 0, 4)]
        )
        nxt = next_eligible_nominator(state, _config(17), from_id=4, inclusive=False)
        assert nxt == 1

    def test_advance_wraps_past_ineligible_back_to_low_owner(self):
        # Wrap from the last owner past a full team to the first eligible.
        full = _team(0, 17, 1)
        state = _state([full, _team(200, 0, 2), _team(200, 0, 3)])
        nxt = next_eligible_nominator(state, _config(17), from_id=3, inclusive=False)
        assert nxt == 2

    def test_advance_skips_full_roster(self):
        state = _state([_team(200, 0, 1), _team(0, 17, 2), _team(200, 0, 3)])
        nxt = next_eligible_nominator(state, _config(17), from_id=1, inclusive=False)
        assert nxt == 3

    def test_advance_skips_manually_done(self):
        done = _team(200, 0, 2)
        done.manually_done = True
        state = _state([_team(200, 0, 1), done, _team(200, 0, 3)])
        nxt = next_eligible_nominator(state, _config(17), from_id=1, inclusive=False)
        assert nxt == 3

    def test_inclusive_keeps_current_when_eligible(self):
        state = _state([_team(200, 0, 1), _team(200, 0, 2)])
        nxt = next_eligible_nominator(state, _config(17), from_id=1, inclusive=True)
        assert nxt == 1

    def test_inclusive_advances_when_current_ineligible(self):
        done = _team(0, 17, 1)
        state = _state([done, _team(200, 0, 2)])
        nxt = next_eligible_nominator(state, _config(17), from_id=1, inclusive=True)
        assert nxt == 2

    def test_returns_none_when_no_one_eligible(self):
        state = _state([_team(0, 17, 1), _team(0, 17, 2)])
        assert (
            next_eligible_nominator(state, _config(17), from_id=1, inclusive=True)
            is None
        )

    def test_exclusive_returns_self_when_sole_eligible(self):
        # Owner 1 is the only eligible team; exclusive search wraps back to it.
        state = _state([_team(200, 0, 1), _team(0, 17, 2)])
        nxt = next_eligible_nominator(state, _config(17), from_id=1, inclusive=False)
        assert nxt == 1


class TestCheckPositionLimit:
    def _player(self, pid=1, position="RB"):
        return Player(
            id=pid,
            first_name="Test",
            last_name="Player",
            team="BUF",
            position=position,
        )

    def _players(self, *positions):
        return [
            Player(
                id=i + 1,
                first_name="P",
                last_name=f"{i}",
                team="BUF",
                position=pos,
            )
            for i, pos in enumerate(positions)
        ]

    def test_returns_none_when_team_is_none(self):
        player = self._player()
        assert check_position_limit(None, player, [player], _config()) is None

    def test_returns_none_when_position_has_no_cap(self):
        # Position "FLEX" is not in position_maximums
        cfg = Configuration(
            initial_budget=200,
            min_bid=1,
            position_maximums={"QB": 3},
            total_rounds=17,
        )
        player = self._player(position="RB")
        team = _team(200, 0)
        assert check_position_limit(team, player, [player], cfg) is None

    def test_returns_none_when_under_limit(self):
        players = self._players("RB", "RB", "WR")
        team = Team(
            owner_id=1,
            budget_remaining=100,
            picks=[
                DraftPick(pick_id=1, player_id=1, owner_id=1, price=5),
            ],
        )
        new_player = self._player(pid=4, position="RB")
        # 1 RB on team, max is 8 -> OK
        assert check_position_limit(team, new_player, players, _config()) is None

    def test_returns_error_when_at_limit(self):
        # Config has QB max = 3
        players = self._players("QB", "QB", "QB")
        team = Team(
            owner_id=1,
            budget_remaining=100,
            picks=[
                DraftPick(pick_id=i + 1, player_id=i + 1, owner_id=1, price=5)
                for i in range(3)
            ],
        )
        new_qb = self._player(pid=10, position="QB")
        result = check_position_limit(team, new_qb, players, _config())
        assert result is not None
        assert "maximum of 3" in result
        assert "QB" in result


class TestNextPickId:
    def test_returns_one_when_no_picks(self):
        state = _state([_team(200, 0, 1), _team(200, 0, 2)])
        assert next_pick_id(state) == 1

    def test_returns_max_plus_one(self):
        teams = [
            Team(
                owner_id=1,
                budget_remaining=100,
                picks=[
                    DraftPick(pick_id=1, player_id=10, owner_id=1, price=5),
                    DraftPick(pick_id=3, player_id=11, owner_id=1, price=5),
                ],
            ),
            Team(
                owner_id=2,
                budget_remaining=100,
                picks=[
                    DraftPick(pick_id=2, player_id=12, owner_id=2, price=5),
                ],
            ),
        ]
        state = _state(teams)
        assert next_pick_id(state) == 4

    def test_single_pick(self):
        teams = [
            Team(
                owner_id=1,
                budget_remaining=100,
                picks=[
                    DraftPick(pick_id=5, player_id=10, owner_id=1, price=5),
                ],
            ),
        ]
        state = _state(teams)
        assert next_pick_id(state) == 6
