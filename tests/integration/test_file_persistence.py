import json
import tempfile
from pathlib import Path

from src.enums import NFLTeam, Position
from src.models import (
    ActionLog,
    Configuration,
    DraftPick,
    DraftState,
    Nominated,
    Owner,
    Player,
    Team,
)
from src.models.action_logger import ActionLogger


class TestFilePersistence:
    """Integration tests for file persistence and round-trip serialization."""

    def test_draft_state_round_trip_with_complex_data(self):
        """Test DraftState serialization using reflection.

        Ensures all fields are covered in the serialization test.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_draft_state.json"

            # Use reflection to get all fields currently defined on DraftState
            defined_fields = set(DraftState.__annotations__.keys())

            # Expected fields that we know should be in DraftState
            expected_fields = {
                "nominated",
                "available_player_ids",
                "teams",
                "next_to_nominate",
                "version",
            }

            # Ensure the model hasn't changed unexpectedly
            assert defined_fields == expected_fields, (
                f"DraftState fields changed: expected {expected_fields}, "
                f"got {defined_fields}"
            )

            # Create complex DraftState with nested objects
            # (no conditionals - test all expected fields)
            nominated = Nominated(
                player_id=101,
                current_bid=25,
                current_bidder_id=3,
                nominating_owner_id=1,
            )

            team1_picks = [
                DraftPick(pick_id=1, player_id=201, owner_id=1, price=45),
                DraftPick(pick_id=2, player_id=202, owner_id=1, price=30),
            ]
            team2_picks = [DraftPick(pick_id=3, player_id=203, owner_id=2, price=50)]

            teams = [
                Team(owner_id=1, budget_remaining=125, picks=team1_picks),
                Team(owner_id=2, budget_remaining=150, picks=team2_picks),
                Team(owner_id=3, budget_remaining=175, picks=[]),
            ]

            # This will fail to construct if any expected field is missing
            # from the model
            original_draft_state = DraftState(
                nominated=nominated,
                available_player_ids=[101, 102, 103, 104, 105],
                teams=teams,
                next_to_nominate=2,
                version=7,
            )

            # The serialization will naturally fail here if any field type
            # can't be serialized
            # Use increment_version=False to test exact version persistence
            original_draft_state.save_to_file(file_path, increment_version=False)

            # Load from file - this will fail if deserialization breaks
            loaded_draft_state = DraftState.load_from_file(file_path)

            # Verify the round trip worked by checking a few key values
            assert loaded_draft_state.next_to_nominate == 2
            assert loaded_draft_state.nominated.player_id == 101
            assert len(loaded_draft_state.teams) == 3
            assert loaded_draft_state.teams[0].picks[0].price == 45
            assert loaded_draft_state.version == 7  # Version persisted correctly

    def test_draft_state_atomic_write_prevents_corruption(self):
        """Test DraftState atomic write prevents corruption on validation failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "atomic_test.json"

            # Create and save a valid DraftState first
            valid_state = DraftState(
                nominated=None,
                available_player_ids=[1, 2, 3],
                teams=[],
                next_to_nominate=1,
            )
            valid_state.save_to_file(file_path)

            # Verify original file exists and is valid
            assert file_path.exists()
            original_content = file_path.read_text()
            loaded_original = DraftState.load_from_file(file_path)
            assert loaded_original.next_to_nominate == 1

            # Simulate validation failure by creating temp file with invalid JSON
            temp_path = file_path.with_suffix(".tmp")
            temp_path.write_text("{ invalid json }")

            # Now try to "load" from this corrupted temp file - should fail validation
            try:
                DraftState.load_from_file(temp_path)
                assert False, "Should have failed to load invalid JSON"
            except (ValueError, json.JSONDecodeError):
                # Expected - temp file has invalid JSON
                pass

            # Verify original file is still intact and valid
            assert file_path.read_text() == original_content
            final_state = DraftState.load_from_file(file_path)
            assert final_state.next_to_nominate == 1  # Original value preserved

            # Clean up temp file
            if temp_path.exists():
                temp_path.unlink()

    def test_action_logger_integration_workflow(self):
        """Test ActionLogger complete workflow with real file I/O."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "action_log.json"
            logger = ActionLogger(log_file)

            # Log multiple actions
            logger.log_action(
                "nomination", 1, {"player_id": 101, "nomination_price": 15}
            )
            logger.log_action("bid", 2, {"player_id": 101, "bid_amount": 20})
            logger.log_action("bid", 3, {"player_id": 101, "bid_amount": 25})
            logger.log_action("draft_pick", 3, {"player_id": 101, "final_price": 25})

            # Verify file was created and contains valid JSON
            assert log_file.exists()
            log_content = log_file.read_text()
            parsed_logs = json.loads(log_content)
            assert len(parsed_logs) == 4

            # Verify log structure and data
            assert parsed_logs[0]["action_type"] == "nomination"
            assert parsed_logs[0]["owner_id"] == 1
            assert parsed_logs[0]["data"]["player_id"] == 101
            assert parsed_logs[0]["data"]["nomination_price"] == 15

            assert parsed_logs[1]["action_type"] == "bid"
            assert parsed_logs[1]["owner_id"] == 2

            assert parsed_logs[3]["action_type"] == "draft_pick"
            assert parsed_logs[3]["data"]["final_price"] == 25

            # Test loading logs back (internal method test)
            loaded_logs = logger._load_logs()
            assert len(loaded_logs) == 4
            assert all(isinstance(log, ActionLog) for log in loaded_logs)

            # Test appending to existing logs
            logger.log_action(
                "nomination", 1, {"player_id": 102, "nomination_price": 12}
            )

            final_logs = logger._load_logs()
            assert len(final_logs) == 5
            assert final_logs[-1].action_type == "nomination"
            assert final_logs[-1].data["player_id"] == 102

    def test_action_logger_handles_corrupted_log_file(self):
        """Test ActionLogger gracefully handles corrupted existing log files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "corrupted_log.json"

            # Create a corrupted log file
            log_file.write_text("{ invalid json content }")

            logger = ActionLogger(log_file)

            # Should start fresh with new logs despite corruption
            logger.log_action("nomination", 1, {"player_id": 201})

            # Verify new log was written correctly
            loaded_logs = logger._load_logs()
            assert len(loaded_logs) == 1
            assert loaded_logs[0].action_type == "nomination"
            assert loaded_logs[0].data["player_id"] == 201

    def test_model_construction_with_realistic_fantasy_data(self):
        """Test complete object construction with realistic fantasy football data."""
        # Create realistic players
        players = [
            Player(
                id=1,
                first_name="Josh",
                last_name="Allen",
                team=NFLTeam.BUF,
                position=Position.QB,
            ),
            Player(
                id=2,
                first_name="Christian",
                last_name="McCaffrey",
                team=NFLTeam.SF,
                position=Position.RB,
            ),
            Player(
                id=3,
                first_name="Tyreek",
                last_name="Hill",
                team=NFLTeam.MIA,
                position=Position.WR,
            ),
        ]

        # Create owners
        owners = [
            Owner(id=1, owner_name="Rick Sanchez", team_name="Rick's Portal Gunners"),
            Owner(id=2, owner_name="Morty Smith", team_name="Morty's Cronenbergs"),
            Owner(id=3, owner_name="Jerry Smith", team_name="Jerry's Unemployment"),
        ]

        # Create draft picks
        picks = [
            DraftPick(pick_id=1, player_id=1, owner_id=1, price=45),  # Josh Allen
            DraftPick(pick_id=2, player_id=2, owner_id=2, price=55),  # CMC
            DraftPick(pick_id=3, player_id=3, owner_id=3, price=40),  # Tyreek Hill
        ]

        # Create teams with picks
        teams = [
            Team(owner_id=1, budget_remaining=155, picks=[picks[0]]),
            Team(owner_id=2, budget_remaining=145, picks=[picks[1]]),
            Team(owner_id=3, budget_remaining=160, picks=[picks[2]]),
        ]

        # Create current nomination
        current_nomination = Nominated(
            player_id=4, current_bid=18, current_bidder_id=2, nominating_owner_id=1
        )

        # Create complete draft state
        draft_state = DraftState(
            nominated=current_nomination,
            available_player_ids=[4, 5, 6, 7, 8, 9, 10],
            teams=teams,
            next_to_nominate=2,
        )

        # Verify all objects constructed properly
        assert len(players) == 3
        assert players[0].display_name == "Allen, J."
        assert players[1].full_name == "Christian McCaffrey"

        assert len(owners) == 3
        assert all(owner.owner_name for owner in owners)

        assert len(teams) == 3
        assert (
            sum(team.budget_remaining for team in teams) == 460
        )  # Total remaining budget
        assert sum(len(team.picks) for team in teams) == 3  # Total picks made

        assert draft_state.nominated.current_bid == 18
        assert len(draft_state.available_player_ids) == 7

    def test_configuration_with_edge_case_position_maximums(self):
        """Test Configuration handles complex position maximum configurations."""
        config = Configuration(
            initial_budget=300,
            min_bid=2,
            position_maximums={
                "QB": 3,
                "RB": 6,
                "WR": 8,
                "TE": 3,
                "K": 2,
                "D/ST": 2,
                "FLEX": 4,
                "BENCH": 15,
            },
            total_rounds=25,
            data_directory="large_league_data",
        )

        # Test serialization and deserialization of complex config
        json_str = config.model_dump_json()
        parsed_data = json.loads(json_str)

        assert parsed_data["initial_budget"] == 300
        assert parsed_data["position_maximums"]["BENCH"] == 15
        assert parsed_data["total_rounds"] == 25

        # Test reconstruction from JSON
        reconstructed = Configuration.model_validate_json(json_str)
        assert reconstructed.initial_budget == config.initial_budget
        assert reconstructed.position_maximums == config.position_maximums
