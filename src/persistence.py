"""Data loading and file-path constants for the draft tracker."""

import json
from pathlib import Path

from src.models import Configuration, DraftState, Player, Team

_BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = _BASE_DIR / "data"

# File paths
DRAFT_STATE_FILE = DATA_DIR / "draft_state.json"
PLAYERS_FILE = DATA_DIR / "players.json"
OWNERS_FILE = DATA_DIR / "owners.json"
CONFIG_FILE = DATA_DIR / "config.json"
PLAYER_STATS_FILE = DATA_DIR / "player_stats.json"
COMMENTS_FILE = DATA_DIR / "analyst-comments.jsonl"


def load_draft_state() -> DraftState:
    """Load current draft state from file."""
    if not DRAFT_STATE_FILE.exists():
        # Initialize with proper state from owners and players
        config = load_configuration()
        players = load_players()
        owners = load_owners()
        owner_ids = sorted(owners.keys()) if owners else []

        initial_state = DraftState(
            nominated=None,
            available_player_ids=[p.id for p in players],
            teams=[
                Team(
                    owner_id=owner_id, budget_remaining=config.initial_budget, picks=[]
                )
                for owner_id in owner_ids
            ],
            next_to_nominate=owner_ids[0] if owner_ids else 1,
            version=1,
        )
        initial_state.save_to_file(DRAFT_STATE_FILE, increment_version=False)
        return initial_state
    return DraftState.load_from_file(DRAFT_STATE_FILE)


def load_players() -> list[Player]:
    """Load all players from file."""
    if not PLAYERS_FILE.exists():
        return []

    with open(PLAYERS_FILE) as f:
        players_data = json.load(f)
    return [Player(**p) for p in players_data]


def load_owners() -> dict[int, dict[str, str]]:
    """Load all owners from file as a map for O(1) lookups."""
    if not OWNERS_FILE.exists():
        return {}

    owners = {}
    with open(OWNERS_FILE) as f:
        owners_data = json.load(f)

    for owner_data in owners_data:
        owners[owner_data["id"]] = {
            "owner_name": owner_data["owner_name"],
            "team_name": owner_data["team_name"],
            "color": owner_data.get("color", "#888888"),
        }

    return owners


def load_configuration() -> Configuration:
    """Load configuration from file."""
    if not CONFIG_FILE.exists():
        # Return default configuration
        return Configuration(
            initial_budget=200,
            min_bid=1,
            position_maximums={
                "QB": 2,
                "RB": 4,
                "WR": 5,
                "TE": 2,
                "K": 1,
                "D/ST": 1,
            },
            total_rounds=15,
            data_directory=str(DATA_DIR),
        )
    return Configuration.load_from_file(CONFIG_FILE)
