from pydantic import BaseModel, Field

from .draft_pick import DraftPick


class Team(BaseModel):
    owner_id: int
    budget_remaining: int
    picks: list[DraftPick] = Field(default_factory=list)
