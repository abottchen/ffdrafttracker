from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from src.models import Configuration


class TestConfiguration:
    """Test suite for Configuration model."""

    def test_configuration_has_expected_fields(self):
        """Test that Configuration accepts all expected fields."""
        Configuration(
            initial_budget=200,
            min_bid=1,
            position_maximums={"QB": 2, "RB": 4, "WR": 5, "TE": 2, "K": 1, "D/ST": 1},
            total_rounds=19,
            data_directory="data",
        )

    def test_configuration_with_default_data_directory(self):
        """Test configuration uses default data directory when not provided."""
        config = Configuration(
            initial_budget=250,
            min_bid=2,
            position_maximums={"QB": 1, "RB": 3},
            total_rounds=15,
        )

        assert config.data_directory == "data"  # Default value

    @patch("pathlib.Path.read_text")
    def test_load_from_file_calls_model_validate_json(self, mock_read_text):
        """Test load_from_file reads file and validates JSON."""
        json_content = (
            '{"initial_budget": 200, "min_bid": 1, '
            '"position_maximums": {"QB": 2}, "total_rounds": 19}'
        )
        mock_read_text.return_value = json_content

        with patch.object(
            Configuration, "model_validate_json", return_value=Mock()
        ) as mock_validate:
            Configuration.load_from_file(Path("test_config.json"))

            mock_read_text.assert_called_once()
            mock_validate.assert_called_once_with(json_content)

    def test_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            Configuration()  # No required fields provided

        with pytest.raises(ValidationError):
            Configuration(initial_budget=200)  # Missing other required fields

        with pytest.raises(ValidationError):
            Configuration(
                initial_budget=200,
                min_bid=1,
                # Missing position_maximums and total_rounds
            )

    def test_invalid_budget_type_raises_validation_error(self):
        """Test that invalid budget type raises ValidationError."""
        with pytest.raises(ValidationError):
            Configuration(
                initial_budget="not_an_int",
                min_bid=1,
                position_maximums={"QB": 2},
                total_rounds=19,
            )

    def test_invalid_min_bid_type_raises_validation_error(self):
        """Test that invalid min_bid type raises ValidationError."""
        with pytest.raises(ValidationError):
            Configuration(
                initial_budget=200,
                min_bid="not_an_int",
                position_maximums={"QB": 2},
                total_rounds=19,
            )

    def test_invalid_position_maximums_type_raises_validation_error(self):
        """Test that invalid position_maximums type raises ValidationError."""
        with pytest.raises(ValidationError):
            Configuration(
                initial_budget=200,
                min_bid=1,
                position_maximums="not_a_dict",
                total_rounds=19,
            )

    def test_invalid_position_maximums_values_raise_validation_error(self):
        """Test that non-integer values in position_maximums raise ValidationError."""
        with pytest.raises(ValidationError):
            Configuration(
                initial_budget=200,
                min_bid=1,
                position_maximums={"QB": "not_an_int"},
                total_rounds=19,
            )

    def test_invalid_total_rounds_type_raises_validation_error(self):
        """Test that invalid total_rounds type raises ValidationError."""
        with pytest.raises(ValidationError):
            Configuration(
                initial_budget=200,
                min_bid=1,
                position_maximums={"QB": 2},
                total_rounds="not_an_int",
            )

    def test_invalid_data_directory_type_raises_validation_error(self):
        """Test that invalid data_directory type raises ValidationError."""
        with pytest.raises(ValidationError):
            Configuration(
                initial_budget=200,
                min_bid=1,
                position_maximums={"QB": 2},
                total_rounds=19,
                data_directory=123,
            )
