"""Unit tests for main.py FastAPI endpoints.

Tests validate API behavior according to DESIGN.md specifications.
Each endpoint test confirms:
- Request/response structure
- HTTP status codes
- Business logic validation
- Error handling
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from src.models import Configuration, DraftPick, DraftState, Nominated, Player, Team


class TestMainApp:
    """Test suite for FastAPI application endpoints."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = TestClient(app)

        # Sample test data
        self.sample_players = [
            Player(
                id=1, first_name="Josh", last_name="Allen", team="BUF", position="QB"
            ),
            Player(
                id=2,
                first_name="Christian",
                last_name="McCaffrey",
                team="SF",
                position="RB",
            ),
            Player(
                id=3, first_name="Tyreek", last_name="Hill", team="MIA", position="WR"
            ),
        ]

        self.sample_owners = {
            1: {"owner_name": "Rick Sanchez", "team_name": "Portal Gunners"},
            2: {"owner_name": "Morty Smith", "team_name": "Aw Geez"},
        }

        self.sample_teams = [
            Team(owner_id=1, budget_remaining=200, picks=[]),
            Team(
                owner_id=2,
                budget_remaining=180,
                picks=[DraftPick(pick_id=1, player_id=2, owner_id=2, price=20)],
            ),
        ]

        self.sample_draft_state = DraftState(
            nominated=None,
            available_player_ids=[1, 3],
            teams=self.sample_teams,
            next_to_nominate=1,
            version=5,
        )

    def create_mock_draft_state(
        self,
        nominated=None,
        available_player_ids=None,
        teams=None,
        next_to_nominate=1,
        version=5,
    ):
        """Helper to create a MagicMock that behaves like DraftState."""
        mock_state = MagicMock(spec=DraftState)
        mock_state.nominated = nominated
        mock_state.available_player_ids = available_player_ids or [1, 3]
        mock_state.teams = teams or self.sample_teams
        mock_state.next_to_nominate = next_to_nominate
        mock_state.version = version
        return mock_state


