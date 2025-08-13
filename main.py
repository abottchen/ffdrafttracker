"""Fantasy Football Draft Tracker - FastAPI Application"""

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from src.models import Configuration, DraftState, Nominated, Player, Team

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Fantasy Football Draft Tracker",
    description="Auction draft tracking tool with optimistic locking",
    version="1.0.0",
)

# Add CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Create directories if they don't exist
DATA_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)
TEMPLATES_DIR.mkdir(exist_ok=True)

# Mount static files (if directory exists and has files)
if STATIC_DIR.exists() and any(STATIC_DIR.iterdir()):
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Set up templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# File paths
DRAFT_STATE_FILE = DATA_DIR / "draft_state.json"
PLAYERS_FILE = DATA_DIR / "players.json"
OWNERS_FILE = DATA_DIR / "owners.json"
CONFIG_FILE = DATA_DIR / "config.json"
ACTION_LOG_FILE = DATA_DIR / "action_log.json"


# Request/Response models
class NominateRequest(BaseModel):
    owner_id: int
    player_id: int
    initial_bid: int
    expected_version: int


class BidRequest(BaseModel):
    owner_id: int
    bid_amount: int
    expected_version: int


class DraftRequest(BaseModel):
    owner_id: int
    player_id: int
    final_price: int
    expected_version: int


class DeleteNominateRequest(BaseModel):
    expected_version: int


class UndoDraftRequest(BaseModel):
    expected_version: int


class ResetRequest(BaseModel):
    expected_version: int | None = None
    force: bool = False


# Helper functions
def load_draft_state() -> DraftState:
    """Load current draft state from file."""
    if not DRAFT_STATE_FILE.exists():
        # Initialize with empty state
        initial_state = DraftState(
            nominated=None,
            available_player_ids=[],
            teams=[],
            next_to_nominate=1,
            version=1,
        )
        initial_state.save_to_file(DRAFT_STATE_FILE, increment_version=False)
        return initial_state
    return DraftState.load_from_file(DRAFT_STATE_FILE)


def load_players() -> list[Player]:
    """Load all players from file."""
    if not PLAYERS_FILE.exists():
        return []
    import json

    with open(PLAYERS_FILE) as f:
        players_data = json.load(f)
    return [Player(**p) for p in players_data]


def load_owners() -> dict[int, dict[str, str]]:
    """Load all owners from file as a map for O(1) lookups."""
    if not OWNERS_FILE.exists():
        return {}
    import json

    owners = {}
    with open(OWNERS_FILE) as f:
        owners_data = json.load(f)

    for owner_data in owners_data:
        owners[owner_data["id"]] = {
            "owner_name": owner_data["owner_name"],
            "team_name": owner_data["team_name"]
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


def check_version(current_version: int, expected_version: int) -> None:
    """Check version for optimistic locking."""
    if current_version != expected_version:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Draft state has changed (version {current_version} != "
                f"{expected_version}). Please refresh and try again."
            ),
        )


