"""Request/response Pydantic models and shared OpenAPI constants."""

from pydantic import BaseModel, Field

from src.models import DraftState, Team


# Request models
class NominateRequest(BaseModel):
    owner_id: int
    player_id: int
    initial_bid: int
    expected_version: int


class BidRequest(BaseModel):
    owner_id: int
    bid_amount: int
    expected_version: int


class DraftRequest(BaseModel):
    owner_id: int
    player_id: int
    final_price: int
    expected_version: int


class ResetRequest(BaseModel):
    expected_version: int | None = None
    force: bool = False


class AdminDraftRequest(BaseModel):
    owner_id: int
    player_id: int
    price: int
    expected_version: int


class TransferRequest(BaseModel):
    pick_id: int
    to_owner_id: int
    expected_version: int


class TeamUpdateRequest(BaseModel):
    manually_done: bool
    expected_version: int


# Response-only models (computed, read-only enrichments over the persisted shape).
class TeamView(Team):
    max_bid: int | None = None  # None when the roster is full


class DraftStateResponse(DraftState):
    teams: list[TeamView] = Field(default_factory=list)
    up_next: int | None = None  # next distinct eligible nominator, or null


class CommentResponse(BaseModel):
    """One analyst-booth comment, tagged with its position in the log.

    ``seq`` is the 1-based position of the (committed) line in the append-only
    log; it is the cursor clients page against (``since`` / ``before``).
    """

    seq: int
    ts: str
    state_version: int
    persona: str
    text: str


# Per-parameter OpenAPI descriptions for the comments feed, shared so the admin
# and viewer specs stay identical.
_COMMENTS_SINCE_DESC = (
    "Return only comments with `seq` greater than this (live tail / forward polling)."
)
_COMMENTS_BEFORE_DESC = (
    "Return only comments with `seq` less than this (older history / backward paging)."
)
_COMMENTS_LIMIT_DESC = (
    "Cap the result to the most recent N comments of the matched window."
)
