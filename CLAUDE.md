# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

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

### Code Quality
```bash
# Lint and format
ruff check src/ tests/     # Linting
ruff format src/ tests/    # Formatting (replaces black)

# Type checking (if mypy is added)
mypy src/
```

### Development Setup
```bash
# Install dependencies
pip install -e .[dev]

# Or manually install dev dependencies
pip install ruff black pytest pytest-cov
```

## Architecture Overview

This is a **Fantasy Football Auction Draft Tracker** - a FastAPI web application for managing live fantasy football auctions. The codebase is currently **models-only** with the web interface planned for future implementation.

### Current Structure (Models Layer)

**Core Domain Models** (`src/models/`):
- **Player**: Immutable player data with NFL team/position
- **Owner**: Fantasy team owners with team names  
- **DraftState**: Central state containing nominated player, available players, teams
- **Nominated**: Currently auctioned player with bid info
- **Team**: Owner's roster with budget and draft picks
- **DraftPick**: Individual draft selection with price
- **Configuration**: App settings (budgets, position limits, data directory)

**Infrastructure**:
- **ActionLog**: Audit trail entries for undo capability  
- **ActionLogger**: Utility for atomic logging to JSON files

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

**Unit Tests** (`tests/unit/models/`):
- Test business logic only with full mocking
- 100% code coverage achieved
- Each model has focused validation and behavior tests
- ActionLogger tests use mocked file I/O

**Integration Tests** (`tests/integration/`):
- Test real file persistence with `tempfile` directories
- Round-trip serialization validation
- Atomic write operation verification  
- Uses reflection to ensure all DraftState fields are tested:
  ```python
  # Ensures test covers all defined model fields
  defined_fields = set(DraftState.__annotations__.keys())
  expected_fields = {'nominated', 'available_player_ids', 'teams', 'next_to_nominate'}
  assert defined_fields == expected_fields
  ```

**Test Quality Standards**:
- Removed 59 framework-testing tests (Pydantic validation, serialization)
- Focus only on custom business logic
- Rick and Morty themed test data for fun
- Reflection-based field coverage prevents serialization blind spots

## Data Model Relationships

```
DraftState
├── nominated: Optional[Nominated]           # Current auction
├── available_player_ids: List[int]          # Undrafted players  
├── teams: List[Team]                        # All fantasy teams
└── next_to_nominate: int                    # Whose turn to nominate

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

**Future FastAPI Integration**: Models designed for direct use in API endpoints with automatic validation and OpenAPI generation
- whenever the API changes, update DESIGN.md to reflect the changes.  Then run the utils/generate_docs.py script to regenerate swagger docs