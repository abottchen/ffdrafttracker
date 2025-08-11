from pydantic import BaseModel

from src.enums import NFLTeam, Position


class Player(BaseModel):
    id: int
    first_name: str
    last_name: str
    team: NFLTeam
    position: Position

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def display_name(self) -> str:
        return f"{self.last_name}, {self.first_name[0]}."
