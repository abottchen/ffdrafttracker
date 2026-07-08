"""Read-only API router, shared between the admin and viewer apps."""

import logging

from fastapi import APIRouter, HTTPException, Query

from src.api.schemas import (
    _COMMENTS_BEFORE_DESC,
    _COMMENTS_LIMIT_DESC,
    _COMMENTS_SINCE_DESC,
    CommentResponse,
    DraftStateResponse,
    TeamView,
)
from src.booth.log import read_comments
from src.draft_rules import max_bid, next_eligible_nominator
from src.models import Configuration, Owner, Player
from src.models.player_stats import PlayerStatsCollection
from src.persistence import (
    COMMENTS_FILE,
    PLAYER_STATS_FILE,
    load_configuration,
    load_draft_state,
    load_owners,
    load_players,
)

logger = logging.getLogger(__name__)

read_router = APIRouter()


@read_router.get("/api/v1/draft-state", response_model=DraftStateResponse)
def get_draft_state():
    """Get complete current draft state."""
    state = load_draft_state()
    config = load_configuration()

    team_views = [
        TeamView(**team.model_dump(), max_bid=max_bid(team, config))
        for team in state.teams
    ]
    up_next = next_eligible_nominator(
        state, config, from_id=state.next_to_nominate, inclusive=False
    )
    if up_next == state.next_to_nominate:
        up_next = None  # fewer than two eligible -> no distinct "up next"

    return DraftStateResponse(
        **state.model_dump(exclude={"teams"}),
        teams=team_views,
        up_next=up_next,
    )


@read_router.get("/api/v1/players", response_model=list[Player])
def get_all_players():
    """Get all player information."""
    return load_players()


@read_router.get("/api/v1/players/available", response_model=list[Player])
def get_available_players():
    """Get available players with details."""
    draft_state = load_draft_state()
    all_players = load_players()

    # Create player lookup
    player_dict = {p.id: p for p in all_players}

    # Return available players
    return [
        player_dict[pid]
        for pid in draft_state.available_player_ids
        if pid in player_dict
    ]


@read_router.get("/api/v1/player/stats", response_model=PlayerStatsCollection)
def get_player_stats():
    """Get player statistics and bye weeks. Returns empty collection if not found."""
    if not PLAYER_STATS_FILE.exists():
        logger.info("Player stats file not found, returning empty collection")
        return PlayerStatsCollection({})

    try:
        with open(PLAYER_STATS_FILE) as f:
            data = f.read()
        return PlayerStatsCollection.model_validate_json(data)
    except Exception as e:
        logger.error(f"Error loading player stats: {e}, returning empty collection")
        return PlayerStatsCollection({})


@read_router.get("/api/v1/owners", response_model=list[Owner])
def get_all_owners():
    """Get all owner information."""
    owners_dict = load_owners()
    # Convert dict back to list format for API compatibility
    return [
        {"id": owner_id, **owner_data} for owner_id, owner_data in owners_dict.items()
    ]


@read_router.get("/api/v1/config", response_model=Configuration)
def get_config():
    """Get draft configuration."""
    return load_configuration()


@read_router.get("/api/v1/owners/{owner_id}", response_model=Owner)
def get_owner(owner_id: int):
    """Get specific owner information."""
    owners = load_owners()
    if owner_id not in owners:
        raise HTTPException(status_code=404, detail=f"Owner {owner_id} not found")
    return {"id": owner_id, **owners[owner_id]}


@read_router.get("/api/v1/teams/{owner_id}")
def get_team(owner_id: int):
    """Get specific team roster with player details."""
    draft_state = load_draft_state()

    # Find team for owner
    team = next((t for t in draft_state.teams if t.owner_id == owner_id), None)
    if not team:
        raise HTTPException(
            status_code=404, detail=f"Team not found for owner {owner_id}"
        )

    # Expand player details
    all_players = load_players()
    player_dict = {p.id: p for p in all_players}

    # Build response with expanded player info
    picks_with_details = []
    for pick in team.picks:
        player = player_dict.get(pick.player_id)
        if player:
            picks_with_details.append(
                {
                    "pick": pick.model_dump(),
                    "player": player.model_dump(),
                }
            )
        else:
            logger.warning(
                "Player %d not found in players.json, skipping from"
                " team %d roster display",
                pick.player_id,
                owner_id,
            )

    return {
        "owner_id": team.owner_id,
        "budget_remaining": team.budget_remaining,
        "picks": picks_with_details,
    }


@read_router.get("/api/v1/comments", response_model=list[CommentResponse])
def get_comments(
    since: int | None = Query(default=None, ge=0, description=_COMMENTS_SINCE_DESC),
    before: int | None = Query(default=None, ge=0, description=_COMMENTS_BEFORE_DESC),
    limit: int | None = Query(default=None, ge=1, description=_COMMENTS_LIMIT_DESC),
):
    """Analyst-booth commentary, ordered oldest-first (ascending `seq`)."""
    comments = [
        CommentResponse(
            seq=i,
            ts=c.ts,
            state_version=c.state_version,
            persona=c.persona,
            text=c.text,
        )
        for i, c in enumerate(read_comments(COMMENTS_FILE), start=1)
    ]
    if since is not None:
        comments = [c for c in comments if c.seq > since]
    if before is not None:
        comments = [c for c in comments if c.seq < before]
    if limit is not None:
        comments = comments[-limit:]
    return comments
