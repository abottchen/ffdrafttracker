from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.models import DraftState


class TestDraftState:
    """Unit tests for DraftState model."""

    def test_draft_state_with_default_values(self):
        """Test DraftState uses default values when not provided."""
        draft_state = DraftState(next_to_nominate=1)

        assert draft_state.nominated is None
        assert draft_state.available_player_ids == []
        assert draft_state.teams == []
        assert draft_state.next_to_nominate == 1

    def test_draft_state_with_none_nominated(self):
        """Test DraftState with no current nomination."""
        draft_state = DraftState(
            nominated=None,
            available_player_ids=[101, 102],
            teams=[],
            next_to_nominate=2,
        )

        assert draft_state.nominated is None
        assert len(draft_state.available_player_ids) == 2
        assert draft_state.next_to_nominate == 2

    @patch("pathlib.Path.replace")
    @patch("pathlib.Path.write_text")
    def test_save_to_file_creates_temp_file_and_validates(
        self, mock_write_text, mock_replace
    ):
        """Test save_to_file creates temporary file and validates it."""
        draft_state = DraftState(next_to_nominate=1)
        file_path = Path("test.json")

        with patch.object(
            DraftState, "load_from_file", return_value=draft_state
        ) as mock_load:
            draft_state.save_to_file(file_path)

            # Should write to temp file
            temp_path = file_path.with_suffix(".tmp")
            mock_write_text.assert_called_once()

            # Should validate temp file
            mock_load.assert_called_once_with(temp_path)

            # Should atomically replace original file
            mock_replace.assert_called_once_with(file_path)

    @patch("pathlib.Path.replace")
    @patch("pathlib.Path.write_text")
    @patch.object(DraftState, "load_from_file")
    def test_save_to_file_atomic_replacement(
        self, mock_load, mock_write_text, mock_replace
    ):
        """Test save_to_file atomically replaces original file."""
        draft_state = DraftState(next_to_nominate=1)
        file_path = Path("atomic_test.json")

        mock_load.return_value = draft_state

        draft_state.save_to_file(file_path)

        # Should atomically replace original file
        mock_replace.assert_called_once_with(file_path)

    @patch("pathlib.Path.read_text")
    def test_load_from_file_calls_model_validate_json(self, mock_read_text):
        """Test load_from_file reads file and validates JSON."""
        json_content = '{"next_to_nominate": 5, "nominated": null}'
        mock_read_text.return_value = json_content

        with patch.object(
            DraftState, "model_validate_json", return_value=Mock()
        ) as mock_validate:
            DraftState.load_from_file(Path("test.json"))

            mock_read_text.assert_called_once()
            mock_validate.assert_called_once_with(json_content)

    @patch("pathlib.Path.read_text", side_effect=FileNotFoundError)
    def test_load_from_file_nonexistent_file_raises_error(self, mock_read_text):
        """Test load_from_file raises error for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            DraftState.load_from_file(Path("nonexistent_file.json"))

    @patch("pathlib.Path.read_text", return_value="{ invalid json }")
    def test_load_from_file_invalid_json_raises_error(self, mock_read_text):
        """Test load_from_file raises error for invalid JSON."""
        with pytest.raises(ValueError):
            DraftState.load_from_file(Path("invalid.json"))

    @patch("pathlib.Path.unlink")
    @patch("pathlib.Path.write_text")
    def test_save_to_file_cleans_up_temp_file_on_validation_failure(
        self, mock_write_text, mock_unlink
    ):
        """Test save_to_file cleans up temp file when validation fails."""
        draft_state = DraftState(next_to_nominate=1)
        file_path = Path("validation_fail_test.json")

        # Mock validation failure
        with patch.object(
            DraftState, "load_from_file", side_effect=ValueError("Validation failed")
        ):
            with pytest.raises(ValueError, match="Failed to validate temporary file"):
                draft_state.save_to_file(file_path)

            # Should clean up temp file
            mock_unlink.assert_called_once_with(missing_ok=True)
