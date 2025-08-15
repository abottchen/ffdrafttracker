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

## API Endpoints

All API endpoints are served from the same FastAPI application at `/api/v1/*`

### Optimistic Locking for Concurrency Control

To prevent double-submissions and race conditions, all state-modifying endpoints use optimistic locking:

- **Version Field:** DraftState includes a `version: int` field that increments on each modification
- **Request Pattern:** All POST/DELETE requests that modify state must include `expected_version: int`
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

### POST /api/v1/nominate
**Purpose:** Nominates a player for auction  
**Request Body:**
- `owner_id: int` - ID of owner making the nomination
- `player_id: int` - ID of player being nominated
- `initial_bid: int` - Opening bid amount (minimum $1)
- `expected_version: int` - Expected draft state version for optimistic locking
**Response Codes:**
- `200` - Success with nomination confirmation and player details
- `400` - Bad request (invalid player/owner ID, missing fields)
- `409` - Conflict (version mismatch - state modified by another operation)
- `422` - Unprocessable (nomination already active, bid below minimum)
**Behavior:** 
  - Validates no current nomination exists (nominated field is None)
  - Validates initial_bid >= min_bid from config
  - Updates nominated field with new Nominated object
  - Uses atomic file operations
  - Logs action with: timestamp, owner_id, player_id, initial_bid

### POST /api/v1/draft
**Purpose:** Records a successful draft pick after auction closes  
**Request Body:**
- `owner_id: int` - ID of owner who won the auction
- `player_id: int` - ID of player being drafted
- `final_price: int` - Final auction price
- `expected_version: int` - Expected draft state version for optimistic locking
**Response Codes:**
- `200` - Success with draft confirmation and updated team roster
- `400` - Bad request (invalid IDs, missing fields)
- `409` - Conflict (version mismatch - state modified by another operation)
- `422` - Unprocessable (no active nomination, price mismatch, insufficient budget)
**Behavior:** 
  - Validates nomination exists and matches player_id
  - Validates owner has sufficient budget for final_price
  - Creates DraftPick and adds to owner's Team
  - Removes player_id from available_player_ids
  - Clears nominated field
  - Uses atomic file operations
  - Logs action with: timestamp, owner_id, player_id, final_price, pick_id

### GET / 
**Purpose:** Serves the main application interface  
**Response:** HTML page with embedded Alpine.js application  
**Behavior:** Renders Jinja2 template with initial draft state

### GET /api/v1/draft-state
**Purpose:** Get complete current draft state  
**Response:** JSON of full DraftState object  
**Behavior:** Returns current draft state from file

### GET /api/v1/players
**Purpose:** Get all player information  
**Response:** JSON array of all Player objects  
**Behavior:** Returns complete player database

### GET /api/v1/players/available
**Purpose:** Get available players with details  
**Response:** JSON array of Player objects not yet drafted  
**Behavior:** Returns Player objects for all IDs in available_player_ids

### GET /api/v1/owners
**Purpose:** Get all owner information  
**Response:** JSON array of all Owner objects  
**Behavior:** Returns complete owner database

### GET /api/v1/owners/{owner_id}
**Purpose:** Get specific owner information  
**Response:** JSON with owner details or 404 if not found  
**Behavior:** Returns individual owner by ID

### GET /api/v1/config
**Purpose:** Get draft configuration settings  
**Response:** JSON of Configuration object  
**Behavior:** Returns draft configuration including budgets, position limits, and total rounds  
**Usage:** Used by frontend for client-side budget validation

### GET /api/v1/export/csv
**Purpose:** Export current draft state as CSV file for external analysis  
**Response:** CSV file download with proper headers for browser download  
**Content-Type:** `text/csv; charset=utf-8`  
**Content-Disposition:** `attachment; filename=draft_export.csv`  
**Behavior:** 
  - Generates structured CSV with owner columns and player/price data
  - First row: Owner names alternating with empty cells ("Adam","","Jodi","",...)
  - Second row: Alternating "Player" and "$" headers for each owner
  - Data rows: Player names in "Last, First" format with corresponding prices
  - Players grouped under their respective owners based on draft picks
  - Handles variable pick counts (empty cells for owners with fewer picks)
  - Uses atomic data loading for consistency with current draft state

### GET /api/v1/teams/{owner_id}
**Purpose:** Get specific team roster with player details  
**Response:** JSON with team info and full player/price data  
**Behavior:** Returns Team with expanded Player objects for each pick

