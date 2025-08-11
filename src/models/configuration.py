from pathlib import Path

from pydantic import BaseModel


class Configuration(BaseModel):
    initial_budget: int
    min_bid: int
    position_maximums: dict[str, int]  # e.g., {"QB": 2, "RB": 4, "WR": 5}
    total_rounds: int
    data_directory: str = "data"

    @classmethod
    def load_from_file(cls, filepath: Path) -> "Configuration":
        """Load Configuration from JSON file"""
        return cls.model_validate_json(filepath.read_text())
