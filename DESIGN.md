# Fantasy Football Draft Tracker Tool

## Overview
A local fantasy football auction draft tracking tool with a web-based interface for single-user operation with screenshare capability. Designed as a monolithic Python application for simplicity and future multi-user extensibility.

## Architecture

### Application Structure
**Technology Stack:** FastAPI (Python) serving both API and frontend  
**Architecture:** Dual-port application with stateless API design  
**Deployment:** Single Python process via command-line execution serving both applications  

**Main Draft Application:**
- **Port:** 8175 (localhost only)
- **Purpose:** Interactive draft management with full admin capabilities
- **Access:** Draft administrator interface

**Team Viewer Application:**
- **Port:** 8176 (all network interfaces - 0.0.0.0)
- **Purpose:** Read-only team viewing for network participants
- **Access:** External network viewing interface

### Frontend Applications

#### Main Draft Interface (Port 8175)
**Technology Stack:** HTML/CSS/JavaScript with vanilla JS  
**Served By:** FastAPI using Jinja2 templates and static files  
**Access:** Browser-based interface at localhost:8175  
**Security:** Localhost only for admin control  

**Key Features:**
- Interactive nomination and bidding controls
- Real-time draft progress bar with color-coded completion status
- Nomination timer (MM:SS format) for tracking auction duration
- Admin controls for draft management:
  - Reset draft to initial state
  - Undo individual draft picks
  - Cancel active nominations
  - Admin draft: Direct player assignment bypassing auction process (for keepers)
- Player search with autocomplete dropdown
- Team bidding interfaces with budget validation
- Live roster updates with player images from ESPN

#### Team Viewer Interface (Port 8176)
**Technology Stack:** HTML/CSS/JavaScript with vanilla JS  
**Served By:** Separate FastAPI application instance  
**Access:** Browser-based interface at [network-ip]:8176  
**Security:** Read-only, no modification capabilities  

**Key Features:**
- Team selection dropdown (defaults to owner ID 1)
- Complete roster display with player images, positions, teams, and prices
- **Player statistics integration**: 2024 season stats and 2025 bye weeks displayed between team logo and price
- Team summary statistics (budget remaining, position counts vs maximums)
- Dark theme with color differentiation for easy reading
- Auto-refresh every 5 seconds for real-time updates
- Responsive design optimized for 17-player rosters
- Fetches all data from main application API (port 8175)

### Backend
**Framework:** FastAPI with Pydantic models  
**Architecture:** Stateless design - all state retrieved from datastore on each request  
**Serialization:** Pydantic models for type safety and JSON serialization  
**Templates:** Jinja2 for initial HTML rendering  
**API Documentation:** Automatic OpenAPI/Swagger generation (code-first approach)

### Data Storage
**Type:** File-based JSON storage  
**Rationale:** Speed is not critical; prioritizing convenience and debuggability  
**Configuration:** Storage directory configurable via `config.json` in repo root  

**Data Files:**
- `draft_state.json` - JSON representation of the pydantic DraftState object
- `players.json` - List of all available players with their details
- `owners.json` - Owner information and ID mappings
- `action_log.json` - History of all draft actions for undo capability
- `config.json` - Application configuration (budgets, min bids, etc.)
- `player_stats.json` - Player statistics and bye weeks (optional, generated separately)

## API Architecture

