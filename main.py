"""Fantasy Football Draft Tracker - FastAPI Application"""

import asyncio
import io
import logging
from pathlib import Path

from fastapi import APIRouter, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from src.booth.log import read_comments
from src.draft_rules import (
    max_bid,
    next_eligible_nominator,
    position_count,
    remaining_roster_spots,
)
from src.models import (
    Configuration,
    DraftPick,
    DraftState,
    Nominated,
    Owner,
    Player,
    Team,
)
from src.models.player_stats import PlayerStatsCollection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Serialise all state mutations so the load-check-save cycle is atomic.
_state_lock = asyncio.Lock()

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
PLAYER_STATS_FILE = DATA_DIR / "player_stats.json"
COMMENTS_FILE = DATA_DIR / "analyst-comments.jsonl"


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


class ResetRequest(BaseModel):
    expected_version: int | None = None
    force: bool = False


class AdminDraftRequest(BaseModel):
    owner_id: int
    player_id: int
    price: int
    expected_version: int


class TeamUpdateRequest(BaseModel):
    manually_done: bool
    expected_version: int


# Response-only models (computed, read-only enrichments over the persisted shape).
class TeamView(Team):
    max_bid: int | None = None  # None when the roster is full


class DraftStateResponse(DraftState):
    teams: list[TeamView] = Field(default_factory=list)
    up_next: int | None = None  # next distinct eligible nominator, or null


class CommentResponse(BaseModel):
    """One analyst-booth comment, tagged with its position in the log.

    ``seq`` is the 1-based position of the (committed) line in the append-only
    log; it is the cursor clients page against (``since`` / ``before``).
    """

    seq: int
    ts: str
    state_version: int
    persona: str
    text: str


# Per-parameter OpenAPI descriptions for the comments feed, shared so the admin
# and viewer specs stay identical.
_COMMENTS_SINCE_DESC = (
    "Return only comments with `seq` greater than this (live tail / forward polling)."
)
_COMMENTS_BEFORE_DESC = (
    "Return only comments with `seq` less than this (older history / backward paging)."
)
_COMMENTS_LIMIT_DESC = (
    "Cap the result to the most recent N comments of the matched window."
)


# Helper functions
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


def generate_draft_csv() -> str:
    """Generate CSV content based on current draft state."""
    import csv

    draft_state = load_draft_state()
    owners = load_owners()
    players = load_players()

    player_dict = {p.id: p for p in players}
    sorted_owner_ids = sorted(owners.keys())

    csv_output = io.StringIO()
    writer = csv.writer(csv_output, quoting=csv.QUOTE_ALL)

    # Row 1: owner names paired with empty cells
    header_row = []
    for owner_id in sorted_owner_ids:
        header_row.extend([owners[owner_id]["owner_name"], ""])
    writer.writerow(header_row)

    # Row 2: alternating Player / $ sub-headers
    sub_header = []
    for _ in sorted_owner_ids:
        sub_header.extend(["Player", "$"])
    writer.writerow(sub_header)

    # Collect picks per owner
    owner_picks = {}
    for team in draft_state.teams:
        if team.owner_id in sorted_owner_ids:
            owner_picks[team.owner_id] = team.picks

    max_picks = max(len(picks) for picks in owner_picks.values()) if owner_picks else 0

    for pick_index in range(max_picks):
        row = []
        for owner_id in sorted_owner_ids:
            picks = owner_picks.get(owner_id, [])
            if pick_index < len(picks):
                pick = picks[pick_index]
                player = player_dict.get(pick.player_id)
                if player:
                    name = f"{player.last_name}, {player.first_name}"
                    row.extend([name, str(pick.price)])
                else:
                    name = f"Unknown Player (ID: {pick.player_id})"
                    row.extend([name, str(pick.price)])
            else:
                row.extend(["", ""])
        writer.writerow(row)

    csv_content = csv_output.getvalue()
    csv_output.close()
    return csv_content


# ---------------------------------------------------------------------------
# Read-only API router, shared between the admin and viewer apps.
# ---------------------------------------------------------------------------
read_router = APIRouter()


@read_router.get("/api/v1/draft-state", response_model=DraftStateResponse)
def get_draft_state():
    """Get complete current draft state."""
    state = load_draft_state()
    config = load_configuration()

    team_views = [
        TeamView(**team.model_dump(), max_bid=max_bid(team, config))
        for team in state.teams
    ]
    up_next = next_eligible_nominator(
        state, config, from_id=state.next_to_nominate, inclusive=False
    )
    if up_next == state.next_to_nominate:
        up_next = None  # fewer than two eligible -> no distinct "up next"

    return DraftStateResponse(
        **state.model_dump(exclude={"teams"}),
        teams=team_views,
        up_next=up_next,
    )