# Routes
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main application interface."""
    # Check if template exists
    template_path = TEMPLATES_DIR / "index.html"
    if not template_path.exists():
        return HTMLResponse(
            content="""
            <html>
                <head><title>Fantasy Football Draft Tracker</title></head>
                <body>
                    <h1>Fantasy Football Draft Tracker</h1>
                    <p>API is running. Template not yet created.</p>
                    <p>Visit <a href="/docs">/docs</a> for API documentation.</p>
                </body>
            </html>
            """,
            status_code=200,
        )

    # Load initial data for template
    draft_state = load_draft_state()
    return templates.TemplateResponse(
        "index.html", {"request": request, "draft_state": draft_state.model_dump()}
    )


@app.get("/api/v1/draft-state")
async def get_draft_state():
    """Get complete current draft state."""
    return load_draft_state()


@app.get("/api/v1/players")
async def get_all_players():
    """Get all player information."""
    return load_players()


@app.get("/api/v1/players/available")
async def get_available_players():
    """Get available players with details."""
    draft_state = load_draft_state()
    all_players = load_players()

    # Create player lookup
    player_dict = {p.id: p for p in all_players}

    # Return available players
    available = [
        player_dict[pid]
        for pid in draft_state.available_player_ids
        if pid in player_dict
    ]
    return available


@app.get("/api/v1/owners")
async def get_all_owners():
    """Get all owner information."""
    owners_dict = load_owners()
    # Convert dict back to list format for API compatibility
    return [
        {"id": owner_id, **owner_data}
        for owner_id, owner_data in owners_dict.items()
    ]


@app.get("/api/v1/owners/{owner_id}")
async def get_owner(owner_id: int):
    """Get specific owner information."""
    owners = load_owners()
    if owner_id not in owners:
        raise HTTPException(
            status_code=404, detail=f"Owner {owner_id} not found"
        )
    return {"id": owner_id, **owners[owner_id]}


@app.get("/api/v1/teams/{owner_id}")
async def get_team(owner_id: int):
    """Get specific team roster with player details."""
    draft_state = load_draft_state()

    # Find team for owner
    team = next((t for t in draft_state.teams if t.owner_id == owner_id), None)
    if not team:
        raise HTTPException(
            status_code=404, detail=f"Team not found for owner {owner_id}"
        )

    # Expand player details
    all_players = load_players()
    player_dict = {p.id: p for p in all_players}

    # Build response with expanded player info
    picks_with_details = []
    for pick in team.picks:
        player = player_dict.get(pick.player_id)
        if player:
            picks_with_details.append({
                "pick": pick.model_dump(),
                "player": player.model_dump(),
            })

    return {
        "owner_id": team.owner_id,
        "budget_remaining": team.budget_remaining,
        "picks": picks_with_details,
    }


@app.post("/api/v1/nominate")
async def nominate_player(request: NominateRequest):
    """Nominate a player for auction."""
    # Load current state
    draft_state = load_draft_state()
    config = load_configuration()

    # Check version
    check_version(draft_state.version, request.expected_version)

    # Validate no current nomination
    if draft_state.nominated is not None:
        raise HTTPException(
            status_code=422,
            detail=(
                "A player is already nominated. Complete or cancel the current "
                "nomination first."
            ),
        )

    # Validate bid amount
    if request.initial_bid < config.min_bid:
        raise HTTPException(
            status_code=422,
            detail=f"Initial bid must be at least ${config.min_bid}",
        )

    # Validate player is available
    if request.player_id not in draft_state.available_player_ids:
        raise HTTPException(
            status_code=422,
            detail=f"Player {request.player_id} is not available",
        )

    # Validate owner exists
    owners = load_owners()
    if request.owner_id not in owners:
        raise HTTPException(
            status_code=400,
            detail=f"Owner {request.owner_id} does not exist",
        )

    # Create nomination
    draft_state.nominated = Nominated(
        player_id=request.player_id,
        current_bid=request.initial_bid,
        current_bidder_id=request.owner_id,
        nominating_owner_id=request.owner_id,
    )

    # Save state with version increment
    draft_state.save_to_file(DRAFT_STATE_FILE)

    # Log action (simplified for now - full ActionLogger integration later)
    logger.info(
        f"Player {request.player_id} nominated by owner {request.owner_id} "
        f"for ${request.initial_bid}"
    )

    # Return success with player details
    players = load_players()
    player = next((p for p in players if p.id == request.player_id), None)

    return {
        "success": True,
        "nomination": draft_state.nominated.model_dump(),
        "player": player.model_dump() if player else None,
        "new_version": draft_state.version,
    }


@app.post("/api/v1/bid")
async def place_bid(request: BidRequest):
    """Place a bid on the currently nominated player."""
    # Load current state
    draft_state = load_draft_state()
    config = load_configuration()

    # Check version
    check_version(draft_state.version, request.expected_version)

    # Validate nomination exists
    if draft_state.nominated is None:
        raise HTTPException(
            status_code=422,
            detail="No player is currently nominated",
        )

    # Validate bid amount exceeds current
    if request.bid_amount <= draft_state.nominated.current_bid:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Bid must exceed current bid of ${draft_state.nominated.current_bid}"
            ),
        )

    # Validate bid meets minimum
    if request.bid_amount < config.min_bid:
        raise HTTPException(
            status_code=422,
            detail=f"Bid must be at least ${config.min_bid}",
        )

    # Find bidding team and validate budget
    team = next((t for t in draft_state.teams if t.owner_id == request.owner_id), None)
    if team and request.bid_amount > team.budget_remaining:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Insufficient budget. Need ${request.bid_amount} but only have "
                f"${team.budget_remaining}"
            ),
        )

    # Update bid
    previous_bid = draft_state.nominated.current_bid
    draft_state.nominated.current_bid = request.bid_amount
    draft_state.nominated.current_bidder_id = request.owner_id

    # Save state with version increment
    draft_state.save_to_file(DRAFT_STATE_FILE)

    # Log action
    logger.info(
        f"Owner {request.owner_id} bid ${request.bid_amount} on player "
        f"{draft_state.nominated.player_id}"
    )

    return {
        "success": True,
        "nomination": draft_state.nominated.model_dump(),
        "previous_bid": previous_bid,
        "new_version": draft_state.version,
    }


@app.post("/api/v1/draft")
async def complete_draft(request: DraftRequest):
    """Complete the auction and draft the player."""
    # Load current state
    draft_state = load_draft_state()

    # Check version
    check_version(draft_state.version, request.expected_version)

    # Validate nomination exists
    if draft_state.nominated is None:
        raise HTTPException(
            status_code=422,
            detail="No player is currently nominated",
        )

    # Validate player matches
    if draft_state.nominated.player_id != request.player_id:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Nominated player {draft_state.nominated.player_id} doesn't match "
                f"request {request.player_id}"
            ),
        )

    # Validate price matches current bid
    if draft_state.nominated.current_bid != request.final_price:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Final price ${request.final_price} doesn't match current bid "
                f"${draft_state.nominated.current_bid}"
            ),
        )

    # Validate owner matches current bidder
    if draft_state.nominated.current_bidder_id != request.owner_id:
        raise HTTPException(
            status_code=422,
            detail=f"Owner {request.owner_id} is not the current high bidder",
        )

    # Find or create team
    team = next((t for t in draft_state.teams if t.owner_id == request.owner_id), None)
    if not team:
        # Create new team with initial budget
        config = load_configuration()
        team = Team(
            owner_id=request.owner_id,
            budget_remaining=config.initial_budget,
            picks=[],
        )
        draft_state.teams.append(team)

    # Validate budget
    if request.final_price > team.budget_remaining:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Insufficient budget. Need ${request.final_price} but only have "
                f"${team.budget_remaining}"
            ),
        )

    # Create draft pick
    from src.models import DraftPick

    # Generate pick ID (simplified - in production use UUID or database ID)
    max_pick_id = max(
        [p.pick_id for t in draft_state.teams for p in t.picks], default=0
    )
    pick = DraftPick(
        pick_id=max_pick_id + 1,
        player_id=request.player_id,
        owner_id=request.owner_id,
        price=request.final_price,
    )

    # Update team
    team.picks.append(pick)
    team.budget_remaining -= request.final_price

    # Remove player from available
    draft_state.available_player_ids.remove(request.player_id)

    # Clear nomination
    draft_state.nominated = None

    # Update next to nominate (cycle through owners)
    owners = load_owners()
    owner_ids = sorted(owners.keys())  # Get ordered list of owner IDs
    if owner_ids:
        current_idx = (
            owner_ids.index(draft_state.next_to_nominate)
            if draft_state.next_to_nominate in owner_ids
            else 0
        )
        next_idx = (current_idx + 1) % len(owner_ids)
        draft_state.next_to_nominate = owner_ids[next_idx]
    else:
        draft_state.next_to_nominate = 1

    # Save state with version increment
    draft_state.save_to_file(DRAFT_STATE_FILE)

    # Log action
    logger.info(
        f"Player {request.player_id} drafted by owner {request.owner_id} "
        f"for ${request.final_price}"
    )

    return {
        "success": True,
        "pick": pick.model_dump(),
        "team": team.model_dump(),
        "next_to_nominate": draft_state.next_to_nominate,
        "new_version": draft_state.version,
    }


# Admin endpoints
@app.delete("/api/v1/nominate")
async def cancel_nomination(request: DeleteNominateRequest):
    """Cancel current nomination (admin action)."""
    # Load current state
    draft_state = load_draft_state()

    # Check version
    check_version(draft_state.version, request.expected_version)

    # Validate nomination exists
    if draft_state.nominated is None:
        raise HTTPException(
            status_code=422,
            detail="No nomination to cancel",
        )

    # Clear nomination
    cancelled_player = draft_state.nominated.player_id
    draft_state.nominated = None

    # Save state with version increment
    draft_state.save_to_file(DRAFT_STATE_FILE)

    logger.info(f"Nomination for player {cancelled_player} cancelled")

    return {
        "success": True,
        "cancelled_player_id": cancelled_player,
        "new_version": draft_state.version,
    }


@app.delete("/api/v1/draft/{pick_id}")
async def remove_draft_pick(pick_id: int, request: UndoDraftRequest):
    """Remove a draft pick and restore player to available pool."""
    # Load current state
    draft_state = load_draft_state()
    
    # Check version for optimistic locking
    check_version(draft_state.version, request.expected_version)
    
    # Find the pick and team
    pick_found = False
    target_team = None
    target_pick = None
    
    for team in draft_state.teams:
        for pick in team.picks:
            if pick.pick_id == pick_id:
                # Found the pick to remove
                target_team = team
                target_pick = pick
                pick_found = True
                break
        if pick_found:
            break
    
    if not pick_found:
        raise HTTPException(
            status_code=404,
            detail=f"Pick with ID {pick_id} not found"
        )
    
    # Critical integrity check: drafted player should NOT be in available pool
    if target_pick.player_id in draft_state.available_player_ids:
        raise HTTPException(
            status_code=422,
            detail=f"Data integrity error: Player {target_pick.player_id} is drafted but also in available pool. Manual intervention required."
        )
    
    # Remove pick from team
    target_team.picks.remove(target_pick)
    
    # Restore budget
    target_team.budget_remaining += target_pick.price
    
    # Add player back to available pool
    draft_state.available_player_ids.append(target_pick.player_id)
    draft_state.available_player_ids.sort()
    
    # Save state with version increment
    draft_state.save_to_file(DRAFT_STATE_FILE)
    
    logger.info(f"Removed pick {pick_id}, returned player {target_pick.player_id} to available pool")
    
    return {
        "success": True,
        "removed_pick_id": pick_id,
        "restored_player_id": target_pick.player_id,
        "new_version": draft_state.version
    }


@app.post("/api/v1/reset")
async def reset_draft(request: ResetRequest):
    """Reset draft to initial state (admin action)."""
    # Load configuration for initial state
    config = load_configuration()
    players = load_players()
    owners = load_owners()

    # If not forcing, check version
    if not request.force and request.expected_version is not None:
        current_state = load_draft_state()
        check_version(current_state.version, request.expected_version)

    # Create fresh draft state
    owner_ids = sorted(owners.keys()) if owners else []
    initial_state = DraftState(
        nominated=None,
        available_player_ids=[p.id for p in players],
        teams=[
            Team(owner_id=owner_id, budget_remaining=config.initial_budget, picks=[])
            for owner_id in owner_ids
        ],
        next_to_nominate=owner_ids[0] if owner_ids else 1,
        version=1,
    )

    # Save without incrementing version (fresh start at v1)
    initial_state.save_to_file(DRAFT_STATE_FILE, increment_version=False)

    logger.info("Draft reset to initial state")

    return {
        "success": True,
        "message": "Draft reset to initial state",
        "new_version": 1,
    }


# Run the application
if __name__ == "__main__":
    import uvicorn

    logger.info("Starting Fantasy Football Draft Tracker on http://localhost:8175")
    uvicorn.run(app, host="0.0.0.0", port=8175)

