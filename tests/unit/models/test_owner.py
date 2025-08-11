import pytest
from pydantic import ValidationError

from src.models import Owner


class TestOwner:
    """Test suite for Owner model."""

    def test_owner_has_expected_fields(self):
        """Test that Owner accepts all expected fields."""
        Owner(
            id=1,
            owner_name="Rick Sanchez",
            team_name="Interdimensional Cable",
        )

    def test_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            Owner()  # No required fields provided

        with pytest.raises(ValidationError):
            Owner(id=1)  # Missing owner_name and team_name

        with pytest.raises(ValidationError):
            Owner(id=1, owner_name="Rick")  # Missing team_name

    def test_invalid_id_type_raises_validation_error(self):
        """Test that invalid id type raises ValidationError."""
        with pytest.raises(ValidationError):
            Owner(
                id="not_an_int",
                owner_name="Birdperson",
                team_name="Phoenix Squad",
            )

        with pytest.raises(ValidationError):
            Owner(
                id=1.5,  # Float instead of int
                owner_name="Birdperson",
                team_name="Phoenix Squad",
            )

    def test_invalid_name_types_raise_validation_error(self):
        """Test that invalid name types raise ValidationError."""
        with pytest.raises(ValidationError):
            Owner(
                id=10,
                owner_name=123,  # Int instead of string
                team_name="Valid Team",
            )

        with pytest.raises(ValidationError):
            Owner(
                id=11,
                owner_name="Valid Owner",
                team_name=456,  # Int instead of string
            )