@read_router.get("/api/v1/players", response_model=list[Player])
def get_all_players():
    """Get all player information."""
    return load_players()


@read_router.get("/api/v1/players/available", response_model=list[Player])
def get_available_players():
    """Get available players with details."""
    draft_state = load_draft_state()
    all_players = load_players()

    # Create player lookup
    player_dict = {p.id: p for p in all_players}

    # Return available players
    return [
        player_dict[pid]
        for pid in draft_state.available_player_ids
        if pid in player_dict
    ]


@read_router.get("/api/v1/player/stats", response_model=PlayerStatsCollection)
def get_player_stats():
    """Get player statistics and bye weeks. Returns empty collection if not found."""
    if not PLAYER_STATS_FILE.exists():
        logger.info("Player stats file not found, returning empty collection")
        return PlayerStatsCollection({})

    try:
        with open(PLAYER_STATS_FILE) as f:
            data = f.read()
        return PlayerStatsCollection.model_validate_json(data)
    except Exception as e:
        logger.error(f"Error loading player stats: {e}, returning empty collection")
        return PlayerStatsCollection({})


@read_router.get("/api/v1/owners", response_model=list[Owner])
def get_all_owners():
    """Get all owner information."""
    owners_dict = load_owners()
    # Convert dict back to list format for API compatibility
    return [
        {"id": owner_id, **owner_data} for owner_id, owner_data in owners_dict.items()
    ]


@read_router.get("/api/v1/config", response_model=Configuration)
def get_config():
    """Get draft configuration."""
    return load_configuration()


@read_router.get("/api/v1/owners/{owner_id}", response_model=Owner)
def get_owner(owner_id: int):
    """Get specific owner information."""
    owners = load_owners()
    if owner_id not in owners:
        raise HTTPException(status_code=404, detail=f"Owner {owner_id} not found")
    return {"id": owner_id, **owners[owner_id]}


@read_router.get("/api/v1/teams/{owner_id}")
def get_team(owner_id: int):
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
            picks_with_details.append(
                {
                    "pick": pick.model_dump(),
                    "player": player.model_dump(),
                }
            )

    return {
        "owner_id": team.owner_id,
        "budget_remaining": team.budget_remaining,
        "picks": picks_with_details,
    }


@read_router.get("/api/v1/comments", response_model=list[CommentResponse])
def get_comments(
    since: int | None = Query(default=None, ge=0, description=_COMMENTS_SINCE_DESC),
    before: int | None = Query(default=None, ge=0, description=_COMMENTS_BEFORE_DESC),
    limit: int | None = Query(default=None, ge=1, description=_COMMENTS_LIMIT_DESC),
):
    """Analyst-booth commentary, ordered oldest-first (ascending `seq`)."""
    comments = [
        CommentResponse(
            seq=i,
            ts=c.ts,
            state_version=c.state_version,
            persona=c.persona,
            text=c.text,
        )
        for i, c in enumerate(read_comments(COMMENTS_FILE), start=1)
    ]
    if since is not None:
        comments = [c for c in comments if c.seq > since]
    if before is not None:
        comments = [c for c in comments if c.seq < before]
    if limit is not None:
        comments = comments[-limit:]
    return comments


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
    config = load_configuration()
    return templates.TemplateResponse(
        request,
        "index.html",
        {"draft_state": draft_state.model_dump(), "config": config.model_dump()},
    )


# Include the shared read router on the admin app.
app.include_router(read_router)


