import pytest
from pydantic import ValidationError

from src.models import Nominated


class TestNominated:
    """Test suite for Nominated model."""

    def test_nominated_has_expected_fields(self):
        """Test that Nominated accepts all expected fields."""
        Nominated(
            player_id=101,
            current_bid=25,
            current_bidder_id=5,
            nominating_owner_id=3,
        )

    def test_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            Nominated()  # No required fields provided

        with pytest.raises(ValidationError):
            Nominated(player_id=101)  # Missing other required fields

        with pytest.raises(ValidationError):
            Nominated(
                player_id=101,
                current_bid=25,
                # Missing current_bidder_id and nominating_owner_id
            )

        with pytest.raises(ValidationError):
            Nominated(
                player_id=101,
                current_bid=25,
                current_bidder_id=5,
                # Missing nominating_owner_id
            )

    def test_invalid_player_id_type_raises_validation_error(self):
        """Test that invalid player_id type raises ValidationError."""
        with pytest.raises(ValidationError):
            Nominated(
                player_id="not_an_int",
                current_bid=25,
                current_bidder_id=5,
                nominating_owner_id=3,
            )

        with pytest.raises(ValidationError):
            Nominated(
                player_id=101.5,  # Float instead of int
                current_bid=25,
                current_bidder_id=5,
                nominating_owner_id=3,
            )

    def test_invalid_current_bid_type_raises_validation_error(self):
        """Test that invalid current_bid type raises ValidationError."""
        with pytest.raises(ValidationError):
            Nominated(
                player_id=101,
                current_bid="not_an_int",
                current_bidder_id=5,
                nominating_owner_id=3,
            )

    def test_invalid_current_bidder_id_type_raises_validation_error(self):
        """Test that invalid current_bidder_id type raises ValidationError."""
        with pytest.raises(ValidationError):
            Nominated(
                player_id=101,
                current_bid=25,
                current_bidder_id="not_an_int",
                nominating_owner_id=3,
            )

    def test_invalid_nominating_owner_id_type_raises_validation_error(self):
        """Test that invalid nominating_owner_id type raises ValidationError."""
        with pytest.raises(ValidationError):
            Nominated(
                player_id=101,
                current_bid=25,
                current_bidder_id=5,
                nominating_owner_id="not_an_int",
            )
