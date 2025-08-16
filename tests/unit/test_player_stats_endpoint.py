"""
Unit tests for the player stats API endpoint.

Tests the /api/v1/player/stats endpoint behavior including:
- Successful loading of stats
- Handling missing files
- Handling invalid JSON
- Error recovery
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app
from src.models.player_stats import PlayerStatsCollection


class TestPlayerStatsEndpoint:
    """Test suite for the player stats endpoint."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_get_player_stats_success(self):
        """Test successful retrieval of player stats."""
        # Sample stats data
        sample_stats = {
            "4429202": {
                "bye_week": 5,
                "position": "RB",
                "team": "GB",
                "rushing": {
                    "carries": "66",
                    "yards": "311",
                    "avg": "4.7",
                    "tds": "2",
                    "long": "40",
                    "fumbles": "1",
                },
                "stats_summary": "Rush: 66att 311yds 2TD",
            },
            "3918298": {
                "bye_week": 7,
                "position": "QB",
                "team": "BUF",
                "passing": {
                    "completions": "359",
                    "attempts": "541",
                    "pct": "66.4",
                    "yards": "4306",
                    "avg": "8.0",
                    "tds": "29",
                    "ints": "18",
                    "sacks": "42",
                    "rating": "87.2",
                },
                "stats_summary": "359/541 4306yds 29TD 18INT",
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(sample_stats, f, indent=2)
            temp_file = Path(f.name)

        try:
            with patch("main.PLAYER_STATS_FILE", temp_file):
                response = self.client.get("/api/v1/player/stats")

            assert response.status_code == 200
            data = response.json()

            # Verify the structure matches our sample data
            assert "4429202" in data
            assert "3918298" in data

            # Check RB stats
            rb_stats = data["4429202"]
            assert rb_stats["bye_week"] == 5
            assert rb_stats["position"] == "RB"
            assert rb_stats["team"] == "GB"
            assert rb_stats["rushing"]["carries"] == "66"
            assert rb_stats["stats_summary"] == "Rush: 66att 311yds 2TD"

            # Check QB stats
            qb_stats = data["3918298"]
            assert qb_stats["bye_week"] == 7
            assert qb_stats["position"] == "QB"
            assert qb_stats["team"] == "BUF"
            assert qb_stats["passing"]["completions"] == "359"
            assert qb_stats["stats_summary"] == "359/541 4306yds 29TD 18INT"

        finally:
            temp_file.unlink(missing_ok=True)

    def test_get_player_stats_file_not_found(self):
        """Test behavior when player stats file doesn't exist."""
        non_existent_file = Path("/tmp/nonexistent_player_stats.json")

        with patch("main.PLAYER_STATS_FILE", non_existent_file):
            response = self.client.get("/api/v1/player/stats")

        assert response.status_code == 200
        data = response.json()

        # Should return empty collection
        assert data == {}

    def test_get_player_stats_invalid_json(self):
        """Test behavior when player stats file contains invalid JSON."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"invalid": json content}')  # Invalid JSON
            temp_file = Path(f.name)

        try:
            with patch("main.PLAYER_STATS_FILE", temp_file):
                response = self.client.get("/api/v1/player/stats")

            assert response.status_code == 200
            data = response.json()

            # Should return empty collection on error
            assert data == {}

        finally:
            temp_file.unlink(missing_ok=True)

    def test_get_player_stats_permission_error(self):
        """Test behavior when there's a permission error reading the file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": {"bye_week": 5}}, f)
            temp_file = Path(f.name)

        try:
            # Mock file exists but open raises PermissionError
            with patch("main.PLAYER_STATS_FILE", temp_file):
                with patch(
                    "builtins.open", side_effect=PermissionError("Access denied")
                ):
                    response = self.client.get("/api/v1/player/stats")

            assert response.status_code == 200
            data = response.json()

            # Should return empty collection on error
            assert data == {}

        finally:
            temp_file.unlink(missing_ok=True)

    def test_get_player_stats_model_validation_error(self):
        """Test behavior when data doesn't match the expected model structure."""
        # Data that doesn't match PlayerStatsCollection structure
        invalid_model_data = {
            "4429202": {
                "invalid_field": "value",
                # Missing required fields like position, team
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(invalid_model_data, f, indent=2)
            temp_file = Path(f.name)

        try:
            with patch("main.PLAYER_STATS_FILE", temp_file):
                response = self.client.get("/api/v1/player/stats")

            assert response.status_code == 200
            data = response.json()

            # Should return empty collection on validation error
            assert data == {}

        finally:
            temp_file.unlink(missing_ok=True)

    def test_get_player_stats_empty_file(self):
        """Test behavior when player stats file is empty."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            # Write empty content
            pass
        temp_file = Path(f.name)

        try:
            with patch("main.PLAYER_STATS_FILE", temp_file):
                response = self.client.get("/api/v1/player/stats")

            assert response.status_code == 200
            data = response.json()

            # Should return empty collection
            assert data == {}

        finally:
            temp_file.unlink(missing_ok=True)

    def test_player_stats_collection_model_methods(self):
        """Test the PlayerStatsCollection model helper methods."""
        sample_data = {
            "123": {
                "bye_week": 5,
                "position": "QB",
                "team": "KC",
                "stats_summary": "Test stats",
            }
        }

        collection = PlayerStatsCollection(sample_data)

        # Test get_player_stats
        player_stats = collection.get_player_stats(123)
        assert player_stats is not None
        assert player_stats.position == "QB"
        assert player_stats.team == "KC"

        # Test with non-existent player
        missing_stats = collection.get_player_stats(999)
        assert missing_stats is None

        # Test has_player
        assert collection.has_player(123) is True
        assert collection.has_player(999) is False

        # Test get_all_stats
        all_stats = collection.get_all_stats()
        assert len(all_stats) == 1
        assert "123" in all_stats
        assert all_stats["123"].position == "QB"
        assert all_stats["123"].team == "KC"