class TestGetEndpoints(TestMainApp):
    """Test GET endpoints."""

    def test_get_root_returns_html(self):
        """Test GET / returns HTML response."""
        with patch("main.load_draft_state") as mock_load:
            mock_load.return_value = self.sample_draft_state
            response = self.client.get("/")

            assert response.status_code == 200
            assert "text/html" in response.headers["content-type"]
            assert "Fantasy Football Draft Tracker" in response.text

    @patch("main.load_draft_state")
    def test_get_draft_state(self, mock_load):
        """Test GET /api/v1/draft-state."""
        mock_load.return_value = self.sample_draft_state

        response = self.client.get("/api/v1/draft-state")

        assert response.status_code == 200
        data = response.json()
        assert data["version"] == 5
        assert data["next_to_nominate"] == 1
        assert len(data["teams"]) == 2
        assert data["nominated"] is None

    @patch("main.load_players")
    def test_get_players(self, mock_load):
        """Test GET /api/v1/players."""
        mock_load.return_value = self.sample_players

        response = self.client.get("/api/v1/players")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["first_name"] == "Josh"
        assert data[0]["last_name"] == "Allen"

    @patch("main.load_players")
    @patch("main.load_draft_state")
    def test_get_available_players(self, mock_draft_state, mock_players):
        """Test GET /api/v1/players/available."""
        mock_players.return_value = self.sample_players
        mock_draft_state.return_value = self.sample_draft_state

        response = self.client.get("/api/v1/players/available")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2  # Only players 1 and 3 are available
        player_ids = [p["id"] for p in data]
        assert 1 in player_ids
        assert 3 in player_ids
        assert 2 not in player_ids  # Player 2 is drafted

    @patch("main.load_owners")
    def test_get_owners(self, mock_load):
        """Test GET /api/v1/owners."""
        mock_load.return_value = self.sample_owners

        response = self.client.get("/api/v1/owners")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["owner_name"] == "Rick Sanchez"

    @patch("main.load_owners")
    def test_get_owner_by_id_success(self, mock_load):
        """Test GET /api/v1/owners/{owner_id} with valid ID."""
        mock_load.return_value = self.sample_owners

        response = self.client.get("/api/v1/owners/1")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["owner_name"] == "Rick Sanchez"
        assert data["team_name"] == "Portal Gunners"

    @patch("main.load_owners")
    def test_get_owner_by_id_not_found(self, mock_load):
        """Test GET /api/v1/owners/{owner_id} with invalid ID."""
        mock_load.return_value = self.sample_owners

        response = self.client.get("/api/v1/owners/999")

        assert response.status_code == 404
        assert "Owner 999 not found" in response.json()["detail"]

    @patch("main.load_players")
    @patch("main.load_draft_state")
    def test_get_team_by_owner_id_success(self, mock_draft_state, mock_players):
        """Test GET /api/v1/teams/{owner_id} with valid ID."""
        mock_players.return_value = self.sample_players
        mock_draft_state.return_value = self.sample_draft_state

        response = self.client.get("/api/v1/teams/2")

        assert response.status_code == 200
        data = response.json()
        assert data["owner_id"] == 2
        assert data["budget_remaining"] == 180
        assert len(data["picks"]) == 1
        assert data["picks"][0]["player"]["first_name"] == "Christian"

    @patch("main.load_players")
    @patch("main.load_draft_state")
    def test_get_team_by_owner_id_not_found(self, mock_draft_state, mock_players):
        """Test GET /api/v1/teams/{owner_id} with invalid ID."""
        mock_players.return_value = self.sample_players
        mock_draft_state.return_value = self.sample_draft_state

        response = self.client.get("/api/v1/teams/999")

        assert response.status_code == 404
        assert "Team not found for owner 999" in response.json()["detail"]

    @patch("main.load_configuration")
    def test_get_config(self, mock_config):
        """Test GET /api/v1/config."""
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=1, position_maximums={}, total_rounds=15
        )

        response = self.client.get("/api/v1/config")

        assert response.status_code == 200
        data = response.json()
        assert data["initial_budget"] == 200
        assert data["min_bid"] == 1
        assert data["total_rounds"] == 15
        assert "position_maximums" in data

    @patch("main.load_players")
    @patch("main.load_owners")
    @patch("main.load_draft_state")
    def test_export_csv_success(self, mock_draft_state, mock_owners, mock_players):
        """Test GET /api/v1/export/csv returns properly formatted CSV."""
        # Setup mock data with some drafted players
        mock_players.return_value = self.sample_players
        mock_owners.return_value = self.sample_owners

        # Create teams with some picks for CSV content
        teams_with_picks = [
            Team(
                owner_id=1,
                budget_remaining=185,
                picks=[DraftPick(pick_id=1, player_id=1, owner_id=1, price=15)],
            ),
            Team(
                owner_id=2,
                budget_remaining=180,
                picks=[DraftPick(pick_id=2, player_id=2, owner_id=2, price=20)],
            ),
        ]

        mock_draft_state.return_value = self.create_mock_draft_state(
            nominated=None,
            available_player_ids=[3],
            teams=teams_with_picks
        )

        response = self.client.get("/api/v1/export/csv")

        # Validate response headers and status
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/csv; charset=utf-8"
        assert "attachment" in response.headers["content-disposition"]
        assert "draft_export.csv" in response.headers["content-disposition"]

        # Validate CSV content structure
        csv_content = response.content.decode("utf-8")
        lines = csv_content.strip().split("\n")

        # Should have at least 3 lines: header row, Player/$ row, and data row
        assert len(lines) >= 3

        # First row should have owner names alternating with empty cells
        first_row = lines[0]
        assert '"Rick Sanchez"' in first_row
        assert '"Morty Smith"' in first_row
        assert '""' in first_row

        # Second row should alternate Player and $ headers
        second_row = lines[1]
        assert '"Player"' in second_row
        assert '"$"' in second_row

        # Third row should have player data
        third_row = lines[2]
        assert '"Allen, Josh"' in third_row or '"McCaffrey, Christian"' in third_row
        assert "15" in third_row or "20" in third_row

    @patch("main.generate_draft_csv")
    def test_export_csv_handles_generation_error(self, mock_generate):
        """Test GET /api/v1/export/csv handles CSV generation errors."""
        mock_generate.side_effect = Exception("CSV generation failed")

        response = self.client.get("/api/v1/export/csv")

        assert response.status_code == 500
        assert "Failed to generate CSV export" in response.json()["detail"]
        assert "CSV generation failed" in response.json()["detail"]


