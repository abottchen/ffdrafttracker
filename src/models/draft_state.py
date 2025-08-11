from pathlib import Path

from pydantic import BaseModel, Field

from .nominated import Nominated
from .team import Team


class DraftState(BaseModel):
    nominated: Nominated | None = None
    available_player_ids: list[int] = Field(default_factory=list)
    teams: list[Team] = Field(default_factory=list)
    next_to_nominate: int

    @classmethod
    def load_from_file(cls, filepath: Path) -> "DraftState":
        """Load DraftState from JSON file"""
        return cls.parse_file(filepath)

    def save_to_file(self, filepath: Path) -> None:
        """Save DraftState to JSON file using atomic operations"""
        # Write to temporary file first
        temp_filepath = filepath.with_suffix(".tmp")
        temp_filepath.write_text(self.json(indent=2))

        # Validate the temporary file by trying to load it
        try:
            self.load_from_file(temp_filepath)
        except Exception as e:
            temp_filepath.unlink(missing_ok=True)  # Clean up temp file
            raise ValueError(f"Failed to validate temporary file: {e}")

        # If validation passes, atomically replace the original
        temp_filepath.replace(filepath)
