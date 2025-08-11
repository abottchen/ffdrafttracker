import pytest
from pydantic import ValidationError

from src.enums import NFLTeam, Position
from src.models import Player


class TestPlayer:
    """Test suite for Player model."""

    def test_player_has_expected_fields(self):
        """Test that Player accepts all expected fields."""
        Player(
            id=1,
            first_name="Patrick",
            last_name="Mahomes",
            team=NFLTeam.KC,
            position=Position.QB,
        )

    def test_full_name_property(self):
        """Test the full_name computed property."""
        player = Player(
            id=2,
            first_name="Travis",
            last_name="Kelce",
            team=NFLTeam.KC,
            position=Position.TE,
        )

        assert player.full_name == "Travis Kelce"

    def test_display_name_property(self):
        """Test the display_name computed property."""
        player = Player(
            id=3,
            first_name="Christian",
            last_name="McCaffrey",
            team=NFLTeam.SF,
            position=Position.RB,
        )

        assert player.display_name == "McCaffrey, C."

    def test_display_name_with_single_char_first_name(self):
        """Test display_name with a single character first name."""
        player = Player(
            id=4,
            first_name="A",
            last_name="Smith",
            team=NFLTeam.NE,
            position=Position.WR,
        )

        assert player.display_name == "Smith, A."

    def test_display_name_with_suffix_in_last_name(self):
        """Test display_name when suffix is in last_name field."""
        player = Player(
            id=5,
            first_name="Calvin",
            last_name="Ridley Jr.",
            team=NFLTeam.TEN,
            position=Position.WR,
        )

        assert player.display_name == "Ridley Jr., C."

    def test_display_name_with_apostrophe_in_first_name(self):
        """Test display_name with apostrophe in first name."""
        player = Player(
            id=6,
            first_name="De'Von",
            last_name="Achane",
            team=NFLTeam.MIA,
            position=Position.RB,
        )

        assert player.display_name == "Achane, D."

    def test_display_name_with_hyphenated_last_name(self):
        """Test display_name with hyphenated last name."""
        player = Player(
            id=7,
            first_name="JuJu",
            last_name="Smith-Schuster",
            team=NFLTeam.KC,
            position=Position.WR,
        )

        assert player.display_name == "Smith-Schuster, J."

    def test_invalid_team_raises_validation_error(self):
        """Test that invalid team raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Player(
                id=99,
                first_name="Summer",
                last_name="Smith",
                team="INVALID",
                position=Position.QB,
            )

        assert "team" in str(exc_info.value)

    def test_invalid_position_raises_validation_error(self):
        """Test that invalid position raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            Player(
                id=99,
                first_name="Jerry",
                last_name="Smith",
                team=NFLTeam.KC,
                position="INVALID",
            )

        assert "position" in str(exc_info.value)

    def test_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            Player()  # No required fields provided

        with pytest.raises(ValidationError):
            Player(id=1)  # Missing other required fields

    def test_invalid_id_type_raises_validation_error(self):
        """Test that invalid id type raises ValidationError."""
        with pytest.raises(ValidationError):
            Player(
                id="not_an_int",
                first_name="Beth",
                last_name="Smith",
                team=NFLTeam.KC,
                position=Position.QB,
            )
