"""Integration tests for main.py FastAPI endpoints.

Tests the full API stack with real file I/O and temporary directories.
Validates end-to-end behavior according to DESIGN.md specifications.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from main import app


class TestMainApiIntegration:
    """Integration test suite for FastAPI application."""

    def setup_method(self):
        """Set up integration test fixtures with real file I/O."""
        self.client = TestClient(app)
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create test data files
        self.setup_test_data()

        # Patch file paths to use temp directory
        self.draft_state_file = self.temp_dir / "draft_state.json"
        self.players_file = self.temp_dir / "players.json"
        self.owners_file = self.temp_dir / "owners.json"
        self.config_file = self.temp_dir / "config.json"

        # Patch the global file path constants
        patch_paths = patch.multiple(
            "main",
            DRAFT_STATE_FILE=self.draft_state_file,
            PLAYERS_FILE=self.players_file,
            OWNERS_FILE=self.owners_file,
            CONFIG_FILE=self.config_file,
        )
        patch_paths.start()
        self.patch_paths = patch_paths  # Store reference for manual cleanup

    def teardown_method(self):
        """Clean up after each test method."""
        # Restore original file paths
        self.patch_paths.stop()

        # Clean up temp directory
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except Exception:
            pass  # Ignore cleanup errors

    def setup_test_data(self):
        """Create test data files."""
        # Sample players
        players_data = [
            {
                "id": 1,
                "first_name": "Josh",
                "last_name": "Allen",
                "team": "BUF",
                "position": "QB",
            },
            {
                "id": 2,
                "first_name": "Christian",
                "last_name": "McCaffrey",
                "team": "SF",
                "position": "RB",
            },
            {
                "id": 3,
                "first_name": "Tyreek",
                "last_name": "Hill",
                "team": "MIA",
                "position": "WR",
            },
            {
                "id": 4,
                "first_name": "Travis",
                "last_name": "Kelce",
                "team": "KC",
                "position": "TE",
            },
        ]

        # Sample owners
        owners_data = [
            {"id": 1, "owner_name": "Rick Sanchez", "team_name": "Portal Gunners"},
            {"id": 2, "owner_name": "Morty Smith", "team_name": "Aw Geez"},
        ]

        # Sample configuration
        config_data = {
            "initial_budget": 200,
            "min_bid": 1,
            "position_maximums": {"QB": 2, "RB": 4, "WR": 6, "TE": 2, "K": 1},
            "total_rounds": 19,
        }

        # Initial draft state
        draft_state_data = {
            "nominated": None,
            "available_player_ids": [1, 2, 3, 4],
            "teams": [
                {"owner_id": 1, "budget_remaining": 200, "picks": []},
                {"owner_id": 2, "budget_remaining": 200, "picks": []},
            ],
            "next_to_nominate": 1,
            "version": 1,
        }

        # Write files
        (self.temp_dir / "players.json").write_text(json.dumps(players_data, indent=2))
        (self.temp_dir / "owners.json").write_text(json.dumps(owners_data, indent=2))
        (self.temp_dir / "config.json").write_text(json.dumps(config_data, indent=2))
        (self.temp_dir / "draft_state.json").write_text(
            json.dumps(draft_state_data, indent=2)
        )


    def test_full_auction_workflow(self):
        """Test complete auction workflow: nominate -> bid -> draft."""
        # Step 1: Nominate a player
        nominate_response = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,  # Josh Allen
                "initial_bid": 5,
                "expected_version": 1,
            },
        )

        assert nominate_response.status_code == 200
        nominate_data = nominate_response.json()
        assert nominate_data["success"] is True
        assert nominate_data["nomination"]["player_id"] == 1
        assert nominate_data["nomination"]["current_bid"] == 5
        new_version = nominate_data["new_version"]

        # Step 2: Place a higher bid
        bid_response = self.client.post(
            "/api/v1/bid",
            json={"owner_id": 2, "bid_amount": 10, "expected_version": new_version},
        )

        assert bid_response.status_code == 200
        bid_data = bid_response.json()
        assert bid_data["success"] is True
        assert bid_data["nomination"]["current_bid"] == 10
        assert bid_data["nomination"]["current_bidder_id"] == 2
        newer_version = bid_data["new_version"]

        # Step 3: Complete the draft
        draft_response = self.client.post(
            "/api/v1/draft",
            json={
                "owner_id": 2,
                "player_id": 1,
                "final_price": 10,
                "expected_version": newer_version,
            },
        )

        assert draft_response.status_code == 200
        draft_data = draft_response.json()
        assert draft_data["success"] is True
        assert draft_data["pick"]["player_id"] == 1
        assert draft_data["pick"]["price"] == 10
        assert draft_data["pick"]["owner_id"] == 2

        # Step 4: Verify state changes
        state_response = self.client.get("/api/v1/draft-state")
        state_data = state_response.json()

        # Nomination should be cleared
        assert state_data["nominated"] is None

        # Player should be removed from available
        assert 1 not in state_data["available_player_ids"]

        # Team should have the pick and reduced budget
        team_2 = next(t for t in state_data["teams"] if t["owner_id"] == 2)
        assert len(team_2["picks"]) == 1
        assert team_2["picks"][0]["player_id"] == 1
        assert team_2["budget_remaining"] == 190  # 200 - 10

    def test_version_consistency_across_operations(self):
        """Test optimistic locking with version numbers."""
        # Get initial version
        initial_state = self.client.get("/api/v1/draft-state").json()
        initial_version = initial_state["version"]

        # First client nominates
        nominate_response = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 5,
                "expected_version": initial_version,
            },
        )
        assert nominate_response.status_code == 200
        new_version = nominate_response.json()["new_version"]

        # Second client tries to use old version - should fail
        stale_bid_response = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 2,
                "bid_amount": 10,
                "expected_version": initial_version,  # Stale version
            },
        )
        assert stale_bid_response.status_code == 409
        assert "Draft state has changed" in stale_bid_response.json()["detail"]

        # Second client uses current version - should succeed
        fresh_bid_response = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 2,
                "bid_amount": 10,
                "expected_version": new_version,  # Current version
            },
        )
        assert fresh_bid_response.status_code == 200

    def test_data_persistence_and_retrieval(self):
        """Test that data persists correctly to files."""
        # Nominate a player
        self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 2,
                "initial_bid": 15,
                "expected_version": 1,
            },
        )

        # Verify file was updated
        draft_state_content = json.loads(self.draft_state_file.read_text())
        assert draft_state_content["nominated"]["player_id"] == 2
        assert draft_state_content["nominated"]["current_bid"] == 15
        assert draft_state_content["version"] == 2

        # Verify GET endpoints read from file correctly
        api_state = self.client.get("/api/v1/draft-state").json()
        assert api_state["nominated"]["player_id"] == 2
        assert api_state["nominated"]["current_bid"] == 15
        assert api_state["version"] == 2

    def test_budget_validation_integration(self):
        """Test budget validation across the full system."""
        # Set up a team with limited budget by drafting an expensive player first
        self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 180,
                "expected_version": 1,
            },
        )

        # Get new version after nomination
        state = self.client.get("/api/v1/draft-state").json()
        version_after_nominate = state["version"]

        # Complete draft for expensive player
        self.client.post(
            "/api/v1/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "final_price": 180,
                "expected_version": version_after_nominate,
            },
        )

        # Get new version after draft
        state = self.client.get("/api/v1/draft-state").json()
        version_after_draft = state["version"]

        # Try to nominate another player - this should succeed even with
        # insufficient budget
        # because budget validation happens during bidding, not nomination
        nominate_response = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,  # This owner now has only $20 left
                "player_id": 2,
                "initial_bid": 15,  # Less than remaining budget
                "expected_version": version_after_draft,
            },
        )
        assert nominate_response.status_code == 200

        # Get version after nomination
        state = self.client.get("/api/v1/draft-state").json()
        version_after_second_nominate = state["version"]

        # Try to bid amount that would prevent roster completion - this should fail
        # Owner 1 has $20 left and 1 player drafted, needs 18 more players
        # If they bid $19, they'd have $1 left but need $17 more for remaining spots
        bid_response = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 1,  # This owner has only $20 left, 1 player drafted
                "bid_amount": 19,  # Would leave $1, need $17 for remaining spots
                "expected_version": version_after_second_nominate,
            },
        )

        # Should fail due to insufficient budget for roster completion
        assert bid_response.status_code == 422
        assert "Insufficient budget" in bid_response.json()["detail"]
        assert "roster spots" in bid_response.json()["detail"]

        # Try a valid bid from owner 2 who has sufficient budget
        valid_bid_response = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 2,  # This owner has $200 left, 0 players drafted
                "bid_amount": 16,  # Exceeds current bid, allows roster completion
                "expected_version": version_after_second_nominate,
            },
        )

        # Should succeed because owner 2 has plenty of budget for roster completion
        assert valid_bid_response.status_code == 200

    def test_player_availability_consistency(self):
        """Test that player availability is maintained correctly."""
        # Get initial available players
        initial_available = self.client.get("/api/v1/players/available").json()
        initial_ids = [p["id"] for p in initial_available]
        assert 1 in initial_ids
        assert 2 in initial_ids

        # Draft a player
        self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 10,
                "expected_version": 1,
            },
        )

        state = self.client.get("/api/v1/draft-state").json()
        version_after_nominate = state["version"]

        self.client.post(
            "/api/v1/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "final_price": 10,
                "expected_version": version_after_nominate,
            },
        )

        # Verify player is no longer available
        updated_available = self.client.get("/api/v1/players/available").json()
        updated_ids = [p["id"] for p in updated_available]
        assert 1 not in updated_ids  # Player 1 should be drafted
        assert 2 in updated_ids  # Player 2 should still be available

        # Verify draft state consistency
        draft_state = self.client.get("/api/v1/draft-state").json()
        assert 1 not in draft_state["available_player_ids"]
        assert 2 in draft_state["available_player_ids"]

    def test_undo_draft_pick_integration(self):
        """Test undoing a draft pick restores state correctly."""
        # Draft a player first
        self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 25,
                "expected_version": 1,
            },
        )

        state = self.client.get("/api/v1/draft-state").json()
        version_after_nominate = state["version"]

        draft_response = self.client.post(
            "/api/v1/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "final_price": 25,
                "expected_version": version_after_nominate,
            },
        )

        pick_id = draft_response.json()["pick"]["pick_id"]

        # Get state after draft
        state_after_draft = self.client.get("/api/v1/draft-state").json()
        version_after_draft = state_after_draft["version"]

        # Verify player is drafted and budget reduced
        team_1 = next(t for t in state_after_draft["teams"] if t["owner_id"] == 1)
        assert len(team_1["picks"]) == 1
        assert team_1["budget_remaining"] == 175  # 200 - 25
        assert 1 not in state_after_draft["available_player_ids"]

        # Undo the draft pick
        undo_response = self.client.request(
            "DELETE",
            f"/api/v1/draft/{pick_id}",
            headers={"If-Match": f'"{version_after_draft}"'},
        )

        assert undo_response.status_code == 200
        undo_data = undo_response.json()
        assert undo_data["success"] is True
        assert undo_data["removed_pick_id"] == pick_id
        assert undo_data["restored_player_id"] == 1

        # Verify state is restored
        final_state = self.client.get("/api/v1/draft-state").json()
        team_1_restored = next(t for t in final_state["teams"] if t["owner_id"] == 1)
        assert len(team_1_restored["picks"]) == 0
        assert team_1_restored["budget_remaining"] == 200  # Budget restored
        assert 1 in final_state["available_player_ids"]  # Player back in pool

    def test_cancel_nomination_integration(self):
        """Test canceling a nomination restores state correctly."""
        # Nominate a player
        nominate_response = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 15,
                "expected_version": 1,
            },
        )

        version_after_nominate = nominate_response.json()["new_version"]

        # Verify nomination exists
        state = self.client.get("/api/v1/draft-state").json()
        assert state["nominated"]["player_id"] == 1

        # Cancel nomination
        cancel_response = self.client.request(
            "DELETE",
            "/api/v1/nominate",
            headers={"If-Match": f'"{version_after_nominate}"'},
        )

        assert cancel_response.status_code == 200
        cancel_data = cancel_response.json()
        assert cancel_data["success"] is True
        assert cancel_data["cancelled_player_id"] == 1

        # Verify nomination is cleared
        final_state = self.client.get("/api/v1/draft-state").json()
        assert final_state["nominated"] is None

    def test_reset_draft_integration(self):
        """Test resetting draft restores initial state."""
        # Make some changes to the draft state
        self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 10,
                "expected_version": 1,
            },
        )

        state = self.client.get("/api/v1/draft-state").json()
        version_after_nominate = state["version"]

        self.client.post(
            "/api/v1/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "final_price": 10,
                "expected_version": version_after_nominate,
            },
        )

        # Verify state has changes
        modified_state = self.client.get("/api/v1/draft-state").json()
        assert len(modified_state["teams"][0]["picks"]) == 1
        assert modified_state["teams"][0]["budget_remaining"] == 190

        # Reset draft
        reset_response = self.client.post("/api/v1/reset", json={"force": True})

        assert reset_response.status_code == 200
        reset_data = reset_response.json()
        assert reset_data["success"] is True
        assert reset_data["new_version"] == 1

        # Verify state is reset
        reset_state = self.client.get("/api/v1/draft-state").json()
        assert reset_state["nominated"] is None
        assert len(reset_state["teams"][0]["picks"]) == 0
        assert reset_state["teams"][0]["budget_remaining"] == 200
        assert set(reset_state["available_player_ids"]) == {1, 2, 3, 4}
        assert reset_state["version"] == 1
