import pytest
from pydantic import ValidationError

from src.models import DraftPick, Team


class TestTeam:
    """Test suite for Team model."""

    def test_team_has_expected_fields(self):
        """Test that Team accepts all expected fields."""
        pick1 = DraftPick(pick_id=1, player_id=101, owner_id=5, price=25)
        pick2 = DraftPick(pick_id=2, player_id=102, owner_id=5, price=50)

        Team(
            owner_id=5,
            budget_remaining=125,
            picks=[pick1, pick2],
        )

    def test_create_team_with_default_empty_picks(self):
        """Test creating a team with default empty picks list."""
        team = Team(
            owner_id=7,
            budget_remaining=150,
        )

        assert team.owner_id == 7
        assert team.budget_remaining == 150
        assert len(team.picks) == 0

    def test_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            Team()  # No required fields provided

        with pytest.raises(ValidationError):
            Team(owner_id=1)  # Missing budget_remaining

    def test_invalid_owner_id_type_raises_validation_error(self):
        """Test that invalid owner_id type raises ValidationError."""
        with pytest.raises(ValidationError):
            Team(
                owner_id="not_an_int",
                budget_remaining=200,
            )

        with pytest.raises(ValidationError):
            Team(
                owner_id=1.5,  # Float instead of int
                budget_remaining=200,
            )

    def test_invalid_budget_remaining_type_raises_validation_error(self):
        """Test that invalid budget_remaining type raises ValidationError."""
        with pytest.raises(ValidationError):
            Team(
                owner_id=1,
                budget_remaining="not_an_int",
            )

    def test_invalid_picks_type_raises_validation_error(self):
        """Test that invalid picks type raises ValidationError."""
        with pytest.raises(ValidationError):
            Team(
                owner_id=1,
                budget_remaining=200,
                picks="not_a_list",
            )

        with pytest.raises(ValidationError):
            Team(
                owner_id=1,
                budget_remaining=200,
                picks=[{"not": "a_draft_pick"}],  # Invalid pick structure
            )

    def test_picks_list_with_invalid_draft_pick_raises_validation_error(self):
        """Test that invalid DraftPick objects in picks list raise ValidationError."""
        with pytest.raises(ValidationError):
            Team(
                owner_id=1,
                budget_remaining=200,
                picks=[
                    DraftPick(pick_id=1, player_id=101, owner_id=1, price=25),  # Valid
                    {
                        "pick_id": "invalid",
                        "player_id": 102,
                        "owner_id": 1,
                        "price": 30,
                    },  # Invalid
                ],
            )
