from pydantic import BaseModel, Field


class Owner(BaseModel):
    id: int
    owner_name: str
    team_name: str
    color: str = Field(default="#888888", pattern=r"^#[0-9A-Fa-f]{6}$")
