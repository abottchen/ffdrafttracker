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

        # Patch the global file path constants. Both the loader functions and
        # the mutating routes reference these through the src.persistence module
        # namespace (reads via load_*(); writes via _persistence.DRAFT_STATE_FILE),
        # so patching src.persistence covers reads and writes alike.
        patch_paths = patch.multiple(
            "src.persistence",
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

        # Owner 1 now has $20 left, 1 pick, 18 open slots → max_bid = 20 - 17 = $3.
        # Nominating above max_bid is now rejected (D1 fix).
        over_max_nominate = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 2,
                "initial_bid": 15,
                "expected_version": version_after_draft,
            },
        )
        assert over_max_nominate.status_code == 422
        assert "Insufficient budget" in over_max_nominate.json()["detail"]

        # Nominating at the max bid ($3) succeeds.
        nominate_response = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 2,
                "initial_bid": 3,
                "expected_version": version_after_draft,
            },
        )
        assert nominate_response.status_code == 200

        # Get version after nomination
        state = self.client.get("/api/v1/draft-state").json()
        version_after_second_nominate = state["version"]

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

    def test_bid_rejected_above_max_bid(self):
        """A bid above the roster-completion max_bid is rejected with 422."""
        # Owner 1 nominates player 1 at $1 (config total_rounds=19, budget 200).
        self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 1,
                "expected_version": 1,
            },
        )
        state = self.client.get("/api/v1/draft-state").json()
        # Owner 2 (0 picks, 19 spots) max_bid = 200 - 18 = 182. Bid 183 must fail.
        resp = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 2,
                "bid_amount": 183,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 422
        assert "Insufficient budget" in resp.json()["detail"]
        assert "roster spots" in resp.json()["detail"]

    def test_bid_at_max_bid_succeeds(self):
        """A bid exactly at max_bid is allowed."""
        self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 1,
                "expected_version": 1,
            },
        )
        state = self.client.get("/api/v1/draft-state").json()
        resp = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 2,
                "bid_amount": 182,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 200

    def test_nominate_rejected_at_position_max(self):
        """Nominating a position the team is already maxed at returns 422."""
        # Re-seed with QB cap of 1 and two QBs so the cap is reachable.
        import json

        config_data = {
            "initial_budget": 200,
            "min_bid": 1,
            "position_maximums": {"QB": 1, "RB": 4, "WR": 6, "TE": 2, "K": 1},
            "total_rounds": 19,
        }
        self.config_file.write_text(json.dumps(config_data))
        players = json.loads(self.players_file.read_text())
        players.append(
            {
                "id": 5,
                "first_name": "Lamar",
                "last_name": "Jackson",
                "team": "BAL",
                "position": "QB",
            }
        )
        self.players_file.write_text(json.dumps(players))
        ds = json.loads(self.draft_state_file.read_text())
        ds["available_player_ids"].append(5)
        self.draft_state_file.write_text(json.dumps(ds))

        # Owner 1 admin-drafts QB player 1 -> now at the QB cap of 1.
        state = self.client.get("/api/v1/draft-state").json()
        self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 5,
                "expected_version": state["version"],
            },
        )
        state = self.client.get("/api/v1/draft-state").json()
        # Owner 1 tries to nominate the other QB -> 422.
        resp = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 5,
                "initial_bid": 1,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 422
        assert "position" in resp.json()["detail"].lower()

    def test_bid_rejected_at_position_max(self):
        """Bidding on a position the team is maxed at returns 422."""
        import json

        config_data = {
            "initial_budget": 200,
            "min_bid": 1,
            "position_maximums": {"QB": 1, "RB": 4, "WR": 6, "TE": 2, "K": 1},
            "total_rounds": 19,
        }
        self.config_file.write_text(json.dumps(config_data))
        players = json.loads(self.players_file.read_text())
        players.append(
            {
                "id": 5,
                "first_name": "Lamar",
                "last_name": "Jackson",
                "team": "BAL",
                "position": "QB",
            }
        )
        self.players_file.write_text(json.dumps(players))
        ds = json.loads(self.draft_state_file.read_text())
        ds["available_player_ids"].append(5)
        self.draft_state_file.write_text(json.dumps(ds))

        # Owner 2 admin-drafts QB player 1 -> at QB cap of 1.
        state = self.client.get("/api/v1/draft-state").json()
        self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 2,
                "player_id": 1,
                "price": 5,
                "expected_version": state["version"],
            },
        )
        # Owner 1 nominates the other QB (owner 1 has 0 QBs -> allowed).
        state = self.client.get("/api/v1/draft-state").json()
        self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 5,
                "initial_bid": 1,
                "expected_version": state["version"],
            },
        )
        # Owner 2 (already maxed at QB) tries to bid -> 422.
        state = self.client.get("/api/v1/draft-state").json()
        resp = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 2,
                "bid_amount": 2,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 422
        assert "position" in resp.json()["detail"].lower()

    def test_admin_draft_overrides_position_max(self):
        """admin/draft is an unbounded override and ignores position maximums."""
        import json

        config_data = {
            "initial_budget": 200,
            "min_bid": 1,
            "position_maximums": {"QB": 1, "RB": 4, "WR": 6, "TE": 2, "K": 1},
            "total_rounds": 19,
        }
        self.config_file.write_text(json.dumps(config_data))
        players = json.loads(self.players_file.read_text())
        players.append(
            {
                "id": 5,
                "first_name": "Lamar",
                "last_name": "Jackson",
                "team": "BAL",
                "position": "QB",
            }
        )
        self.players_file.write_text(json.dumps(players))
        ds = json.loads(self.draft_state_file.read_text())
        ds["available_player_ids"].append(5)
        self.draft_state_file.write_text(json.dumps(ds))

        # Owner 1 admin-drafts QB player 1 -> at the QB cap of 1.
        state = self.client.get("/api/v1/draft-state").json()
        first = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 5,
                "expected_version": state["version"],
            },
        )
        assert first.status_code == 200

        # Admin-draft a SECOND QB onto the same team -> still succeeds (unbounded).
        state = self.client.get("/api/v1/draft-state").json()
        second = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 5,
                "price": 5,
                "expected_version": state["version"],
            },
        )
        assert second.status_code == 200

        # Owner 1 now holds 2 QBs, exceeding the configured maximum of 1.
        state = self.client.get("/api/v1/draft-state").json()
        team1 = next(t for t in state["teams"] if t["owner_id"] == 1)
        assert sum(1 for p in team1["picks"] if p["player_id"] in (1, 5)) == 2

    def test_bid_rejected_when_roster_full(self):
        """A full-roster team's bid is rejected with a clean message (no negatives)."""
        import json

        config_data = {
            "initial_budget": 200,
            "min_bid": 1,
            "position_maximums": {"QB": 2, "RB": 4, "WR": 6, "TE": 2, "K": 1},
            "total_rounds": 1,
        }
        self.config_file.write_text(json.dumps(config_data))

        # Owner 1 admin-drafts a player -> roster full (1/1).
        state = self.client.get("/api/v1/draft-state").json()
        self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 5,
                "expected_version": state["version"],
            },
        )
        # Owner 2 nominates a different player.
        state = self.client.get("/api/v1/draft-state").json()
        self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 2,
                "player_id": 2,
                "initial_bid": 1,
                "expected_version": state["version"],
            },
        )
        # Owner 1 (full roster) tries to bid -> 422 with a sensible message.
        state = self.client.get("/api/v1/draft-state").json()
        resp = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 1,
                "bid_amount": 2,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "full" in detail.lower()
        assert "-1" not in detail

    def test_draft_advances_to_next_owner(self):
        """After a draft, next_to_nominate moves to the next eligible owner."""
        self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 5,
                "expected_version": 1,
            },
        )
        state = self.client.get("/api/v1/draft-state").json()
        self.client.post(
            "/api/v1/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "final_price": 5,
                "expected_version": state["version"],
            },
        )
        state = self.client.get("/api/v1/draft-state").json()
        assert state["next_to_nominate"] == 2  # advanced from 1

    def test_admin_draft_skips_filled_nominator(self):
        """If admin-draft fills the current nominator's roster, the turn passes."""
        import json

        # Tiny roster so a single admin-draft completes owner 1.
        config_data = {
            "initial_budget": 200,
            "min_bid": 1,
            "position_maximums": {"QB": 2, "RB": 4, "WR": 6, "TE": 2, "K": 1},
            "total_rounds": 1,
        }
        self.config_file.write_text(json.dumps(config_data))
        # next_to_nominate is 1; admin-draft a player onto owner 1 -> roster full.
        state = self.client.get("/api/v1/draft-state").json()
        assert state["next_to_nominate"] == 1
        self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 5,
                "expected_version": state["version"],
            },
        )
        state = self.client.get("/api/v1/draft-state").json()
        assert state["next_to_nominate"] == 2  # owner 1 now full -> advance

    def test_patch_team_marks_done(self):
        """PATCH sets manually_done and bumps the version."""
        state = self.client.get("/api/v1/draft-state").json()
        resp = self.client.patch(
            "/api/v1/teams/1",
            json={
                "manually_done": True,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["manually_done"] is True
        new_state = self.client.get("/api/v1/draft-state").json()
        team1 = next(t for t in new_state["teams"] if t["owner_id"] == 1)
        assert team1["manually_done"] is True

    def test_patch_team_marking_current_nominator_advances_turn(self):
        """Marking the current nominator done passes the turn on."""
        state = self.client.get("/api/v1/draft-state").json()
        assert state["next_to_nominate"] == 1
        self.client.patch(
            "/api/v1/teams/1",
            json={
                "manually_done": True,
                "expected_version": state["version"],
            },
        )
        state = self.client.get("/api/v1/draft-state").json()
        assert state["next_to_nominate"] == 2

    def test_patch_team_can_clear_done(self):
        """manually_done can be toggled back off."""
        state = self.client.get("/api/v1/draft-state").json()
        self.client.patch(
            "/api/v1/teams/1",
            json={
                "manually_done": True,
                "expected_version": state["version"],
            },
        )
        state = self.client.get("/api/v1/draft-state").json()
        resp = self.client.patch(
            "/api/v1/teams/1",
            json={
                "manually_done": False,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 200
        assert resp.json()["manually_done"] is False

    def test_patch_team_version_conflict(self):
        """A stale expected_version yields 409."""
        resp = self.client.patch(
            "/api/v1/teams/1",
            json={
                "manually_done": True,
                "expected_version": 999,
            },
        )
        assert resp.status_code == 409

    def test_patch_unknown_team_404(self):
        state = self.client.get("/api/v1/draft-state").json()
        resp = self.client.patch(
            "/api/v1/teams/999",
            json={
                "manually_done": True,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 404

    def test_draft_state_exposes_max_bid_and_up_next(self):
        """draft-state carries per-team max_bid + manually_done and up_next."""
        state = self.client.get("/api/v1/draft-state").json()
        # total_rounds=19, budget 200, 0 picks -> max_bid = 200 - 18 = 182.
        team1 = next(t for t in state["teams"] if t["owner_id"] == 1)
        assert team1["max_bid"] == 182
        assert team1["manually_done"] is False
        # Two eligible teams (owners 1 and 2); from owner 1 up_next is 2.
        assert state["up_next"] == 2

    def test_max_bid_none_when_roster_full(self):
        """A full roster reports max_bid = null."""
        import json

        config_data = {
            "initial_budget": 200,
            "min_bid": 1,
            "position_maximums": {"QB": 2, "RB": 4, "WR": 6, "TE": 2, "K": 1},
            "total_rounds": 1,
        }
        self.config_file.write_text(json.dumps(config_data))
        state = self.client.get("/api/v1/draft-state").json()
        self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 5,
                "expected_version": state["version"],
            },
        )
        state = self.client.get("/api/v1/draft-state").json()
        team1 = next(t for t in state["teams"] if t["owner_id"] == 1)
        assert team1["max_bid"] is None

    def test_up_next_null_with_one_eligible_team(self):
        """up_next is null when only one team can still nominate."""
        import json

        config_data = {
            "initial_budget": 200,
            "min_bid": 1,
            "position_maximums": {"QB": 2, "RB": 4, "WR": 6, "TE": 2, "K": 1},
            "total_rounds": 1,
        }
        self.config_file.write_text(json.dumps(config_data))
        # Fill owner 2's roster -> only owner 1 eligible.
        state = self.client.get("/api/v1/draft-state").json()
        self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 2,
                "player_id": 2,
                "price": 5,
                "expected_version": state["version"],
            },
        )
        state = self.client.get("/api/v1/draft-state").json()
        assert state["next_to_nominate"] == 1
        assert state["up_next"] is None

    def test_owners_include_default_color(self):
        """Owners without a seeded color report the default gray."""
        owners = self.client.get("/api/v1/owners").json()
        assert all("color" in o for o in owners)
        assert owners[0]["color"] == "#888888"

    def test_owner_color_passthrough(self):
        """A seeded color is returned verbatim."""
        import json

        owners_data = [
            {
                "id": 1,
                "owner_name": "Rick",
                "team_name": "Portal Gunners",
                "color": "#21D4FD",
            },
            {
                "id": 2,
                "owner_name": "Morty",
                "team_name": "Aw Geez",
                "color": "#FF5CA8",
            },
        ]
        self.owners_file.write_text(json.dumps(owners_data))
        owner = self.client.get("/api/v1/owners/1").json()
        assert owner["color"] == "#21D4FD"

    def test_root_injects_config_into_context(self):
        """root() passes the full config object into the template context."""
        from unittest.mock import MagicMock

        from fastapi.responses import HTMLResponse

        import main

        with patch.object(
            main.templates,
            "TemplateResponse",
            MagicMock(return_value=HTMLResponse("ok")),
        ) as m:
            self.client.get("/")
        context = m.call_args.args[2]
        assert "config" in context
        assert context["config"]["total_rounds"] == 19  # from the test fixture

    def test_viewer_injects_config_into_context(self):
        """team_viewer() passes the full config object into the template context."""
        from unittest.mock import MagicMock

        from fastapi.responses import HTMLResponse
        from fastapi.testclient import TestClient

        import main

        viewer_client = TestClient(main.viewer_app)
        with patch.object(
            main.templates,
            "TemplateResponse",
            MagicMock(return_value=HTMLResponse("ok")),
        ) as m:
            viewer_client.get("/")
        context = m.call_args.args[2]
        assert "config" in context
        assert context["config"]["total_rounds"] == 19

    def test_duplicate_mutation_same_version_yields_409(self):
        """Two sequential mutations with the same expected_version:
        one succeeds (200) and the other is rejected (409)."""
        state = self.client.get("/api/v1/draft-state").json()
        version = state["version"]

        # First admin-draft succeeds
        first = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 5,
                "expected_version": version,
            },
        )
        assert first.status_code == 200

        # Second admin-draft with the same expected_version is rejected
        second = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 2,
                "player_id": 2,
                "price": 5,
                "expected_version": version,
            },
        )
        assert second.status_code == 409
        assert "Draft state has changed" in second.json()["detail"]

    def test_transfer_pick_success(self):
        """Atomically transfer a pick from one team to another."""
        # Admin-draft player 1 onto owner 1.
        state = self.client.get("/api/v1/draft-state").json()
        draft_resp = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 30,
                "expected_version": state["version"],
            },
        )
        assert draft_resp.status_code == 200
        pick_id = draft_resp.json()["pick"]["pick_id"]

        state = self.client.get("/api/v1/draft-state").json()

        # Transfer the pick to owner 2.
        resp = self.client.post(
            "/api/v1/admin/transfer",
            json={
                "pick_id": pick_id,
                "to_owner_id": 2,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["from_owner_id"] == 1
        assert data["to_owner_id"] == 2
        assert data["pick"]["player_id"] == 1
        assert data["pick"]["price"] == 30

        # Verify state: owner 1 budget restored, owner 2 budget deducted.
        final = self.client.get("/api/v1/draft-state").json()
        team1 = next(t for t in final["teams"] if t["owner_id"] == 1)
        team2 = next(t for t in final["teams"] if t["owner_id"] == 2)
        assert team1["budget_remaining"] == 200  # refunded
        assert len(team1["picks"]) == 0
        assert team2["budget_remaining"] == 170  # 200 - 30
        assert len(team2["picks"]) == 1
        assert team2["picks"][0]["player_id"] == 1
        # Player should NOT be in available pool (still drafted).
        assert 1 not in final["available_player_ids"]

    def test_transfer_pick_not_found(self):
        """Transfer with an invalid pick_id returns 404."""
        state = self.client.get("/api/v1/draft-state").json()
        resp = self.client.post(
            "/api/v1/admin/transfer",
            json={
                "pick_id": 999,
                "to_owner_id": 2,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 404

    def test_transfer_pick_version_conflict(self):
        """Transfer with stale expected_version returns 409."""
        state = self.client.get("/api/v1/draft-state").json()
        self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 10,
                "expected_version": state["version"],
            },
        )
        # Use the stale version.
        resp = self.client.post(
            "/api/v1/admin/transfer",
            json={
                "pick_id": 1,
                "to_owner_id": 2,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 409

    def test_transfer_pick_same_team_rejected(self):
        """Transfer to the same team is rejected with 422."""
        state = self.client.get("/api/v1/draft-state").json()
        draft_resp = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 10,
                "expected_version": state["version"],
            },
        )
        pick_id = draft_resp.json()["pick"]["pick_id"]
        state = self.client.get("/api/v1/draft-state").json()
        resp = self.client.post(
            "/api/v1/admin/transfer",
            json={
                "pick_id": pick_id,
                "to_owner_id": 1,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 422
        assert "same" in resp.json()["detail"].lower()

    def test_transfer_pick_insufficient_budget(self):
        """Transfer rejected when destination team cannot afford the pick."""
        # Drain owner 2's budget almost completely.
        state = self.client.get("/api/v1/draft-state").json()
        self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 2,
                "player_id": 2,
                "price": 195,
                "expected_version": state["version"],
            },
        )
        # Draft a $10 player onto owner 1.
        state = self.client.get("/api/v1/draft-state").json()
        draft_resp = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 3,
                "price": 10,
                "expected_version": state["version"],
            },
        )
        pick_id = draft_resp.json()["pick"]["pick_id"]
        state = self.client.get("/api/v1/draft-state").json()
        # Owner 2 has $5 left but the pick costs $10.
        resp = self.client.post(
            "/api/v1/admin/transfer",
            json={
                "pick_id": pick_id,
                "to_owner_id": 2,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 422
        assert "budget" in resp.json()["detail"].lower()

    def test_transfer_pick_position_limit(self):
        """Transfer rejected when destination team is at position maximum."""
        import json

        config_data = {
            "initial_budget": 200,
            "min_bid": 1,
            "position_maximums": {"QB": 1, "RB": 4, "WR": 6, "TE": 2, "K": 1},
            "total_rounds": 19,
        }
        self.config_file.write_text(json.dumps(config_data))
        players = json.loads(self.players_file.read_text())
        players.append(
            {
                "id": 5,
                "first_name": "Lamar",
                "last_name": "Jackson",
                "team": "BAL",
                "position": "QB",
            }
        )
        self.players_file.write_text(json.dumps(players))
        ds = json.loads(self.draft_state_file.read_text())
        ds["available_player_ids"].append(5)
        self.draft_state_file.write_text(json.dumps(ds))

        # Owner 2 admin-drafts QB player 1 -> at QB cap of 1.
        state = self.client.get("/api/v1/draft-state").json()
        self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 2,
                "player_id": 1,
                "price": 5,
                "expected_version": state["version"],
            },
        )
        # Owner 1 admin-drafts the other QB.
        state = self.client.get("/api/v1/draft-state").json()
        draft_resp = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 5,
                "price": 5,
                "expected_version": state["version"],
            },
        )
        pick_id = draft_resp.json()["pick"]["pick_id"]
        # Transfer the QB from owner 1 to owner 2 (already at QB max) -> 422.
        state = self.client.get("/api/v1/draft-state").json()
        resp = self.client.post(
            "/api/v1/admin/transfer",
            json={
                "pick_id": pick_id,
                "to_owner_id": 2,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 422
        assert "position" in resp.json()["detail"].lower()

    def test_transfer_pick_dest_roster_full(self):
        """Transfer rejected when destination team roster is full."""
        import json

        config_data = {
            "initial_budget": 200,
            "min_bid": 1,
            "position_maximums": {"QB": 2, "RB": 4, "WR": 6, "TE": 2, "K": 1},
            "total_rounds": 1,
        }
        self.config_file.write_text(json.dumps(config_data))

        # Owner 2 admin-drafts a player -> roster full (1/1).
        state = self.client.get("/api/v1/draft-state").json()
        self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 2,
                "player_id": 2,
                "price": 5,
                "expected_version": state["version"],
            },
        )
        # Owner 1 drafts a player.
        state = self.client.get("/api/v1/draft-state").json()
        draft_resp = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 5,
                "expected_version": state["version"],
            },
        )
        pick_id = draft_resp.json()["pick"]["pick_id"]
        # Transfer to owner 2 (roster full) -> 422.
        state = self.client.get("/api/v1/draft-state").json()
        resp = self.client.post(
            "/api/v1/admin/transfer",
            json={
                "pick_id": pick_id,
                "to_owner_id": 2,
                "expected_version": state["version"],
            },
        )
        assert resp.status_code == 422
        assert "full" in resp.json()["detail"].lower()
