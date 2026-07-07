# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

Dependencies are managed with **uv** (committed `uv.lock`, pinned + hashed). Run the tools below via `uv run <cmd>`, or `source .venv/bin/activate` once and use the bare commands. Plain `python` is not on PATH on Linux — use the venv.

### Testing
```bash
# Run all tests
python -m pytest tests/

# Run specific test types
python -m pytest tests/unit/        # Unit tests only
python -m pytest tests/integration/ # Integration tests only

# Run single test file
python -m pytest tests/unit/models/test_draft_state.py -v

# Run with coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

### Running the App
```bash
uv run python main.py
# Main draft tracker: http://localhost:8175
# Team viewer app:   http://localhost:8176
```

### Code Quality
```bash
# Lint and format
ruff check src/ tests/     # Linting
ruff format src/ tests/    # Formatting (replaces black)
djlint templates/          # Lint Jinja2 templates (run after any template change)
```

### Development Setup
```bash
# Create/sync the virtualenv (.venv) exactly from the lockfile
uv sync --extra dev
```

### API Changes
Whenever an API route is added, modified, or removed:
1. Update `DESIGN.md` to reflect the change
2. Update `README.md` if user-visible behavior changed
3. Run `uv run python utils/generate_docs.py` to regenerate OpenAPI docs

### Dependency Management
- `pyproject.toml` holds abstract deps (`>=`); **`uv.lock` is the pinned + hashed source of truth** (including transitive deps).
- After editing deps in `pyproject.toml`: run `uv lock`, then regenerate the pip fallback with `uv export --extra dev --no-emit-project -o requirements.txt` (generated file — do not hand-edit).
- CI installs hash-verified via `uv sync --frozen` and runs `pip-audit` for known CVEs.

## Architecture Overview

This is a **Fantasy Football Auction Draft Tracker** - a FastAPI web application for managing live fantasy football auctions. It serves **two** FastAPI apps from `main.py`, run on separate threads by `python main.py`: an **admin** app (port 8175, full read/write) and a **read-only viewer** app (port 8176) for remote participants — write endpoints are isolated to the admin app by design. Both use Jinja2 `templates/` + `static/` assets, backed by Pydantic models with JSON-file persistence in `data/`.

### Current Structure (Models Layer)

**Core Domain Models** (`src/models/`):
- **Player**: Immutable player data with NFL team/position
- **Owner**: Fantasy team owners with team names  
- **DraftState**: Central state containing nominated player, available players, teams
- **Nominated**: Currently auctioned player with bid info
- **Team**: Owner's roster with budget and draft picks
- **DraftPick**: Individual draft selection with price
- **Configuration**: App settings (budgets, position limits, data directory)
- **PlayerStats**: Per-player stat lines (passing/rushing/receiving) shown in the viewer

**Booth Module** (`src/booth/`):
- Live draft commentary system — personas react to `draft_state.json` changes
- Posts running commentary to `data/analyst-comments.jsonl`
- `watch.py` monitors state, `slice.py` prepares context, `log.py` reads comments, `personas/` holds per-persona configs

**Domain Rules** (`src/draft_rules.py`):
- `max_bid()`, `next_eligible_nominator()`, `position_count()`, `remaining_roster_spots()`
- Business logic separate from models; used directly in FastAPI route handlers

### Key Architectural Patterns

**Pydantic-Centric Design**: All models are Pydantic v2 BaseModels providing:
- JSON serialization/deserialization
- Type validation at runtime
- Automatic OpenAPI schema generation (for future FastAPI endpoints)

**Atomic File Operations**: State persistence uses write-to-temp-then-replace pattern:
```python
def save_to_file(self, filepath: Path) -> None:
    temp_filepath = filepath.with_suffix(".tmp")
    temp_filepath.write_text(self.model_dump_json(indent=2))
    
    # Validate temp file by loading it back
    try:
        self.load_from_file(temp_filepath)
    except Exception as e:
        temp_filepath.unlink(missing_ok=True)
        raise ValueError(f"Failed to validate temporary file: {e}")
    
    # Atomic replacement
    temp_filepath.replace(filepath)
```

**Stateless Design**: No in-memory state - all data loaded from JSON files on each operation, enabling:
- Easy debugging by examining JSON files
- Manual state editing for testing
- Crash recovery without data loss

**ID-Based References**: Models reference each other by ID rather than embedding objects, preventing duplication and enabling flexible updates.

## Test Architecture

**Strict Unit/Integration Separation**:

**Unit Tests** (`tests/unit/models/`, `tests/unit/booth/`):
- Test business logic only with full mocking
- High coverage (no enforced `fail_under` gate)
- Each model has focused validation and behavior tests
- `tests/unit/booth/` covers the commentary module (`watch`/`slice`/`log`)

**Integration Tests** (`tests/integration/`):
- Test real file persistence with `tempfile` directories
- Round-trip serialization validation
- Atomic write operation verification  
- Uses reflection to ensure all DraftState fields are tested:
  ```python
  # Ensures test covers all defined model fields
  defined_fields = set(DraftState.__annotations__.keys())
  expected_fields = {'nominated', 'available_player_ids', 'teams', 'next_to_nominate', 'version'}
  assert defined_fields == expected_fields
  ```

**End-to-End Tests** (`tests/e2e/`):
- `test_complete_draft.py` drives a full draft flow against the app

**Test Quality Standards**:
- Focus only on custom business logic, not framework behavior (Pydantic handles that)
- Reflection-based field coverage prevents serialization blind spots

## Data Model Relationships

```
DraftState
├── nominated: Optional[Nominated]           # Current auction
├── available_player_ids: List[int]          # Undrafted players  
├── teams: List[Team]                        # All fantasy teams
├── next_to_nominate: int                    # Whose turn to nominate
└── version: int                             # Optimistic-locking counter (bumped on save)

Team
├── owner_id: int                            # References Owner
├── budget_remaining: int                    # Money left
└── picks: List[DraftPick]                   # Drafted players

DraftPick  
├── player_id: int                           # References Player
├── owner_id: int                            # References Owner  
├── price: int                               # Auction price
└── pick_id: int                             # For undo operations

Nominated
├── player_id: int                           # References Player
├── current_bidder_id: int                   # References Owner
├── nominating_owner_id: int                 # References Owner
└── current_bid: int                         # Highest bid
```

## Key Implementation Notes

**Pydantic v2 Usage**: Uses modern `model_validate_json()` instead of deprecated `parse_file()`

**Enum Integration**: NFLTeam and Position enums provide validation and type safety

**Configuration-Driven**: Position maximums, budgets, etc. loaded from config.json

**Fantasy Football Domain**: Models reflect auction draft mechanics (nominations, bids, position limits)

**Optimistic Locking**: All mutating API endpoints accept `expected_version` and reject stale reads with HTTP 409, preventing concurrent edit conflicts.