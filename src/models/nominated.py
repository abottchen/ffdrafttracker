from pydantic import BaseModel


class Nominated(BaseModel):
    player_id: int
    current_bid: int
    current_bidder_id: int
    nominating_owner_id: int
