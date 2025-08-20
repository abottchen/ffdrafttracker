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
   pip install -e .
   # OR manually:
   pip install fastapi uvicorn pydantic
   ```

3. **Set up your draft data**
   ```bash
   # Copy sample data files to data/ directory
   # Customize owners.json, players.json, and config.json
   ```

4. **Generate player statistics (optional)**
   ```bash
   # Fetch 2024 season stats and 2025 bye weeks from ESPN
   python utils/fetch_player_stats.py
   
   # For testing with limited players:
   python utils/fetch_player_stats.py --limit 50
   ```

5. **Start the application**
   ```bash
   python main.py
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
  "data_directory": "data"
}
```

### Team Owners (`data/owners.json`)
```json
[
  {
    "id": 1,
    "owner_name": "John Smith",
    "team_name": "Smith's Squad"
  }
]
```

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
python -m pytest tests/ -v

# Unit tests only
python -m pytest tests/unit/ -v

# Integration tests only
python -m pytest tests/integration/ -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

### Code Quality
```bash
# Linting and formatting
ruff check src/ tests/
ruff format src/ tests/
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
4. Start the application: `python main.py`
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
4. Run the test suite: `python -m pytest tests/ -v`
5. Submit a pull request