@app.get("/api/v1/export/csv")
async def export_draft_csv():
    """Export current draft state as CSV file (admin only)."""
    try:
        csv_content = generate_draft_csv()

        # Return as streaming response with appropriate headers
        return StreamingResponse(
            io.BytesIO(csv_content.encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=draft_export.csv"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate CSV export: {str(e)}"
        )


@app.post("/api/v1/nominate")
async def nominate_player(request: NominateRequest):
    """Nominate a player for auction."""
    async with _state_lock:
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
                    "A player is already nominated. Complete or cancel the "
                    "current nomination first."
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

        # Find the nominating team and enforce the max-bid reserve rule.
        team = next(
            (t for t in draft_state.teams if t.owner_id == request.owner_id),
            None,
        )
        if team is not None:
            mb = max_bid(team, config)
            if mb is None:
                raise HTTPException(
                    status_code=422,
                    detail="Roster is full; this team cannot nominate.",
                )
            if request.initial_bid > mb:
                spots = remaining_roster_spots(team, config)
                remaining_after = team.budget_remaining - request.initial_bid
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Insufficient budget. After "
                        f"${request.initial_bid} bid, "
                        f"you would have ${remaining_after} left but "
                        f"need at least ${spots - 1} to fill remaining "
                        f"{spots - 1} roster spots"
                    ),
                )

        # Enforce position maximum for the nominating team.
        players = load_players()
        player = next((p for p in players if p.id == request.player_id), None)
        if player is not None:
            max_at_pos = config.position_maximums.get(player.position)
            player_positions = {p.id: p.position for p in players}
            if max_at_pos is not None:
                if team is not None and (
                    position_count(team, player.position, player_positions)
                    >= max_at_pos
                ):
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Team is already at the maximum of "
                            f"{max_at_pos} players at the "
                            f"{player.position} position"
                        ),
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

        # Return success with player details
        owner = owners.get(request.owner_id, {})

        # Log action with names
        player_name = (
            f"{player.first_name} {player.last_name}"
            if player
            else f"ID:{request.player_id}"
        )
        owner_name = owner.get("owner_name", f"ID:{request.owner_id}")
        logger.info(
            f"Player {player_name} nominated by {owner_name} for ${request.initial_bid}"
        )

        return {
            "success": True,
            "nomination": draft_state.nominated.model_dump(),
            "player": player.model_dump() if player else None,
            "new_version": draft_state.version,
        }


@app.post("/api/v1/bid")
async def place_bid(request: BidRequest):
    """Place a bid on the currently nominated player."""
    async with _state_lock:
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
                    f"Bid must exceed current bid of "
                    f"${draft_state.nominated.current_bid}"
                ),
            )

        # Validate bid meets minimum
        if request.bid_amount < config.min_bid:
            raise HTTPException(
                status_code=422,
                detail=f"Bid must be at least ${config.min_bid}",
            )

        # Find bidding team and validate budget
        team = next(
            (t for t in draft_state.teams if t.owner_id == request.owner_id),
            None,
        )
        if not team:
            raise HTTPException(
                status_code=422,
                detail=(f"Team not found for owner {request.owner_id} in draft state"),
            )

        # Reject if the bid would break roster completion.
        mb = max_bid(team, config)
        if mb is None:
            raise HTTPException(
                status_code=422,
                detail="Roster is full; this team cannot bid.",
            )
        if request.bid_amount > mb:
            spots = remaining_roster_spots(team, config)
            remaining_budget_after_bid = team.budget_remaining - request.bid_amount
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Insufficient budget. After "
                    f"${request.bid_amount} bid, "
                    f"you would have "
                    f"${remaining_budget_after_bid} left but need "
                    f"at least ${spots - 1} to fill remaining "
                    f"{spots - 1} roster spots"
                ),
            )

        # Enforce position maximum for the bidding team.
        players = load_players()
        player = next(
            (p for p in players if p.id == draft_state.nominated.player_id),
            None,
        )
        if player is not None:
            max_at_pos = config.position_maximums.get(player.position)
            if max_at_pos is not None:
                player_positions = {p.id: p.position for p in players}
                if (
                    position_count(team, player.position, player_positions)
                    >= max_at_pos
                ):
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            f"Team is already at the maximum of "
                            f"{max_at_pos} players at the "
                            f"{player.position} position"
                        ),
                    )

        # Update bid
        previous_bid = draft_state.nominated.current_bid
        draft_state.nominated.current_bid = request.bid_amount
        draft_state.nominated.current_bidder_id = request.owner_id

        # Save state with version increment
        draft_state.save_to_file(DRAFT_STATE_FILE)

        # Get names for logging
        owners = load_owners()
        owner = owners.get(request.owner_id, {})

        player_name = (
            f"{player.first_name} {player.last_name}"
            if player
            else f"ID:{draft_state.nominated.player_id}"
        )
        owner_name = owner.get("owner_name", f"ID:{request.owner_id}")

        # Log action
        logger.info(f"{owner_name} bid ${request.bid_amount} on {player_name}")

        return {
            "success": True,
            "nomination": draft_state.nominated.model_dump(),
            "previous_bid": previous_bid,
            "new_version": draft_state.version,
        }


