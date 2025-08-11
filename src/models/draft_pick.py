from pydantic import BaseModel


class DraftPick(BaseModel):
    pick_id: int
    player_id: int
    owner_id: int
    price: int