class TestPostEndpoints(TestMainApp):
    """Test POST endpoints."""

    @patch("main.load_draft_state")
    @patch("main.load_owners")
    @patch("main.load_configuration")
    def test_nominate_success_200(self, mock_config, mock_owners, mock_draft_state):
        """Test POST /api/v1/nominate returns 200 with valid nomination."""
        # DESIGN.md: 200 - Success with nomination confirmation and player details
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=1, position_maximums={}, total_rounds=19
        )
        mock_owners.return_value = self.sample_owners
        mock_draft_state.return_value = self.create_mock_draft_state()

        response = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 15,
                "expected_version": 5,
            },
        )

        # Validate response structure per DESIGN.md
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "nomination" in data
        assert data["nomination"]["player_id"] == 1
        assert data["nomination"]["current_bid"] == 15
        assert data["nomination"]["current_bidder_id"] == 1
        assert data["nomination"]["nominating_owner_id"] == 1
        assert "new_version" in data

        # Validate business logic per DESIGN.md
        # Uses atomic file operations
        mock_draft_state.return_value.save_to_file.assert_called_once()

    @patch("main.load_draft_state")
    def test_nominate_409_version_mismatch(self, mock_draft_state):
        """Test POST /api/v1/nominate returns 409 for version mismatch."""
        # DESIGN.md: 409 - Conflict (version mismatch - state modified by
        # another operation)
        mock_draft_state.return_value = self.create_mock_draft_state()

        response = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 15,
                "expected_version": 3,  # Wrong version
            },
        )

        assert response.status_code == 409
        assert "Draft state has changed" in response.json()["detail"]

    @patch("main.load_draft_state")
    def test_nominate_422_nomination_already_active(self, mock_draft_state):
        """Test POST /api/v1/nominate returns 422 when nomination already active."""
        # DESIGN.md: 422 - Unprocessable (nomination already active, bid below minimum)
        nomination = Nominated(
            player_id=2, current_bidder_id=1, nominating_owner_id=1, current_bid=10
        )
        mock_draft_state.return_value = self.create_mock_draft_state(
            nominated=nomination
        )

        response = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 15,
                "expected_version": 5,
            },
        )

        assert response.status_code == 422
        assert "A player is already nominated" in response.json()["detail"]

    @patch("main.load_draft_state")
    @patch("main.load_owners")
    @patch("main.load_configuration")
    def test_nominate_422_bid_below_minimum(
        self, mock_config, mock_owners, mock_draft_state
    ):
        """Test POST /api/v1/nominate returns 422 for bid below minimum."""
        # DESIGN.md: Validates initial_bid >= min_bid from config
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=5, position_maximums={}, total_rounds=19
        )
        mock_owners.return_value = self.sample_owners
        mock_draft_state.return_value = self.create_mock_draft_state()

        response = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 3,  # Below min_bid of 5
                "expected_version": 5,
            },
        )

        assert response.status_code == 422
        assert "Initial bid must be at least" in response.json()["detail"]

    def test_nominate_400_missing_fields(self):
        """Test POST /api/v1/nominate returns 400 for missing required fields."""
        # DESIGN.md: 400 - Bad request (invalid player/owner ID, missing fields)
        response = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                # Missing player_id, initial_bid, expected_version
            },
        )

        assert (
            response.status_code == 422
        )  # FastAPI validation returns 422 for missing fields

    @patch("main.load_draft_state")
    def test_nominate_version_mismatch(self, mock_draft_state):
        """Test POST /api/v1/nominate with version mismatch."""
        mock_draft_state.return_value = self.create_mock_draft_state()

        response = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 15,
                "expected_version": 3,  # Wrong version
            },
        )

        assert response.status_code == 409
        assert "Draft state has changed" in response.json()["detail"]

    @patch("main.load_draft_state")
    def test_nominate_player_already_nominated(self, mock_draft_state):
        """Test POST /api/v1/nominate when player already nominated."""
        nomination = Nominated(
            player_id=2, current_bidder_id=1, nominating_owner_id=1, current_bid=10
        )
        mock_draft_state.return_value = self.create_mock_draft_state(
            nominated=nomination
        )

        response = self.client.post(
            "/api/v1/nominate",
            json={
                "owner_id": 1,
                "player_id": 1,
                "initial_bid": 15,
                "expected_version": 5,
            },
        )

        assert response.status_code == 422
        assert "A player is already nominated" in response.json()["detail"]

    @patch("main.load_draft_state")
    @patch("main.load_configuration")
    def test_bid_success_200(self, mock_config, mock_draft_state):
        """Test POST /api/v1/bid returns 200 with valid bid."""
        # DESIGN.md: 200 - Success with updated nomination info
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=1, position_maximums={}, total_rounds=19
        )

        nomination = Nominated(
            player_id=1, current_bidder_id=1, nominating_owner_id=1, current_bid=10
        )
        mock_draft_state.return_value = self.create_mock_draft_state(
            nominated=nomination, available_player_ids=[3]
        )

        response = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 2,
                "bid_amount": 15,  # Exceeds current bid of 10
                "expected_version": 5,
            },
        )

        # Validate response structure per DESIGN.md
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "nomination" in data
        assert data["nomination"]["current_bid"] == 15
        assert data["nomination"]["current_bidder_id"] == 2
        assert "new_version" in data

        # Validate business logic per DESIGN.md
        # Uses atomic file operations
        mock_draft_state.return_value.save_to_file.assert_called_once()

    @patch("main.load_draft_state")
    def test_bid_409_version_mismatch(self, mock_draft_state):
        """Test POST /api/v1/bid returns 409 for version mismatch."""
        # DESIGN.md: 409 - Conflict (version mismatch - state modified by
        # another operation)
        nomination = Nominated(
            player_id=1, current_bidder_id=1, nominating_owner_id=1, current_bid=10
        )
        mock_draft_state.return_value = self.create_mock_draft_state(
            nominated=nomination, available_player_ids=[3]
        )

        response = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 2,
                "bid_amount": 15,
                "expected_version": 3,  # Wrong version
            },
        )

        assert response.status_code == 409
        assert "Draft state has changed" in response.json()["detail"]

    @patch("main.load_draft_state")
    def test_bid_422_no_active_nomination(self, mock_draft_state):
        """Test POST /api/v1/bid returns 422 when no active nomination."""
        # DESIGN.md: 422 - Unprocessable (no active nomination, insufficient
        # bid amount, insufficient budget, position limit reached)
        mock_draft_state.return_value = self.create_mock_draft_state()  # No nomination

        response = self.client.post(
            "/api/v1/bid", json={"owner_id": 2, "bid_amount": 15, "expected_version": 5}
        )

        assert response.status_code == 422
        assert "No player is currently nominated" in response.json()["detail"]

    @patch("main.load_draft_state")
    @patch("main.load_configuration")
    def test_bid_422_insufficient_bid_amount(self, mock_config, mock_draft_state):
        """Test POST /api/v1/bid returns 422 for insufficient bid amount."""
        # DESIGN.md: Validates bid amount exceeds current bid and >= min_bid
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=1, position_maximums={}, total_rounds=19
        )

        nomination = Nominated(
            player_id=1, current_bidder_id=1, nominating_owner_id=1, current_bid=20
        )
        mock_draft_state.return_value = self.create_mock_draft_state(
            nominated=nomination, available_player_ids=[3]
        )

        response = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 2,
                "bid_amount": 15,  # Less than current bid of 20
                "expected_version": 5,
            },
        )

        assert response.status_code == 422
        assert "Bid must exceed current bid" in response.json()["detail"]

    @patch("main.load_draft_state")
    @patch("main.load_configuration")
    def test_bid_422_insufficient_budget(self, mock_config, mock_draft_state):
        """Test POST /api/v1/bid returns 422 for insufficient budget to complete
        roster."""
        # DESIGN.md: Validates owner has sufficient budget to complete full roster
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=1, position_maximums={}, total_rounds=19
        )

        # Team with 16 players already drafted and $20 remaining budget
        # With 19 total rounds, they need 3 more players
        existing_picks = [
            DraftPick(pick_id=i, player_id=i + 10, owner_id=2, price=10)
            for i in range(16)
        ]
        low_budget_teams = [
            Team(owner_id=1, budget_remaining=200, picks=[]),
            Team(
                owner_id=2, budget_remaining=20, picks=existing_picks
            ),  # 16 players, $20 left
        ]

        nomination = Nominated(
            player_id=1, current_bidder_id=1, nominating_owner_id=1, current_bid=3
        )
        mock_draft_state.return_value = self.create_mock_draft_state(
            nominated=nomination,
            available_player_ids=[1, 3],
            teams=low_budget_teams
        )

        response = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 2,
                "bid_amount": 19,  # Would leave only $1, but need $2 for 2 more players
                "expected_version": 5,
            },
        )

        assert response.status_code == 422
        assert "Insufficient budget" in response.json()["detail"]
        assert "roster spots" in response.json()["detail"]

    @patch("main.load_draft_state")
    @patch("main.load_configuration")
    def test_bid_422_sufficient_budget_for_roster_completion(
        self, mock_config, mock_draft_state
    ):
        """Test POST /api/v1/bid allows bid when budget can complete roster."""
        # DESIGN.md: Budget validation should allow bids that leave enough for
        # roster completion
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=1, position_maximums={}, total_rounds=19
        )

        # Team with 16 players already drafted and $20 remaining budget
        # With 19 total rounds, they need 3 more players
        existing_picks = [
            DraftPick(pick_id=i, player_id=i + 10, owner_id=2, price=10)
            for i in range(16)
        ]
        sufficient_budget_teams = [
            Team(owner_id=1, budget_remaining=200, picks=[]),
            Team(
                owner_id=2, budget_remaining=20, picks=existing_picks
            ),  # 16 players, $20 left
        ]

        nomination = Nominated(
            player_id=1, current_bidder_id=1, nominating_owner_id=1, current_bid=3
        )
        mock_draft_state.return_value = self.create_mock_draft_state(
            nominated=nomination,
            available_player_ids=[1, 3],
            teams=sufficient_budget_teams
        )

        response = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 2,
                "bid_amount": 18,  # Would leave $2, exactly enough for 2 more players
                "expected_version": 5,
            },
        )

        # Should succeed because $2 remaining is enough for 2 more $1 players
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch("main.load_draft_state")
    @patch("main.load_configuration")
    def test_bid_edge_case_one_dollar_for_one_player(
        self, mock_config, mock_draft_state
    ):
        """Test POST /api/v1/bid allows bid leaving exactly $1 for 1 remaining
        player."""
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=1, position_maximums={}, total_rounds=19
        )

        # Team with 18 players already drafted and $10 remaining budget
        # With 19 total rounds, they need 1 more player
        existing_picks = [
            DraftPick(pick_id=i, player_id=i + 10, owner_id=2, price=10)
            for i in range(18)
        ]
        teams_with_one_spot_left = [
            Team(owner_id=1, budget_remaining=200, picks=[]),
            Team(
                owner_id=2, budget_remaining=10, picks=existing_picks
            ),  # 18 players, $10 left
        ]

        nomination = Nominated(
            player_id=1, current_bidder_id=1, nominating_owner_id=1, current_bid=3
        )
        mock_draft_state.return_value = self.create_mock_draft_state(
            nominated=nomination,
            available_player_ids=[1, 3],
            teams=teams_with_one_spot_left
        )

        response = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 2,
                "bid_amount": 9,  # Would leave exactly $1 for exactly 1 more player
                "expected_version": 5,
            },
        )

        # Should succeed because $1 remaining is exactly enough for 1 more player
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @patch("main.load_draft_state")
    @patch("main.load_configuration")
    def test_bid_edge_case_zero_dollars_roster_complete(
        self, mock_config, mock_draft_state
    ):
        """Test POST /api/v1/bid allows bid using all money if it completes the
        roster."""
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=1, position_maximums={}, total_rounds=19
        )

        # Team with 18 players already drafted and $15 remaining budget
        # With 19 total rounds, they need 1 more player - this bid would complete roster
        existing_picks = [
            DraftPick(pick_id=i, player_id=i + 10, owner_id=2, price=10)
            for i in range(18)
        ]
        teams_ready_to_complete = [
            Team(owner_id=1, budget_remaining=200, picks=[]),
            Team(
                owner_id=2, budget_remaining=15, picks=existing_picks
            ),  # 18 players, $15 left
        ]

        nomination = Nominated(
            player_id=1, current_bidder_id=1, nominating_owner_id=1, current_bid=3
        )
        mock_draft_state.return_value = self.create_mock_draft_state(
            nominated=nomination,
            available_player_ids=[1, 3],
            teams=teams_ready_to_complete
        )

        response = self.client.post(
            "/api/v1/bid",
            json={
                "owner_id": 2,
                "bid_amount": 15,  # Uses all money but completes roster
                "expected_version": 5,
            },
        )

        # Should succeed because winning completes the roster (0 remaining spots)
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Validate business logic per DESIGN.md
        # Uses atomic file operations
        mock_draft_state.return_value.save_to_file.assert_called_once()

    @patch("main.load_draft_state")
    def test_draft_success(self, mock_draft_state):
        """Test POST /api/v1/draft with valid data."""
        nomination = Nominated(
            player_id=1, current_bidder_id=2, nominating_owner_id=1, current_bid=20
        )
        mock_draft_state.return_value = self.create_mock_draft_state(
            nominated=nomination,
            available_player_ids=[1, 3],  # Player 1 must be available to be drafted
        )

        with patch("main.load_owners") as mock_owners:
            mock_owners.return_value = self.sample_owners

            response = self.client.post(
                "/api/v1/draft",
                json={
                    "owner_id": 2,
                    "player_id": 1,
                    "final_price": 20,
                    "expected_version": 5,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["pick"]["player_id"] == 1
            assert data["pick"]["price"] == 20
            mock_draft_state.return_value.save_to_file.assert_called_once()

    @patch("main.load_draft_state")
    def test_reset_draft_success(self, mock_draft_state):
        """Test POST /api/v1/reset with valid data."""
        mock_draft_state.return_value = self.sample_draft_state

        with (
            patch("main.load_configuration") as mock_config,
            patch("main.load_players") as mock_players,
            patch("main.load_owners") as mock_owners,
            patch("main.DraftState") as mock_draft_class,
        ):
            mock_config.return_value = MagicMock(initial_budget=200)
            mock_players.return_value = self.sample_players
            mock_owners.return_value = self.sample_owners

            mock_initial_state = MagicMock()
            mock_draft_class.return_value = mock_initial_state

            response = self.client.post(
                "/api/v1/reset", json={"expected_version": 5, "force": False}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["new_version"] == 1
            mock_initial_state.save_to_file.assert_called_once()

    @patch("main.load_draft_state")
    @patch("main.load_configuration")
    @patch("main.load_owners")
    @patch("main.load_players")
    def test_admin_draft_success_200(
        self, mock_players, mock_owners, mock_config, mock_draft_state
    ):
        """Test POST /api/v1/admin/draft returns 200 with valid admin draft."""
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=1, position_maximums={}, total_rounds=17
        )
        mock_owners.return_value = self.sample_owners
        mock_players.return_value = self.sample_players
        mock_draft_state.return_value = self.create_mock_draft_state()

        response = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 25,
                "expected_version": 5,
            },
        )

        # Validate response structure
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "pick" in data
        assert data["pick"]["player_id"] == 1
        assert data["pick"]["price"] == 25
        assert data["pick"]["owner_id"] == 1
        assert "team" in data
        assert "new_version" in data

        # Validate business logic - uses atomic file operations
        mock_draft_state.return_value.save_to_file.assert_called_once()

    @patch("main.load_draft_state")
    def test_admin_draft_409_version_mismatch(self, mock_draft_state):
        """Test POST /api/v1/admin/draft returns 409 for version mismatch."""
        mock_draft_state.return_value = self.create_mock_draft_state()

        response = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 25,
                "expected_version": 3,  # Wrong version
            },
        )

        assert response.status_code == 409
        assert "Draft state has changed" in response.json()["detail"]

    @patch("main.load_draft_state")
    @patch("main.load_players")
    def test_admin_draft_422_player_not_available(self, mock_players, mock_draft_state):
        """Test POST /api/v1/admin/draft returns 422 for unavailable player."""
        # Player 2 exists but is not in available_player_ids
        mock_players.return_value = self.sample_players
        mock_draft_state.return_value = self.create_mock_draft_state(
            available_player_ids=[1, 3]  # Player 2 not available
        )

        response = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 2,  # Player 2 not available
                "price": 25,
                "expected_version": 5,
            },
        )

        assert response.status_code == 422
        assert "Player 2 is not available for draft" in response.json()["detail"]

    @patch("main.load_draft_state")
    @patch("main.load_players")
    def test_admin_draft_400_player_not_found(self, mock_players, mock_draft_state):
        """Test POST /api/v1/admin/draft returns 400 for player not in database."""
        mock_players.return_value = self.sample_players  # Only players 1, 2, 3
        mock_draft_state.return_value = self.create_mock_draft_state(
            available_player_ids=[
                1,
                3,
                999,
            ]  # Player 999 in available but not in database
        )

        response = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 999,  # Player not in database
                "price": 25,
                "expected_version": 5,
            },
        )

        assert response.status_code == 400
        assert "Player 999 not found in players database" in response.json()["detail"]

    @patch("main.load_draft_state")
    @patch("main.load_players")
    @patch("main.load_owners")
    def test_admin_draft_400_owner_not_found(
        self, mock_owners, mock_players, mock_draft_state
    ):
        """Test POST /api/v1/admin/draft returns 400 for invalid owner."""
        mock_players.return_value = self.sample_players
        mock_owners.return_value = self.sample_owners
        mock_draft_state.return_value = self.create_mock_draft_state()

        response = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 999,  # Invalid owner
                "player_id": 1,
                "price": 25,
                "expected_version": 5,
            },
        )

        assert response.status_code == 400
        assert "Owner 999 not found" in response.json()["detail"]

    @patch("main.load_draft_state")
    @patch("main.load_configuration")
    @patch("main.load_players")
    @patch("main.load_owners")
    def test_admin_draft_400_invalid_price(
        self, mock_owners, mock_players, mock_config, mock_draft_state
    ):
        """Test POST /api/v1/admin/draft returns 400 for invalid price."""
        mock_players.return_value = self.sample_players
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=1, position_maximums={}, total_rounds=17
        )
        mock_owners.return_value = self.sample_owners
        mock_draft_state.return_value = self.create_mock_draft_state()

        response = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 0,  # Invalid price
                "expected_version": 5,
            },
        )

        assert response.status_code == 400
        assert "Price must be greater than 0" in response.json()["detail"]

    @patch("main.load_draft_state")
    @patch("main.load_configuration")
    @patch("main.load_owners")
    @patch("main.load_players")
    def test_admin_draft_skips_budget_validation(
        self, mock_players, mock_owners, mock_config, mock_draft_state
    ):
        """Test POST /api/v1/admin/draft allows draft even with insufficient budget."""
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=1, position_maximums={}, total_rounds=17
        )
        mock_owners.return_value = self.sample_owners
        mock_players.return_value = self.sample_players

        # Create team with very low budget
        low_budget_team = Team(owner_id=1, budget_remaining=5, picks=[])
        mock_draft_state.return_value = self.create_mock_draft_state(
            teams=[low_budget_team, self.sample_teams[1]]
        )

        response = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 100,  # Way more than budget allows
                "expected_version": 5,
            },
        )

        # Should succeed despite insufficient budget
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["pick"]["price"] == 100

    @patch("main.load_draft_state")
    @patch("main.load_configuration")
    @patch("main.load_players")
    @patch("main.load_owners")
    def test_admin_draft_422_team_not_found(
        self, mock_owners, mock_players, mock_config, mock_draft_state
    ):
        """Test POST /api/v1/admin/draft returns 422 when team not found."""
        mock_players.return_value = self.sample_players
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=1, position_maximums={}, total_rounds=17
        )
        mock_owners.return_value = self.sample_owners

        # Draft state with no team for owner 1
        mock_draft_state.return_value = self.create_mock_draft_state(
            teams=[self.sample_teams[1]]  # Only team for owner 2
        )

        response = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,  # Valid owner but no team in draft state
                "player_id": 1,
                "price": 25,
                "expected_version": 5,
            },
        )

        assert response.status_code == 422
        assert "Team not found for owner 1 in draft state" in response.json()["detail"]

    @patch("main.load_draft_state")
    @patch("main.load_configuration")
    @patch("main.load_owners")
    @patch("main.load_players")
    def test_admin_draft_generates_pick_id(
        self, mock_players, mock_owners, mock_config, mock_draft_state
    ):
        """Test POST /api/v1/admin/draft generates correct pick_id."""
        mock_config.return_value = Configuration(
            initial_budget=200, min_bid=1, position_maximums={}, total_rounds=17
        )
        mock_owners.return_value = self.sample_owners
        mock_players.return_value = self.sample_players

        # Create teams with existing picks to test pick_id generation
        existing_picks = [
            DraftPick(pick_id=1, player_id=2, owner_id=2, price=20),
            DraftPick(pick_id=3, player_id=4, owner_id=1, price=15),
        ]
        teams_with_picks = [
            Team(owner_id=1, budget_remaining=185, picks=[existing_picks[1]]),
            Team(owner_id=2, budget_remaining=180, picks=[existing_picks[0]]),
        ]
        mock_draft_state.return_value = self.create_mock_draft_state(
            teams=teams_with_picks
        )

        response = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                "player_id": 1,
                "price": 25,
                "expected_version": 5,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should generate pick_id = max(existing) + 1 = 3 + 1 = 4
        assert data["pick"]["pick_id"] == 4

    def test_admin_draft_422_missing_fields(self):
        """Test POST /api/v1/admin/draft returns 422 for missing required fields."""
        response = self.client.post(
            "/api/v1/admin/draft",
            json={
                "owner_id": 1,
                # Missing player_id, price, expected_version
            },
        )

        assert (
            response.status_code == 422
        )  # FastAPI validation returns 422 for missing fields