@app.post("/api/v1/draft")
async def complete_draft(request: DraftRequest):
    """Complete the auction and draft the player."""
    async with _state_lock:
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
                    f"Nominated player "
                    f"{draft_state.nominated.player_id} doesn't "
                    f"match request {request.player_id}"
                ),
            )

        # Validate price matches current bid
        if draft_state.nominated.current_bid != request.final_price:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Final price ${request.final_price} doesn't "
                    f"match current bid "
                    f"${draft_state.nominated.current_bid}"
                ),
            )

        # Validate owner matches current bidder
        if draft_state.nominated.current_bidder_id != request.owner_id:
            raise HTTPException(
                status_code=422,
                detail=(f"Owner {request.owner_id} is not the current high bidder"),
            )

        # Find team (must exist - teams are immutable from owners.json)
        team = next(
            (t for t in draft_state.teams if t.owner_id == request.owner_id),
            None,
        )
        if not team:
            raise HTTPException(
                status_code=422,
                detail=(f"Team not found for owner {request.owner_id} in draft state"),
            )

        # Validate budget
        if request.final_price > team.budget_remaining:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Insufficient budget. Need "
                    f"${request.final_price} but only have "
                    f"${team.budget_remaining}"
                ),
            )

        # Create draft pick
        max_pick_id = max(
            [p.pick_id for t in draft_state.teams for p in t.picks],
            default=0,
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
        if request.player_id not in draft_state.available_player_ids:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Data integrity error: player "
                    f"{request.player_id} is "
                    "not in the available player pool"
                ),
            )
        draft_state.available_player_ids.remove(request.player_id)

        # Clear nomination
        draft_state.nominated = None

        # Advance to next eligible nominator.
        config = load_configuration()
        nxt = next_eligible_nominator(
            draft_state,
            config,
            from_id=draft_state.next_to_nominate,
            inclusive=False,
        )
        if nxt is not None:
            draft_state.next_to_nominate = nxt

        # Save state with version increment
        draft_state.save_to_file(DRAFT_STATE_FILE)

        # Get names for logging
        players = load_players()
        owners = load_owners()
        player = next((p for p in players if p.id == request.player_id), None)
        owner = owners.get(request.owner_id, {})

        player_name = (
            f"{player.first_name} {player.last_name}"
            if player
            else f"ID:{request.player_id}"
        )
        owner_name = owner.get("owner_name", f"ID:{request.owner_id}")

        # Log action
        logger.info(f"{player_name} drafted by {owner_name} for ${request.final_price}")

        return {
            "success": True,
            "pick": pick.model_dump(),
            "team": team.model_dump(),
            "next_to_nominate": draft_state.next_to_nominate,
            "new_version": draft_state.version,
        }


@app.post("/api/v1/admin/draft")
async def admin_draft_player(request: AdminDraftRequest):
    """Admin-only endpoint to draft a player directly without auction.

    Intentionally skips budget and position-max validation -- this is the
    admin escape hatch for keepers and mid-draft corrections.
    """
    async with _state_lock:
        # Load current state
        draft_state = load_draft_state()

        # Check version
        check_version(draft_state.version, request.expected_version)

        # Validate player exists in players database
        players = load_players()
        player = next((p for p in players if p.id == request.player_id), None)
        if not player:
            raise HTTPException(
                status_code=400,
                detail=(f"Player {request.player_id} not found in players database"),
            )

        # Reject if the player is currently nominated.
        if (
            draft_state.nominated is not None
            and draft_state.nominated.player_id == request.player_id
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Player {request.player_id} is currently "
                    "nominated. Cancel the nomination first."
                ),
            )

        # Validate player is available for draft
        if request.player_id not in draft_state.available_player_ids:
            raise HTTPException(
                status_code=422,
                detail=(f"Player {request.player_id} is not available for draft"),
            )

        # Validate owner exists
        owners = load_owners()
        if request.owner_id not in owners:
            raise HTTPException(
                status_code=400,
                detail=f"Owner {request.owner_id} not found",
            )

        # Validate price is positive
        if request.price <= 0:
            raise HTTPException(
                status_code=400,
                detail="Price must be greater than 0",
            )

        # Find team (must exist for valid owner)
        team = next(
            (t for t in draft_state.teams if t.owner_id == request.owner_id),
            None,
        )
        if not team:
            raise HTTPException(
                status_code=422,
                detail=(f"Team not found for owner {request.owner_id} in draft state"),
            )

        # Create draft pick
        all_picks = [pick for team in draft_state.teams for pick in team.picks]
        pick_id = max([pick.pick_id for pick in all_picks], default=0) + 1

        pick = DraftPick(
            pick_id=pick_id,
            player_id=request.player_id,
            owner_id=request.owner_id,
            price=request.price,
        )

        # Add pick to team and adjust budget
        team.picks.append(pick)
        team.budget_remaining -= request.price

        # Remove player from available list
        draft_state.available_player_ids.remove(request.player_id)

        # Repair the nominator pointer.
        config = load_configuration()
        nxt = next_eligible_nominator(
            draft_state,
            config,
            from_id=draft_state.next_to_nominate,
            inclusive=True,
        )
        if nxt is not None:
            draft_state.next_to_nominate = nxt

        # Save state with version increment
        draft_state.save_to_file(DRAFT_STATE_FILE)

        # Get names for logging (player already loaded above)
        owner = owners.get(request.owner_id, {})

        player_name = f"{player.first_name} {player.last_name}"
        owner_name = owner.get("owner_name", f"ID:{request.owner_id}")

        # Log action
        logger.info(
            f"ADMIN DRAFT: {owner_name} drafted {player_name} for ${request.price}"
        )

        return {
            "success": True,
            "pick": pick.model_dump(),
            "team": team.model_dump(),
            "new_version": draft_state.version,
        }


