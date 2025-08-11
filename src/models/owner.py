from pydantic import BaseModel


class Owner(BaseModel):
    id: int
    owner_name: str
    team_name: str
