from datetime import datetime

from pydantic import BaseModel, Field


class ActionLog(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    action_type: str  # "nominate", "bid", "draft", "undo"
    owner_id: int
    data: dict  # Flexible data based on action type