@app.patch("/api/v1/teams/{owner_id}")
async def update_team(owner_id: int, request: TeamUpdateRequest):
    """Set or clear a team's manually-done flag (admin action)."""
    async with _state_lock:
        draft_state = load_draft_state()
        check_version(draft_state.version, request.expected_version)

        team = next((t for t in draft_state.teams if t.owner_id == owner_id), None)
        if not team:
            raise HTTPException(
                status_code=404,
                detail=f"Team not found for owner {owner_id}",
            )

        team.manually_done = request.manually_done

        # Repair the nominator pointer.
        config = load_configuration()
        nxt = next_eligible_nominator(
            draft_state,
            config,
            from_id=draft_state.next_to_nominate,
            inclusive=True,
        )
        if nxt is not None:
            draft_state.next_to_nominate = nxt

        draft_state.save_to_file(DRAFT_STATE_FILE)

        owners = load_owners()
        owner_name = owners.get(owner_id, {}).get("owner_name", f"ID:{owner_id}")
        logger.info(f"Team for {owner_name} manually_done set to {team.manually_done}")

        return {
            "success": True,
            "owner_id": owner_id,
            "manually_done": team.manually_done,
            "next_to_nominate": draft_state.next_to_nominate,
            "new_version": draft_state.version,
        }


# Admin endpoints
@app.delete("/api/v1/nominate")
async def cancel_nomination(
    if_match: str = Header(
        ..., description="ETag for optimistic locking (expected version)"
    ),
):
    """Cancel current nomination (admin action)."""
    async with _state_lock:
        # Load current state
        draft_state = load_draft_state()

        # Parse ETag and check version for optimistic locking
        try:
            expected_version = int(if_match.strip('"'))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=("If-Match header must contain a valid version number"),
            )

        # Check version
        check_version(draft_state.version, expected_version)

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

        # Get player name for logging
        players = load_players()
        player = next((p for p in players if p.id == cancelled_player), None)
        player_name = (
            f"{player.first_name} {player.last_name}"
            if player
            else f"ID:{cancelled_player}"
        )

        logger.info(f"Nomination for {player_name} cancelled")

        return {
            "success": True,
            "cancelled_player_id": cancelled_player,
            "new_version": draft_state.version,
        }


