from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models import ActionLog


class TestActionLog:
    """Test suite for ActionLog model."""

    def test_action_log_has_expected_fields(self):
        """Test that ActionLog accepts all expected fields."""
        test_time = datetime(2024, 1, 15, 12, 30, 45)
        ActionLog(
            timestamp=test_time,
            action_type="nominate",
            owner_id=5,
            data={"player_id": 101, "initial_bid": 25},
        )

    def test_create_action_log_with_auto_timestamp(self):
        """Test creating an action log with automatic timestamp."""
        before_time = datetime.now()

        log = ActionLog(
            action_type="bid",
            owner_id=3,
            data={"player_id": 102, "bid_amount": 50},
        )

        after_time = datetime.now()

        assert before_time <= log.timestamp <= after_time
        assert log.action_type == "bid"
        assert log.owner_id == 3

    def test_missing_required_fields_raises_validation_error(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            ActionLog()  # No required fields provided

        with pytest.raises(ValidationError):
            ActionLog(action_type="bid")  # Missing owner_id and data

        with pytest.raises(ValidationError):
            ActionLog(
                action_type="bid",
                owner_id=1,
                # Missing data
            )

    def test_invalid_timestamp_type_raises_validation_error(self):
        """Test that invalid timestamp type raises ValidationError."""
        with pytest.raises(ValidationError):
            ActionLog(
                timestamp="not_a_datetime",
                action_type="bid",
                owner_id=1,
                data={},
            )

    def test_invalid_action_type_raises_validation_error(self):
        """Test that invalid action_type type raises ValidationError."""
        with pytest.raises(ValidationError):
            ActionLog(
                action_type=123,  # Int instead of string
                owner_id=1,
                data={},
            )

    def test_invalid_owner_id_type_raises_validation_error(self):
        """Test that invalid owner_id type raises ValidationError."""
        with pytest.raises(ValidationError):
            ActionLog(
                action_type="bid",
                owner_id="not_an_int",
                data={},
            )

        with pytest.raises(ValidationError):
            ActionLog(
                action_type="bid",
                owner_id=1.5,  # Float instead of int
                data={},
            )

    def test_invalid_data_type_raises_validation_error(self):
        """Test that invalid data type raises ValidationError."""
        with pytest.raises(ValidationError):
            ActionLog(
                action_type="bid",
                owner_id=1,
                data="not_a_dict",
            )