All API endpoints are served from the same FastAPI application at `/api/v1/*`. For complete endpoint documentation, see the [live API documentation](https://abottchen.github.io/ffdrafttracker/).

### Optimistic Locking for Concurrency Control

To prevent double-submissions and race conditions, all state-modifying endpoints use optimistic locking:

- **Version Field:** DraftState includes a `version: int` field that increments on each modification
- **Request Pattern:** POST requests include `expected_version: int` in body; DELETE requests use `If-Match` header with ETag
- **Conflict Detection:** If `draft_state.version != expected_version`, returns HTTP 409 Conflict
- **Client Recovery:** On 409, client should refresh state and retry with new version
- **Benefits:** Prevents both accidental double-clicks and legitimate concurrent modifications

### Error Response Standards

The API uses semantic HTTP status codes to distinguish different error scenarios:

- **400 Bad Request:** Invalid input data (missing required fields, malformed JSON, invalid IDs)
- **409 Conflict:** Version mismatch due to concurrent modification
- **422 Unprocessable Entity:** Business rule violations (insufficient budget, position limits, etc.)

This allows frontend to handle errors appropriately:
- 400 → Log error (shouldn't happen with proper frontend validation)
- 409 → Automatically refresh state and retry
- 422 → Display specific error message to user

**Example 409 Response (Version Mismatch):**
```json
{
  "detail": "Draft state has changed (version 43 != 42). Please refresh and try again.",
  "current_version": 43
}
```

**Example 422 Response (Business Rule Violation):**
```json
{
  "detail": "Insufficient budget. Owner needs $50 but only has $45 remaining."
}
```

### Core API Design Patterns

**State Management Flow:**
1. **Nominate** → **Bid** (optional, multiple) → **Draft** → Repeat
2. Each operation validates the current state before modification
3. All state changes are atomic and logged for audit trails

**Admin Operations:**
- Reset entire draft state
- Undo individual picks
- Cancel nominations  
- Direct player assignment (bypassing auction for keepers)

**Data Export:**
- CSV export for external analysis and record keeping
- Structured format compatible with spreadsheet applications

**Player Statistics Integration:**
- Optional enhanced player data with 2024 season statistics and 2025 bye weeks
- Graceful degradation: application functions fully without stats data
- Stats fetched from `/api/v1/player/stats` endpoint with defensive error handling

## File Structure
```
ffdrafttracker/
├── main.py                # Main FastAPI application (ports 8175 & 8176)
├── src/
│   ├── __init__.py
│   ├── enums/
│   │   ├── __init__.py
│   │   ├── team.py        # NFLTeam enum
│   │   └── position.py    # Position enum
│   └── models/
│       ├── __init__.py
│       ├── player.py      # Player model
│       ├── owner.py       # Owner model
│       ├── nominated.py   # Nominated model
│       ├── draft_pick.py  # DraftPick model
│       ├── team.py        # Team model
│       ├── draft_state.py # DraftState model
│       ├── action_log.py  # ActionLog model
│       ├── action_logger.py # ActionLogger utility
│       ├── configuration.py # Configuration model
│       └── player_stats.py # Player statistics models
├── static/                # Static assets (if needed)
├── templates/
│   ├── index.html         # Main draft application template
│   └── team_viewer.html   # Team viewer application template
├── data/
│   ├── draft_state.json   # Current draft state
│   ├── players.json       # Player database
│   ├── owners.json        # Owner information
│   ├── action_log.json    # Complete action history
│   ├── config.json        # Application configuration
│   └── player_stats.json  # Player statistics and bye weeks (optional)
├── tests/                 # Test suite
│   ├── unit/              # Unit tests for models
│   └── integration/       # Integration tests for file persistence
├── utils/
│   ├── fetch_espn_players.py # Utility for player data import
│   └── fetch_player_stats.py # Utility for player statistics import
├── requirements.txt       # Python dependencies
├── pyproject.toml        # Project configuration
├── DESIGN.md             # This architecture document
├── CLAUDE.md             # Development guidance
└── README.md             # Project overview
```

## Architecture Decision: FastAPI

### Why FastAPI Over Alternatives

**Vs. Flask:**
- Built-in request/response validation via Pydantic
- Automatic OpenAPI generation eliminates documentation drift
- Native async support for future scalability
- Type hints provide better IDE support and catch errors at development time

**Vs. Django:**
- Lighter weight for API-focused application
- No ORM complexity - simple file-based storage meets current needs
- Faster development iteration with automatic docs
- Modern Python patterns (type hints, async/await)

**Vs. Express/Node.js:**
- Leverages existing Python ecosystem for data processing
- Pydantic provides superior data validation vs manual validation
- Type safety catches errors that would be runtime failures in JavaScript

### Automatic OpenAPI Generation
- **Code-First Approach:** Pydantic models serve as single source of truth
- **No Build Step:** OpenAPI spec generated at runtime from Python code
- **Always in Sync:** Documentation cannot drift from implementation
- **Documentation Hosting:** Static docs generated via utility script for GitHub Pages

### Type Safety Benefits
```
Pydantic Models (Python) → FastAPI Endpoints → OpenAPI Schema
                         ↓                    ↓
                   Runtime Validation    Client Generation
                         ↓
                   Type-safe API responses
```

**Development Benefits:**
- IDE autocomplete for request/response models
- Validation errors caught at API boundary, not in business logic
- Refactoring safety - type system catches breaking changes
- Automatic serialization of complex Python objects to JSON

## Data Models

### Enums (src/enums/)

**NFLTeam** (`team.py`): Enum containing all 32 NFL team abbreviations (ARI, ATL, BAL, etc.)

**Position** (`position.py`): Enum for fantasy positions:
- QB (Quarterback)
- RB (Running Back) 
- WR (Wide Receiver)
- TE (Tight End)
- K (Kicker)
- D/ST (Defense/Special Teams)

### Models (src/models/)

**Player** (`player.py`): Core player representation (immutable)
- `id: int` - Unique identifier for image retrieval
- `first_name: str` - Player's first name
- `last_name: str` - Player's last name  
- `team: NFLTeam` - NFL team (validated enum)
- `position: Position` - Player position (validated enum)
- Properties:
  - `full_name` - Returns "First Last"
  - `display_name` - Returns "Last, F."

**Owner** (`owner.py`): Fantasy team owner
- `id: int` - Unique identifier for the owner
- `owner_name: str` - Name of the person who owns the team
- `team_name: str` - Name of their fantasy team

**Nominated** (`nominated.py`): Currently nominated player for auction
- `player_id: int` - ID of the nominated player
- `current_bid: int` - Current highest bid amount
- `current_bidder_id: int` - ID of owner with current high bid
- `nominating_owner_id: int` - ID of owner who nominated

**DraftPick** (`draft_pick.py`): Record of a completed draft selection
- `pick_id: int` - Unique identifier for this pick (for undo operations)
- `player_id: int` - ID of the drafted player
- `owner_id: int` - ID of owner who drafted the player
- `price: int` - Final auction price

**Team** (`team.py`): Fantasy team roster
- `owner_id: int` - ID of the team owner
- `budget_remaining: int` - Money left to spend
- `picks: List[DraftPick]` - List of all drafted players with prices

**DraftState** (`draft_state.py`): Complete draft state
- `nominated: Optional[Nominated]` - Currently nominated player (if any)
- `available_player_ids: List[int]` - IDs of all undrafted players
- `teams: List[Team]` - All teams with their rosters
- `owner_id_next_to_nominate: int` - Owner ID of next person to nominate (in numerical order)

**ActionLog** (`action_log.py`): Audit trail for undo capability
- `timestamp: datetime` - When the action occurred
- `action_type: str` - Type of action (nominate, bid, draft, undo)
- `owner_id: int` - Who performed the action
- `data: dict` - Action-specific data

**Configuration** (`configuration.py`): Application settings
- `initial_budget: int` - Starting budget per team (e.g., 200)
- `min_bid: int` - Minimum bid amount (e.g., 1)
- `position_maximums: Dict[str, int]` - Max players per position (e.g., {"QB": 2, "RB": 4})
- `total_rounds: int` - Total draft rounds (e.g., 19)
- `data_directory: str` - Where to store data files

**PlayerStats** (`player_stats.py`): Enhanced player data (optional)
- `bye_week: Optional[int]` - 2025 NFL bye week (1-18)
- `position: str` - Player position for validation
- `team: str` - NFL team abbreviation
- `passing: Optional[PassingStats]` - QB passing statistics
- `rushing: Optional[RushingStats]` - Rushing statistics (QBs, RBs, WRs)
- `receiving: Optional[ReceivingStats]` - Receiving statistics (WRs, TEs, RBs)
- `kicking: Optional[KickingStats]` - Kicking statistics (Ks)
- `stats_summary: Optional[str]` - Formatted display string

**PlayerStatsCollection** (`player_stats.py`): Dictionary of player statistics
- Root model containing `Dict[str, PlayerStats]` keyed by player ID
- Provides O(1) lookup methods for efficient UI rendering
- Graceful handling of missing or incomplete data

**Design Notes**: 
- Player objects remain immutable - prices are tracked in DraftPick
- Using IDs instead of embedded objects prevents data duplication
- The `id` fields enable flexible image handling for both players and owners
- ActionLog enables full undo/redo capability
- Configuration loaded once at startup from config.json

## Validation Rules

**Position Limits:**
- Bids rejected (HTTP 409) if owner already at position maximum
- Frontend should disable bid buttons for players when limits reached
- Position maximums configurable in config.json

**Draft Completion:**
- Frontend tracks 19 roster spots per team (configurable)
- Buttons grey out when all positions filled
- Backend remains stateless - frontend handles completion logic

**Nomination Order:**
- Proceeds in numerical order by owner_id
- Cycles back to lowest owner_id after highest
- owner_id_next_to_nominate field tracks current turn

## Expected State Flow

**Normal Auction Sequence:**
1. `POST /api/v1/nominate` - Creates nomination (only if none exists)
2. `POST /api/v1/bid` - Zero or more bids (only if nomination exists)
3. `POST /api/v1/draft` - Completes auction (only if nomination exists, clears it)
4. Repeat from step 1

**State Validation:**
- Nominate: Requires `nominated == None`
- Bid: Requires `nominated != None`  
- Draft: Requires `nominated != None`, clears to `None` on success

**Atomic File Operations:**
- All state changes write to `.tmp` file first
- Validate by attempting to parse the temporary file
- Only replace original file if validation succeeds
- Prevents corruption during manual edits or system failures
- 1-2 second transaction time acceptable for data integrity

**Action Logging:**
- Every POST to nominate/bid/draft writes to action_log.json
- Logs include: timestamp, action_type, owner_id, and action-specific data
- **Nominate**: player_id, initial_bid
- **Bid**: player_id, bid_amount, previous_bid
- **Draft**: player_id, final_price, pick_id
- Enables complete audit trail and potential undo functionality
- Uses same atomic file operations as draft state