@app.delete("/api/v1/draft/{pick_id}")
async def remove_draft_pick(
    pick_id: int,
    if_match: str = Header(
        ..., description="ETag for optimistic locking (expected version)"
    ),
):
    """Remove a draft pick and restore player to available pool."""
    async with _state_lock:
        # Load current state
        draft_state = load_draft_state()

        # Parse ETag and check version for optimistic locking
        try:
            expected_version = int(if_match.strip('"'))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=("If-Match header must contain a valid version number"),
            )

        check_version(draft_state.version, expected_version)

        # Find the pick and team
        pick_found = False
        target_team = None
        target_pick = None

        for team in draft_state.teams:
            for pick in team.picks:
                if pick.pick_id == pick_id:
                    target_team = team
                    target_pick = pick
                    pick_found = True
                    break
            if pick_found:
                break

        if not pick_found:
            raise HTTPException(
                status_code=404,
                detail=f"Pick with ID {pick_id} not found",
            )

        # Critical integrity check
        if target_pick.player_id in draft_state.available_player_ids:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Data integrity error: Player "
                    f"{target_pick.player_id} is drafted but also "
                    f"in available pool. Manual intervention "
                    f"required."
                ),
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

        # Get player name for logging
        players = load_players()
        player = next((p for p in players if p.id == target_pick.player_id), None)
        player_name = (
            f"{player.first_name} {player.last_name}"
            if player
            else f"ID:{target_pick.player_id}"
        )

        logger.info(f"Removed pick {pick_id}, returned {player_name} to available pool")

        return {
            "success": True,
            "removed_pick_id": pick_id,
            "restored_player_id": target_pick.player_id,
            "new_version": draft_state.version,
        }


@app.post("/api/v1/reset")
async def reset_draft(request: ResetRequest):
    """Reset draft to initial state (admin action)."""
    async with _state_lock:
        # Load configuration for initial state
        config = load_configuration()
        players = load_players()
        owners = load_owners()

        # If not forcing, require and check version
        if not request.force:
            if request.expected_version is None:
                raise HTTPException(
                    status_code=422,
                    detail=("expected_version is required unless force=true"),
                )
            current_state = load_draft_state()
            check_version(current_state.version, request.expected_version)

        # Create fresh draft state
        owner_ids = sorted(owners.keys()) if owners else []
        initial_state = DraftState(
            nominated=None,
            available_player_ids=[p.id for p in players],
            teams=[
                Team(
                    owner_id=owner_id,
                    budget_remaining=config.initial_budget,
                    picks=[],
                )
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


# Create a separate app instance for the team viewer
viewer_app = FastAPI(
    title="Fantasy Football Team Viewer",
    description="Read-only team viewing interface",
    version="1.0.0",
)

# Add CORS for viewer app
viewer_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for viewer app (same as main app)
if STATIC_DIR.exists() and any(STATIC_DIR.iterdir()):
    viewer_app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include the shared read router on the viewer app.
viewer_app.include_router(read_router)


# Team Viewer Routes
@viewer_app.get("/", response_class=HTMLResponse)
async def team_viewer(request: Request, team_id: int = 1):
    """Serve the team viewer interface."""
    # Check if template exists
    template_path = TEMPLATES_DIR / "team_viewer.html"
    if not template_path.exists():
        return HTMLResponse(
            content="""
            <html>
                <head><title>Team Viewer - Template Missing</title></head>
                <body style="background: #1a1a1a; color: #e0e0e0; \
font-family: Arial, sans-serif; padding: 20px;">
                    <h1>Team Viewer</h1>
                    <p>Template not yet created.</p>
                    <p>This page now has its own read-only API endpoints.</p>
                </body>
            </html>
            """,
            status_code=200,
        )

    config = load_configuration()
    return templates.TemplateResponse(
        request,
        "team_viewer.html",
        {"selected_team_id": team_id, "config": config.model_dump()},
    )


# Run the application
if __name__ == "__main__":
    import signal
    import sys
    from threading import Thread

    import uvicorn

    # Function to run the main app
    def run_main():
        logger.info("Starting Fantasy Football Draft Tracker on http://0.0.0.0:8175")
        uvicorn.run(app, host="0.0.0.0", port=8175)

    # Function to run the viewer app
    def run_viewer():
        logger.info("Starting Fantasy Football Team Viewer on http://0.0.0.0:8176")
        uvicorn.run(viewer_app, host="0.0.0.0", port=8176)

    # Signal handler for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Shutting down servers...")
        sys.exit(0)

    # Set up signal handling
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start both servers in separate threads (daemon threads exit when main exits)
    main_thread = Thread(target=run_main, daemon=True)
    viewer_thread = Thread(target=run_viewer, daemon=True)

    main_thread.start()
    viewer_thread.start()

    try:
        # Keep the main thread alive
        while True:
            main_thread.join(timeout=1)
            viewer_thread.join(timeout=1)
            if not main_thread.is_alive() or not viewer_thread.is_alive():
                break
    except KeyboardInterrupt:
        logger.info("Received KeyboardInterrupt, shutting down...")
        sys.exit(0)
