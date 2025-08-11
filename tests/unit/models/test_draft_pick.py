import pytest
from pydantic import ValidationError

from src.models import DraftPick


class TestDraftPick:
    """Test suite for DraftPick model."""

    def test_draft_pick_has_expected_fields(self):
        """Test that DraftPick accepts all expected fields."""
        DraftPick(
            pick_id=1,
            player_id=101,
            owner_id=5,
            price=25,
        )

    def test_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            DraftPick()  # No required fields provided

        with pytest.raises(ValidationError):
            DraftPick(pick_id=1)  # Missing other required fields

        with pytest.raises(ValidationError):
            DraftPick(
                pick_id=1,
                player_id=101,
                # Missing owner_id and price
            )

        with pytest.raises(ValidationError):
            DraftPick(
                pick_id=1,
                player_id=101,
                owner_id=5,
                # Missing price
            )

    def test_invalid_pick_id_type_raises_validation_error(self):
        """Test that invalid pick_id type raises ValidationError."""
        with pytest.raises(ValidationError):
            DraftPick(
                pick_id="not_an_int",
                player_id=101,
                owner_id=5,
                price=25,
            )

        with pytest.raises(ValidationError):
            DraftPick(
                pick_id=1.5,  # Float instead of int
                player_id=101,
                owner_id=5,
                price=25,
            )

    def test_invalid_player_id_type_raises_validation_error(self):
        """Test that invalid player_id type raises ValidationError."""
        with pytest.raises(ValidationError):
            DraftPick(
                pick_id=1,
                player_id="not_an_int",
                owner_id=5,
                price=25,
            )

    def test_invalid_owner_id_type_raises_validation_error(self):
        """Test that invalid owner_id type raises ValidationError."""
        with pytest.raises(ValidationError):
            DraftPick(
                pick_id=1,
                player_id=101,
                owner_id="not_an_int",
                price=25,
            )

    def test_invalid_price_type_raises_validation_error(self):
        """Test that invalid price type raises ValidationError."""
        with pytest.raises(ValidationError):
            DraftPick(
                pick_id=1,
                player_id=101,
                owner_id=5,
                price="not_an_int",
            )
