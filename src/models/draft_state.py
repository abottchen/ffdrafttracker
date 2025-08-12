from pathlib import Path

from pydantic import BaseModel, Field

from .nominated import Nominated
from .team import Team


class DraftState(BaseModel):
    nominated: Nominated | None = None
    available_player_ids: list[int] = Field(default_factory=list)
    teams: list[Team] = Field(default_factory=list)
    next_to_nominate: int
    version: int = 1  # For optimistic locking to prevent double-submissions

    @classmethod
    def load_from_file(cls, filepath: Path) -> "DraftState":
        """Load DraftState from JSON file"""
        return cls.model_validate_json(filepath.read_text())

    def save_to_file(self, filepath: Path, increment_version: bool = True) -> None:
        """Save DraftState to JSON file using atomic operations.

        Args:
            filepath: Path to save the file to
            increment_version: Whether to increment the version (default True).
                              Set to False for initial saves or resets.
        """
        # Increment version for normal saves to support optimistic locking
        if increment_version:
            self.version += 1

        # Write to temporary file first
        temp_filepath = filepath.with_suffix(".tmp")
        temp_filepath.write_text(self.model_dump_json(indent=2))

        # Validate the temporary file by trying to load it
        try:
            self.load_from_file(temp_filepath)
        except Exception as e:
            temp_filepath.unlink(missing_ok=True)  # Clean up temp file
            raise ValueError(f"Failed to validate temporary file: {e}")

        # If validation passes, atomically replace the original
        temp_filepath.replace(filepath)
