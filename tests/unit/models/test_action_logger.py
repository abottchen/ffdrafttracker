import json
from pathlib import Path
from unittest.mock import Mock, patch

from src.models.action_logger import ActionLogger


class TestActionLogger:
    """Unit tests for ActionLogger utility class."""

    def test_action_logger_initialization(self):
        """Test ActionLogger can be initialized with a file path."""
        log_path = Path("test_log.json")
        logger = ActionLogger(log_path)

        assert logger.log_file_path == log_path

    @patch.object(ActionLogger, "_save_logs")
    @patch.object(ActionLogger, "_load_logs")
    @patch("src.models.action_logger.ActionLog")
    def test_log_action_creates_action_and_saves(
        self, mock_action_log_class, mock_load_logs, mock_save_logs
    ):
        """Test log_action creates ActionLog and saves to file."""
        # Setup mocks
        mock_action_instance = Mock()
        mock_action_log_class.return_value = mock_action_instance
        existing_logs = [Mock(), Mock()]
        mock_load_logs.return_value = existing_logs

        logger = ActionLogger(Path("test.json"))

        # Call method
        logger.log_action("draft_pick", 123, {"player_id": 456})

        # Verify ActionLog was created with correct parameters
        mock_action_log_class.assert_called_once_with(
            action_type="draft_pick", owner_id=123, data={"player_id": 456}
        )

        # Verify logs were loaded
        mock_load_logs.assert_called_once()

        # Verify save_logs was called with a list that includes the new action
        mock_save_logs.assert_called_once()
        call_args = mock_save_logs.call_args[0][0]
        assert len(call_args) == 3  # 2 existing + 1 new
        assert call_args[-1] == mock_action_instance  # New action is last

    @patch("pathlib.Path.exists")
    def test_load_logs_returns_empty_list_when_file_not_exists(self, mock_exists):
        """Test _load_logs returns empty list when file doesn't exist."""
        mock_exists.return_value = False

        logger = ActionLogger(Path("nonexistent.json"))
        result = logger._load_logs()

        assert result == []

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_load_logs_returns_empty_list_when_file_empty(
        self, mock_read_text, mock_exists
    ):
        """Test _load_logs returns empty list when file is empty or whitespace."""
        mock_exists.return_value = True
        mock_read_text.return_value = "   \n  "

        logger = ActionLogger(Path("empty.json"))
        result = logger._load_logs()

        assert result == []

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    @patch("src.models.action_logger.ActionLog")
    def test_load_logs_parses_valid_json_into_action_logs(
        self, mock_action_log_class, mock_read_text, mock_exists
    ):
        """Test _load_logs correctly parses JSON into ActionLog objects."""
        mock_exists.return_value = True
        mock_log1 = Mock()
        mock_log2 = Mock()
        mock_action_log_class.side_effect = [mock_log1, mock_log2]

        json_data = [
            {"action_type": "draft_pick", "owner_id": 1, "data": {"player_id": 101}},
            {"action_type": "nomination", "owner_id": 2, "data": {"player_id": 102}},
        ]
        mock_read_text.return_value = json.dumps(json_data)

        logger = ActionLogger(Path("valid.json"))
        result = logger._load_logs()

        # Verify ActionLog objects were created with correct data
        assert mock_action_log_class.call_count == 2
        mock_action_log_class.assert_any_call(**json_data[0])
        mock_action_log_class.assert_any_call(**json_data[1])

        assert result == [mock_log1, mock_log2]

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_load_logs_returns_empty_list_on_corrupted_json(
        self, mock_read_text, mock_exists
    ):
        """Test _load_logs returns empty list when JSON is corrupted."""
        mock_exists.return_value = True
        mock_read_text.return_value = "{ invalid json }"

        logger = ActionLogger(Path("corrupted.json"))
        result = logger._load_logs()

        assert result == []

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.read_text")
    def test_load_logs_returns_empty_list_on_action_log_creation_error(
        self, mock_read_text, mock_exists
    ):
        """Test _load_logs returns empty list when ActionLog creation fails."""
        mock_exists.return_value = True
        mock_read_text.return_value = '[{"invalid": "data"}]'

        logger = ActionLogger(Path("invalid_data.json"))
        result = logger._load_logs()

        assert result == []

    @patch("pathlib.Path.replace")
    @patch("pathlib.Path.write_text")
    def test_save_logs_uses_atomic_write_pattern(self, mock_write_text, mock_replace):
        """Test _save_logs uses atomic write with temp file."""
        mock_log1 = Mock()
        mock_log2 = Mock()
        mock_log1.model_dump.return_value = {"action_type": "draft_pick", "owner_id": 1}
        mock_log2.model_dump.return_value = {"action_type": "nomination", "owner_id": 2}

        logs = [mock_log1, mock_log2]

        logger = ActionLogger(Path("output.json"))
        logger._save_logs(logs)

        # Verify temp file was written with correct JSON
        expected_json = json.dumps(
            [
                {"action_type": "draft_pick", "owner_id": 1},
                {"action_type": "nomination", "owner_id": 2},
            ],
            indent=2,
            default=str,
        )

        mock_write_text.assert_called_once_with(expected_json)

        # Verify atomic replacement occurred
        mock_replace.assert_called_once_with(Path("output.json"))

    @patch("pathlib.Path.replace")
    @patch("pathlib.Path.write_text")
    def test_save_logs_handles_datetime_serialization(
        self, mock_write_text, mock_replace
    ):
        """Test _save_logs uses default=str for datetime serialization."""
        mock_log = Mock()
        mock_log.model_dump.return_value = {"timestamp": "datetime_object_here"}

        logger = ActionLogger(Path("datetime_test.json"))
        logger._save_logs([mock_log])

        # Verify json.dumps was called with default=str parameter
        mock_write_text.assert_called_once()
        call_args = mock_write_text.call_args[0][0]

        # Should be valid JSON string
        parsed = json.loads(call_args)
        assert len(parsed) == 1
        assert parsed[0]["timestamp"] == "datetime_object_here"