### POST /api/v1/bid
**Purpose:** Update bid on currently nominated player  
**Request Body:**
- `owner_id: int` - ID of owner placing bid
- `bid_amount: int` - New bid amount (must exceed current)
- `expected_version: int` - Expected draft state version for optimistic locking
**Response Codes:**
- `200` - Success with updated nomination info
- `400` - Bad request (invalid owner ID, missing fields)
- `409` - Conflict (version mismatch - state modified by another operation)
- `422` - Unprocessable (no active nomination, insufficient bid amount, insufficient budget, position limit reached)
**Behavior:** 
  - Validates nomination exists
  - Validates bid amount exceeds current bid and >= min_bid
  - Validates owner has sufficient budget remaining for bid_amount
  - Validates owner hasn't reached position maximum for player's position
  - Updates current_bid and current_bidder_id if valid
  - Uses atomic file operations
  - Logs action with: timestamp, owner_id, player_id, bid_amount, previous_bid

### DELETE /api/v1/nominate
**Purpose:** Cancel current nomination (admin action)  
**Request Body:**
- `expected_version: int` - Expected draft state version for optimistic locking
**Response Codes:**
- `200` - Success confirmation
- `409` - Conflict (version mismatch)
- `422` - Unprocessable (no active nomination to cancel)
**Behavior:** Clears nominated field in draft state, increments version

### DELETE /api/v1/draft/{pick_id}
**Purpose:** Undo a draft pick (admin action)  
**Request Body:**
- `expected_version: int` - Expected draft state version for optimistic locking
**Response Codes:**
- `200` - Success confirmation
- `404` - Not found (pick_id doesn't exist)
- `409` - Conflict (version mismatch)
- `422` - Unprocessable (data integrity error - player is both drafted and available)
**Response:** Success confirmation  
**Behavior:** 
  - Removes DraftPick from team
  - Adds player_id back to available_player_ids

### POST /api/v1/reset
**Purpose:** Reset draft to initial state (admin action)  
**Request Body:**
- `expected_version: int` - Expected draft state version (optional, ignored if force=true)
- `force: bool` - Skip version check if true (default false)
**Response Codes:**
- `200` - Success confirmation
- `409` - Conflict (version mismatch, unless force=true)
**Behavior:** Resets draft_state.json to initial configuration, sets version to 1

### POST /api/v1/admin/draft
**Purpose:** Admin-only endpoint to draft a player directly without nomination/bidding process  
**Request Body:**
- `owner_id: int` - ID of owner drafting the player
- `player_id: int` - ID of player being drafted
- `price: int` - Draft price (must be positive)
- `expected_version: int` - Expected draft state version for optimistic locking
**Response Codes:**
- `200` - Success with draft confirmation and updated team roster
- `400` - Bad request (invalid owner/player ID, invalid price)
- `409` - Conflict (version mismatch - state modified by another operation)
- `422` - Unprocessable (player not available, team not found in draft state)
**Behavior:**
- Skips all normal validation (budget limits, position limits, nomination requirements)
- Only validates basic data integrity (player exists and available, owner exists, positive price)
- Creates DraftPick and adds to owner's Team
- Removes player_id from available_player_ids
- Updates team budget (can go negative)
- Uses atomic file operations
- Logs action with "ADMIN DRAFT:" prefix for audit trail
- Designed for quickly importing keeper players or handling admin scenarios

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
│       └── configuration.py # Configuration model
├── static/                # Static assets (if needed)
├── templates/
│   ├── index.html         # Main draft application template
│   └── team_viewer.html   # Team viewer application template
├── data/
│   ├── draft_state.json   # Current draft state
│   ├── players.json       # Player database
│   ├── owners.json        # Owner information
│   ├── action_log.json    # Complete action history
│   └── config.json        # Application configuration
├── tests/                 # Test suite
│   ├── unit/              # Unit tests for models
│   └── integration/       # Integration tests for file persistence
├── utils/
│   └── fetch_espn_players.py # Utility for player data import
├── requirements.txt       # Python dependencies
├── pyproject.toml        # Project configuration
├── DESIGN.md             # This architecture document
├── CLAUDE.md             # Development guidance
└── README.md             # Project overview
```

## FastAPI Benefits

### Automatic OpenAPI Generation
- **Code-First Approach:** Pydantic models serve as single source of truth
- **No Build Step:** OpenAPI spec generated at runtime from Python code
- **Always in Sync:** Documentation cannot drift from implementation
- **Interactive Docs:** 
  - Swagger UI available at `/docs` for testing
  - ReDoc available at `/redoc` for documentation
  - OpenAPI JSON at `/openapi.json` for client generation

### Development Workflow
1. Define Pydantic models in `models.py`
2. Use models directly in FastAPI endpoints
3. OpenAPI documentation automatically available
4. No YAML files to maintain
5. No code generation step required

### Type Safety Flow
```
Pydantic Models (Python) → Runtime API → Auto-generated OpenAPI
                         ↓
                   JSON Validation
                         ↓
                   Type-safe API responses
```

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
