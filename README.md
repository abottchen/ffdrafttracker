# Fantasy Football Draft Tracker

[![CI](https://github.com/abottchen/ffdrafttracker/workflows/CI/badge.svg)](https://github.com/abottchen/ffdrafttracker/actions)
[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?logo=fastapi)](https://fastapi.tiangolo.com)
[![API Documentation](https://img.shields.io/badge/API-Documentation-blue)](https://abottchen.github.io/ffdrafttracker/)

A live auction draft tracking tool for fantasy football leagues. Features a web-based interface for managing auctions with real-time updates, optimistic locking for concurrent access, and separate admin/viewer interfaces.

## Features

### **Dual Interface Design**
- **Admin Interface** (port 8175) - Full draft management controls with read/write API access
- **Team Viewer** (port 8176) - Read-only team viewing for remote participants with secure API separation

### **Live Draft Management**
- Real-time nomination and bidding system
- Draft progress tracking with visual progress bar
- Player search with autocomplete
- Budget validation and position limit enforcement

### **Team Management**
- Individual team rosters with player images
- Enhanced player information with 2024 stats and 2025 bye weeks (when available)
- Budget tracking and remaining picks
- Position breakdown vs league maximums
- Complete draft history with undo capability

### **Analyst Booth Commentary**
- Live play-by-play from the analyst booth, served from `GET /api/v1/comments`
- Admin: a one-line "Booth" chyron above the Draft Wire; click to expand the last few calls
- Viewer: a full scrollable transcript in the Draft Analysis tab (headshot panel, infinite scroll for history)

### **League History** (Viewer)
- A "League History" tab presenting the multi-season archive, served from `GET /api/v1/league-history`
- Champion banners, a 23-season finish grid (color = regular-season finish, gold = title), régime-vs-crown, player loyalty, title droughts, and most-rostered players
- Click any grid cell to open that team's full end-of-season roster and step through a manager's seasons
- Auction price history, served from `GET /api/v1/auction-prices` (or `/{year}` for one season): every player's auction salary by season (2016–present) with owner, keeper flag, and ESPN player id

### **Data Integrity**
- Optimistic locking prevents concurrent modification conflicts
- Atomic file operations for crash safety
- Complete audit trail of all draft actions

## Quick Start

### Prerequisites
- Python 3.8+
- Web browser

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd ffdrafttracker
   ```

2. **Install dependencies**
   ```bash
   # Recommended (uses the committed uv.lock):
   uv sync --extra dev
   # OR with pip:
   pip install -e .
   ```

3. **Set up your draft data**
   ```bash
   # Copy sample data files to data/ directory
   # Customize owners.json, players.json, and config.json
   ```

4. **Generate player statistics (optional)**
   ```bash
   # Fetch 2024 season stats and 2025 bye weeks from ESPN
   uv run python utils/fetch_player_stats.py

   # For testing with limited players:
   uv run python utils/fetch_player_stats.py --limit 50
   ```

5. **Start the application**
   ```bash
   uv run python main.py
   ```

6. **Access the interfaces**
   - **Draft Admin**: http://localhost:8175 (local admin access)
   - **Team Viewer**: http://[your-ip]:8176 (remote participant access)

## Configuration

### League Settings (`data/config.json`)
```json
{
  "initial_budget": 200,
  "min_bid": 1,
  "position_maximums": {
    "QB": 3,
    "RB": 8,
    "WR": 8,
    "TE": 3,
    "K": 3,
    "D/ST": 3
  },
  "total_rounds": 17,
  "data_directory": "data",
  "draft_year": 2025
}
```

### Team Owners (`data/owners.json`)
```json
[
  {
    "id": 1,
    "owner_name": "John Smith",
    "team_name": "Smith's Squad",
    "color": "#21D4FD"
  }
]
```

`color` is a per-team identity hex color (`#RRGGBB`), hand-edited reference data used by both the admin and viewer UIs. It defaults to `#888888` if omitted.

### Player Database (`data/players.json`)
Players and defenses with ESPN IDs for automatic image loading:
```json
[
  {
    "id": 1,
    "first_name": "Arizona",
    "last_name": "Cardinals",
    "team": "ARI",
    "position": "D/ST"
  },
  {
    "id": 4242335,
    "first_name": "Patrick",
    "last_name": "Mahomes",
    "team": "KC",
    "position": "QB"
  }
]
```

## Development

### Running Tests
```bash
# All tests
uv run python -m pytest tests/ -v

# Unit tests only
uv run python -m pytest tests/unit/ -v

# Integration tests only
uv run python -m pytest tests/integration/ -v

# With coverage
uv run python -m pytest tests/ --cov=src --cov-report=term-missing
```

### Code Quality
```bash
# Linting and formatting
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

### API Documentation
- **Admin API (Full Access)**: http://localhost:8175/docs
- **Viewer API (Read-Only)**: http://localhost:8176/docs
- **OpenAPI Schemas**: Available at `/openapi.json` on each port

## Architecture

Built with FastAPI and Pydantic for type safety and automatic API documentation. Uses file-based JSON storage for simplicity and debuggability.

### Key Components
- **Models** (`src/models/`) - Pydantic data models with validation
- **Enums** (`src/enums/`) - NFL teams and positions
- **Templates** (`templates/`) - Jinja2 HTML templates
- **Data** (`data/`) - JSON files for all draft state

### Design Principles
- **Stateless API** - All state loaded from files on each request
- **Shared Business Logic** - DRY principles with common data functions
- **Security Separation** - Write operations isolated to admin interface
- **Atomic Operations** - Crash-safe file writes with validation
- **Type Safety** - Pydantic models prevent runtime errors
- **Zero Build** - No compilation or bundling required

For detailed architecture information, see [DESIGN.md](DESIGN.md).

## Usage

### Starting a Draft
1. Customize `data/owners.json` with your league members
2. Import player data to `data/players.json` (or use sample data)
3. Adjust league settings in `data/config.json`
4. Start the application: `uv run python main.py`
5. Share the team viewer URL with participants: `http://[your-ip]:8176`

### During the Draft
- **Nominate players** using the search interface
- **Place bids** through team panels or bid inputs
- **Complete auctions** with the "Draft Player" button
- **Monitor progress** via the progress bar and timer
- **Undo mistakes** using admin controls if needed

### Admin Controls
- **Reset Draft** - Start over completely
- **Cancel Nomination** - Remove current nomination
- **Remove Picks** - Undo individual draft selections
- **Refresh Data** - Reload from files

## Data Files

All draft data is stored in human-readable JSON files in the `data/` directory:

- `draft_state.json` - Current draft state (auto-managed)
- `players.json` - Available players database
- `owners.json` - League member information
- `config.json` - League rules and settings
- `action_log.json` - Complete audit trail (auto-managed)
- `player_stats.json` - Player statistics and bye weeks (optional, generated by script)
- `analyst-comments.jsonl` - Append-only analyst booth commentary log (JSON Lines; served by `GET /api/v1/comments`)
- `league_history.json` - Season-by-season league history archive 2003–2025 (champions, standings, rosters, draft prices; updated by script — see below)
- `auction_prices.json` - Auction salaries by season 2016–2024 (grouped by owner; `{player, price, keeper, espn_id}` per pick; served by `GET /api/v1/auction-prices`)

## League History Archive

`data/league_history.json` is a season-by-season archive of the league's history
(2003–2025): champion, runner-up, best regular-season record, full final
standings, and every team's end-of-season roster with draft prices. League
members are stored by **first name only** (no last names, emails, or account
handles). This file is the source of truth — it is committed and edited in place.

### Shape

```jsonc
{
  "seasons": [                          // newest first
    {
      "year": 2025,
      "champion":    { "owner": "Raman", "team_name": "THE NIGHTMARE" },
      "runner_up":   { "owner": "Adam",  "team_name": "Call Me The Breece" },
      "best_record": { "owner": "Raman", "team_name": "THE NIGHTMARE", "record": "12-2" },
      "shared_title": false,            // true only for the 2022 co-championship
      "note": null,                     // e.g. "SPLIT TITLE"
      "source": "espn",                 // "espn" (2012+) | "yahoo" (2003-2011)
      "draft_type": "auction",          // "auction" | "snake"
      "standings": [                    // every team that season
        {
          "team_name": "THE NIGHTMARE",
          "owner": "Raman",
          "wins": 12, "losses": 2, "ties": 0,
          "points_for": 1912.46,
          "final_rank": 1,              // 1 = champion, 2 = runner-up, ...
          "roster": [                   // end-of-season roster
            {
              "player_name": "Christian McCaffrey",
              "position": "RB",         // QB|RB|WR|TE|K|D/ST
              "nfl_team": "SF",
              "slot": "RB",             // lineup slot, or "Bench" / "IR"
              "acquisition": "DRAFTED", // DRAFTED | ADDED | TRADED
              "draft_price": 54,        // auction salary (null if not drafted)
              "draft_pick": null        // overall pick # for snake drafts
            }
          ]
        }
      ]
    }
  ]
}
```

The "Most Championships" leaderboard is derived from this data (each season's
champion, plus the runner-up when `shared_title` is true), not stored.

### Updating after a season

At the end of each season, pull the just-completed year from ESPN and splice it
into the archive:

```bash
PYTHONPATH=. uv run python utils/add_espn_season.py 2026
```

This fetches the season from ESPN's read API and adds it directly to
`data/league_history.json` (replacing it if the year is already present). It
prints the champion as a sanity check. Owners come from each ESPN member's first
name.

- **Private leagues** need your ESPN auth cookies. From a logged-in browser
  (DevTools → Application → Cookies → `fantasy.espn.com`), export them first:
  ```bash
  export ESPN_S2='AEB...'
  export ESPN_SWID='{XXXXXXXX-XXXX-...}'
  ```
- **Nickname not matching?** If the league calls someone by a name other than
  their ESPN first name, add an override to `ESPN_NAME_OVERRIDES` in
  `src/espn_history.py` and re-run.
- **Owner won't resolve?** If a team's ESPN member is missing from the season's
  member list or has no first name on their profile, the script **fails and
  writes nothing**, naming the offending team. Fix it on ESPN and re-run.
- `--league-id <id>` targets a different ESPN league (default is the league's own id).

Pre-2012 seasons came from Yahoo Fantasy (one-time import) and are not refreshed
by this script.

## Network Setup

Both applications run on all network interfaces (0.0.0.0) but serve different purposes:
- **Port 8175**: Admin interface with full read/write capabilities
- **Port 8176**: Team viewer with read-only access for remote participants

### Firewall Configuration
Ensure ports are accessible to your network participants:
```bash
# Windows Firewall example
netsh advfirewall firewall add rule name="FFDraftTracker-Viewer" dir=in action=allow protocol=TCP localport=8176
netsh advfirewall firewall add rule name="FFDraftTracker-Admin" dir=in action=allow protocol=TCP localport=8175
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run the test suite: `uv run python -m pytest tests/ -v`
5. Submit a pull request