class TestDeleteEndpoints(TestMainApp):
    """Test DELETE endpoints."""

    @patch("main.load_draft_state")
    def test_cancel_nomination_success(self, mock_draft_state):
        """Test DELETE /api/v1/nominate with valid nomination."""
        nomination = Nominated(
            player_id=1, current_bidder_id=1, nominating_owner_id=1, current_bid=10
        )
        mock_draft_state.return_value = self.create_mock_draft_state(
            nominated=nomination, available_player_ids=[3]
        )

        response = self.client.request(
            "DELETE", "/api/v1/nominate", headers={"If-Match": '"5"'}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["cancelled_player_id"] == 1
        mock_draft_state.return_value.save_to_file.assert_called_once()

    @patch("main.load_draft_state")
    def test_cancel_nomination_no_nomination(self, mock_draft_state):
        """Test DELETE /api/v1/nominate when no nomination exists."""
        mock_draft_state.return_value = self.sample_draft_state

        response = self.client.request(
            "DELETE", "/api/v1/nominate", headers={"If-Match": '"5"'}
        )

        assert response.status_code == 422
        assert "No nomination to cancel" in response.json()["detail"]

    @patch("main.load_draft_state")
    def test_remove_draft_pick_success(self, mock_draft_state):
        """Test DELETE /api/v1/draft/{pick_id} with valid pick."""
        mock_draft_state.return_value = self.create_mock_draft_state()

        response = self.client.request(
            "DELETE", "/api/v1/draft/1", headers={"If-Match": '"5"'}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["removed_pick_id"] == 1
        assert data["restored_player_id"] == 2
        mock_draft_state.return_value.save_to_file.assert_called_once()

    @patch("main.load_draft_state")
    def test_remove_draft_pick_not_found(self, mock_draft_state):
        """Test DELETE /api/v1/draft/{pick_id} with invalid pick."""
        mock_draft_state.return_value = self.create_mock_draft_state()

        response = self.client.request(
            "DELETE", "/api/v1/draft/999", headers={"If-Match": '"5"'}
        )

        assert response.status_code == 404
        assert "Pick with ID 999 not found" in response.json()["detail"]


class TestErrorHandling(TestMainApp):
    """Test error handling scenarios."""

    def test_version_check_function(self):
        """Test the check_version utility function."""
        from main import check_version

        # Should not raise for matching versions
        check_version(5, 5)

        # Should raise HTTPException for mismatched versions
        with pytest.raises(Exception):  # HTTPException
            check_version(5, 3)

    @patch("main.load_draft_state")
    def test_missing_request_body(self, mock_draft_state):
        """Test endpoints with missing request body."""
        mock_draft_state.return_value = self.sample_draft_state

        response = self.client.post("/api/v1/nominate")
        assert response.status_code == 422  # Validation error

    @patch("main.load_draft_state")
    def test_invalid_json(self, mock_draft_state):
        """Test endpoints with invalid JSON."""
        mock_draft_state.return_value = self.sample_draft_state

        response = self.client.post(
            "/api/v1/nominate",
            data="invalid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422
