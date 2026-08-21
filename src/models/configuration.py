from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, Field

from src.enums.team import NFLTeam


class Configuration(BaseModel):
    initial_budget: int
    min_bid: int
    position_maximums: dict[str, int]  # e.g., {"QB": 2, "RB": 4, "WR": 5}
    total_rounds: int
    data_directory: str = "data"
    # UI year; the viewer's prior-season stats column shows this minus 1
    draft_year: int = 2025
    # Per-team bye weeks for the draft_year season; update alongside draft_year
    bye_weeks: dict[NFLTeam, Annotated[int, Field(ge=1, le=18)]] = Field(
        default_factory=dict
    )

    def missing_bye_week_teams(self) -> list[NFLTeam]:
        """NFL teams without a configured bye week (empty when complete)."""
        return sorted(set(NFLTeam) - set(self.bye_weeks))

    @classmethod
    def load_from_file(cls, filepath: Path) -> "Configuration":
        """Load Configuration from JSON file"""
        return cls.model_validate_json(filepath.read_text())
