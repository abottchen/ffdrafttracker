"""Mutating (admin-only) API endpoints."""

import asyncio
import io
import logging

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from src import persistence as _persistence
from src.api.schemas import (
    AdminDraftRequest,
    BidRequest,
    DraftRequest,
    NominateRequest,
    ResetRequest,
    TeamUpdateRequest,
    TransferRequest,
)
from src.draft_rules import (
    check_position_limit,
    max_bid,
    next_eligible_nominator,
    next_pick_id,
    remaining_roster_spots,
)
from src.models import DraftPick, DraftState, Nominated, Team
from src.persistence import (
    load_configuration,
    load_draft_state,
    load_owners,
    load_players,
)

logger = logging.getLogger(__name__)

# Serialise all state mutations so the load-check-save cycle is atomic.
_state_lock = asyncio.Lock()

admin_router = APIRouter()


def check_version(current_version: int, expected_version: int) -> None:
    """Check version for optimistic locking."""
    if current_version != expected_version:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Draft state has changed (version {current_version} != "
                f"{expected_version}). Please refresh and try again."
            ),
        )


def parse_etag_version(if_match: str) -> int:
    """Extract the integer version from an ``If-Match`` ETag header.

    Raises ``HTTPException(400)`` when the value is not a valid integer.
    """
    try:
        return int(if_match.strip('"'))
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="If-Match header must contain a valid version number",
        )


def generate_draft_csv() -> str:
    """Generate CSV content based on current draft state."""
    import csv

    draft_state = load_draft_state()
    owners = load_owners()
    players = load_players()

    player_dict = {p.id: p for p in players}
    sorted_owner_ids = sorted(owners.keys())

    csv_output = io.StringIO()
    writer = csv.writer(csv_output, quoting=csv.QUOTE_ALL)

    # Row 1: owner names paired with empty cells
    header_row = []
    for owner_id in sorted_owner_ids:
        header_row.extend([owners[owner_id]["owner_name"], ""])
    writer.writerow(header_row)

    # Row 2: alternating Player / $ sub-headers
    sub_header = []
    for _ in sorted_owner_ids:
        sub_header.extend(["Player", "$"])
    writer.writerow(sub_header)

    # Collect picks per owner
    owner_picks = {}
    for team in draft_state.teams:
        if team.owner_id in sorted_owner_ids:
            owner_picks[team.owner_id] = team.picks
        else:
            logger.warning(
                "Team owner_id %d not in owners list, skipping from CSV export",
                team.owner_id,
            )

    max_picks = max(len(picks) for picks in owner_picks.values()) if owner_picks else 0

    for pick_index in range(max_picks):
        row = []
        for owner_id in sorted_owner_ids:
            picks = owner_picks.get(owner_id, [])
            if pick_index < len(picks):
                pick = picks[pick_index]
                player = player_dict.get(pick.player_id)
                if player:
                    name = f"{player.last_name}, {player.first_name}"
                    row.extend([name, str(pick.price)])
                else:
                    name = f"Unknown Player (ID: {pick.player_id})"
                    row.extend([name, str(pick.price)])
            else:
                row.extend(["", ""])
        writer.writerow(row)

    csv_content = csv_output.getvalue()
    csv_output.close()
    return csv_content


@admin_router.get("/api/v1/export/csv")
async def export_draft_csv():
    """Export current draft state as CSV file (admin only)."""
    try:
        csv_content = generate_draft_csv()

        # Return as streaming response with appropriate headers
        return StreamingResponse(
            io.BytesIO(csv_content.encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=draft_export.csv"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate CSV export: {str(e)}"
        )


@admin_router.post("/api/v1/nominate")
async def nominate_player(request: NominateRequest):
    # Turn order intentionally not enforced -- admin controls nomination sequence.
    """Nominate a player for auction."""
    async with _state_lock:
        # Load current state
        draft_state = load_draft_state()
        config = load_configuration()

        # Check version
        check_version(draft_state.version, request.expected_version)

        # Validate no current nomination
        if draft_state.nominated is not None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "A player is already nominated. Complete or cancel the "
                    "current nomination first."
                ),
            )

        # Validate bid amount
        if request.initial_bid < config.min_bid:
            raise HTTPException(
                status_code=422,
                detail=f"Initial bid must be at least ${config.min_bid}",
            )

        # Validate player is available
        if request.player_id not in draft_state.available_player_ids:
            raise HTTPException(
                status_code=422,
                detail=f"Player {request.player_id} is not available",
            )

        # Validate owner exists
        owners = load_owners()
        if request.owner_id not in owners:
            raise HTTPException(
                status_code=422,
                detail=f"Owner {request.owner_id} does not exist",
            )

        # Find the nominating team and enforce the max-bid reserve rule.
        team = next(
            (t for t in draft_state.teams if t.owner_id == request.owner_id),
            None,
        )
        if team is not None:
            mb = max_bid(team, config)
            if mb is None:
                raise HTTPException(
                    status_code=422,
                    detail="Roster is full; this team cannot nominate.",
                )
            if request.initial_bid > mb:
                spots = remaining_roster_spots(team, config)
                remaining_after = team.budget_remaining - request.initial_bid
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Insufficient budget. After "
                        f"${request.initial_bid} bid, "
                        f"you would have ${remaining_after} left but "
                        f"need at least ${spots - 1} to fill remaining "
                        f"{spots - 1} roster spots"
                    ),
                )

        # Enforce position maximum for the nominating team.
        players = load_players()
        player = next((p for p in players if p.id == request.player_id), None)
        if player is not None:
            pos_err = check_position_limit(team, player, players, config)
            if pos_err is not None:
                raise HTTPException(status_code=422, detail=pos_err)

        # Create nomination
        draft_state.nominated = Nominated(
            player_id=request.player_id,
            current_bid=request.initial_bid,
            current_bidder_id=request.owner_id,
            nominating_owner_id=request.owner_id,
        )

        # Save state with version increment
        draft_state.save_to_file(_persistence.DRAFT_STATE_FILE)

        # Return success with player details
        owner = owners.get(request.owner_id, {})

        # Log action with names
        player_name = (
            f"{player.first_name} {player.last_name}"
            if player
            else f"ID:{request.player_id}"
        )
        owner_name = owner.get("owner_name", f"ID:{request.owner_id}")
        logger.info(
            f"Player {player_name} nominated by {owner_name} for ${request.initial_bid}"
        )

        return {
            "success": True,
            "nomination": draft_state.nominated.model_dump(),
            "player": player.model_dump() if player else None,
            "new_version": draft_state.version,
        }


@admin_router.post("/api/v1/bid")
async def place_bid(request: BidRequest):
    """Place a bid on the currently nominated player."""
    async with _state_lock:
        # Load current state
        draft_state = load_draft_state()
        config = load_configuration()

        # Check version
        check_version(draft_state.version, request.expected_version)

        # Validate nomination exists
        if draft_state.nominated is None:
            raise HTTPException(
                status_code=422,
                detail="No player is currently nominated",
            )

        # Validate bid amount exceeds current
        if request.bid_amount <= draft_state.nominated.current_bid:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Bid must exceed current bid of "
                    f"${draft_state.nominated.current_bid}"
                ),
            )

        # Validate bid meets minimum
        if request.bid_amount < config.min_bid:
            raise HTTPException(
                status_code=422,
                detail=f"Bid must be at least ${config.min_bid}",
            )

        # Find bidding team and validate budget
        team = next(
            (t for t in draft_state.teams if t.owner_id == request.owner_id),
            None,
        )
        if not team:
            raise HTTPException(
                status_code=422,
                detail=(f"Team not found for owner {request.owner_id} in draft state"),
            )

        # Reject if the bid would break roster completion.
        mb = max_bid(team, config)
        if mb is None:
            raise HTTPException(
                status_code=422,
                detail="Roster is full; this team cannot bid.",
            )
        if request.bid_amount > mb:
            spots = remaining_roster_spots(team, config)
            remaining_budget_after_bid = team.budget_remaining - request.bid_amount
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Insufficient budget. After "
                    f"${request.bid_amount} bid, "
                    f"you would have "
                    f"${remaining_budget_after_bid} left but need "
                    f"at least ${spots - 1} to fill remaining "
                    f"{spots - 1} roster spots"
                ),
            )

        # Enforce position maximum for the bidding team.
        players = load_players()
        player = next(
            (p for p in players if p.id == draft_state.nominated.player_id),
            None,
        )
        if player is not None:
            pos_err = check_position_limit(team, player, players, config)
            if pos_err is not None:
                raise HTTPException(status_code=422, detail=pos_err)

        # Update bid
        previous_bid = draft_state.nominated.current_bid
        draft_state.nominated.current_bid = request.bid_amount
        draft_state.nominated.current_bidder_id = request.owner_id

        # Save state with version increment
        draft_state.save_to_file(_persistence.DRAFT_STATE_FILE)

        # Get names for logging
        owners = load_owners()
        owner = owners.get(request.owner_id, {})

        player_name = (
            f"{player.first_name} {player.last_name}"
            if player
            else f"ID:{draft_state.nominated.player_id}"
        )
        owner_name = owner.get("owner_name", f"ID:{request.owner_id}")

        # Log action
        logger.info(f"{owner_name} bid ${request.bid_amount} on {player_name}")

        return {
            "success": True,
            "nomination": draft_state.nominated.model_dump(),
            "previous_bid": previous_bid,
            "new_version": draft_state.version,
        }


@admin_router.post("/api/v1/draft")
async def complete_draft(request: DraftRequest):
    """Complete the auction and draft the player."""
    async with _state_lock:
        # Load current state
        draft_state = load_draft_state()

        # Check version
        check_version(draft_state.version, request.expected_version)

        # Validate nomination exists
        if draft_state.nominated is None:
            raise HTTPException(
                status_code=422,
                detail="No player is currently nominated",
            )

        # Validate player matches
        if draft_state.nominated.player_id != request.player_id:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Nominated player "
                    f"{draft_state.nominated.player_id} doesn't "
                    f"match request {request.player_id}"
                ),
            )

        # Validate price matches current bid
        if draft_state.nominated.current_bid != request.final_price:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Final price ${request.final_price} doesn't "
                    f"match current bid "
                    f"${draft_state.nominated.current_bid}"
                ),
            )

        # Validate owner matches current bidder
        if draft_state.nominated.current_bidder_id != request.owner_id:
            raise HTTPException(
                status_code=422,
                detail=(f"Owner {request.owner_id} is not the current high bidder"),
            )

        # Find team (must exist - teams are immutable from owners.json)
        team = next(
            (t for t in draft_state.teams if t.owner_id == request.owner_id),
            None,
        )
        if not team:
            raise HTTPException(
                status_code=422,
                detail=(f"Team not found for owner {request.owner_id} in draft state"),
            )

        # Validate budget
        if request.final_price > team.budget_remaining:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Insufficient budget. Need "
                    f"${request.final_price} but only have "
                    f"${team.budget_remaining}"
                ),
            )

        # Create draft pick
        pick = DraftPick(
            pick_id=next_pick_id(draft_state),
            player_id=request.player_id,
            owner_id=request.owner_id,
            price=request.final_price,
        )

        # Update team
        team.picks.append(pick)
        team.budget_remaining -= request.final_price

        # Remove player from available
        if request.player_id not in draft_state.available_player_ids:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Data integrity error: player "
                    f"{request.player_id} is "
                    "not in the available player pool"
                ),
            )
        draft_state.available_player_ids.remove(request.player_id)

        # Clear nomination
        draft_state.nominated = None

        # Advance to next eligible nominator.
        config = load_configuration()
        nxt = next_eligible_nominator(
            draft_state,
            config,
            from_id=draft_state.next_to_nominate,
            inclusive=False,
        )
        if nxt is not None:
            draft_state.next_to_nominate = nxt

        # Save state with version increment
        draft_state.save_to_file(_persistence.DRAFT_STATE_FILE)

        # Get names for logging
        players = load_players()
        owners = load_owners()
        player = next((p for p in players if p.id == request.player_id), None)
        owner = owners.get(request.owner_id, {})

        player_name = (
            f"{player.first_name} {player.last_name}"
            if player
            else f"ID:{request.player_id}"
        )
        owner_name = owner.get("owner_name", f"ID:{request.owner_id}")

        # Log action
        logger.info(f"{player_name} drafted by {owner_name} for ${request.final_price}")

        return {
            "success": True,
            "pick": pick.model_dump(),
            "team": team.model_dump(),
            "next_to_nominate": draft_state.next_to_nominate,
            "new_version": draft_state.version,
        }


@admin_router.post("/api/v1/admin/draft")
async def admin_draft_player(request: AdminDraftRequest):
    """Admin-only endpoint to draft a player directly without auction.

    Intentionally skips budget and position-max validation -- this is the
    admin escape hatch for keepers and mid-draft corrections.
    """
    async with _state_lock:
        # Load current state
        draft_state = load_draft_state()

        # Check version
        check_version(draft_state.version, request.expected_version)

        # Validate player exists in players database
        players = load_players()
        player = next((p for p in players if p.id == request.player_id), None)
        if not player:
            raise HTTPException(
                status_code=422,
                detail=(f"Player {request.player_id} not found in players database"),
            )

        # Reject if the player is currently nominated.
        if (
            draft_state.nominated is not None
            and draft_state.nominated.player_id == request.player_id
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Player {request.player_id} is currently "
                    "nominated. Cancel the nomination first."
                ),
            )

        # Validate player is available for draft
        if request.player_id not in draft_state.available_player_ids:
            raise HTTPException(
                status_code=422,
                detail=(f"Player {request.player_id} is not available for draft"),
            )

        # Validate owner exists
        owners = load_owners()
        if request.owner_id not in owners:
            raise HTTPException(
                status_code=422,
                detail=f"Owner {request.owner_id} not found",
            )

        # Validate price is positive
        if request.price <= 0:
            raise HTTPException(
                status_code=400,
                detail="Price must be greater than 0",
            )

        # Find team (must exist for valid owner)
        team = next(
            (t for t in draft_state.teams if t.owner_id == request.owner_id),
            None,
        )
        if not team:
            raise HTTPException(
                status_code=422,
                detail=(f"Team not found for owner {request.owner_id} in draft state"),
            )

        # Create draft pick
        pick = DraftPick(
            pick_id=next_pick_id(draft_state),
            player_id=request.player_id,
            owner_id=request.owner_id,
            price=request.price,
        )

        # Add pick to team and adjust budget
        team.picks.append(pick)
        team.budget_remaining -= request.price

        # Remove player from available list
        draft_state.available_player_ids.remove(request.player_id)

        # Repair the nominator pointer.
        config = load_configuration()
        nxt = next_eligible_nominator(
            draft_state,
            config,
            from_id=draft_state.next_to_nominate,
            inclusive=True,
        )
        if nxt is not None:
            draft_state.next_to_nominate = nxt

        # Save state with version increment
        draft_state.save_to_file(_persistence.DRAFT_STATE_FILE)

        # Get names for logging (player already loaded above)
        owner = owners.get(request.owner_id, {})

        player_name = f"{player.first_name} {player.last_name}"
        owner_name = owner.get("owner_name", f"ID:{request.owner_id}")

        # Log action
        logger.info(
            f"ADMIN DRAFT: {owner_name} drafted {player_name} for ${request.price}"
        )

        return {
            "success": True,
            "pick": pick.model_dump(),
            "team": team.model_dump(),
            "new_version": draft_state.version,
        }


@admin_router.post("/api/v1/admin/transfer")
async def transfer_pick(request: TransferRequest):
    """Atomically transfer a draft pick from one team to another.

    Removes the pick from the source team (refunding budget) and adds it
    to the destination team (deducting budget) in a single load-mutate-save
    cycle.  Budget and position-limit validation is enforced for the
    destination team (same rules as the normal draft flow).
    """
    async with _state_lock:
        draft_state = load_draft_state()
        config = load_configuration()

        # Check version
        check_version(draft_state.version, request.expected_version)

        # Find the pick across all teams
        source_team: Team | None = None
        target_pick: DraftPick | None = None
        for team in draft_state.teams:
            for pick in team.picks:
                if pick.pick_id == request.pick_id:
                    source_team = team
                    target_pick = pick
                    break
            if target_pick is not None:
                break

        if target_pick is None or source_team is None:
            raise HTTPException(
                status_code=404,
                detail=f"Pick with ID {request.pick_id} not found",
            )

        # Prevent no-op transfer to the same team
        if source_team.owner_id == request.to_owner_id:
            raise HTTPException(
                status_code=422,
                detail="Source and destination teams are the same",
            )

        # Find destination team
        dest_team = next(
            (t for t in draft_state.teams if t.owner_id == request.to_owner_id),
            None,
        )
        if dest_team is None:
            owners = load_owners()
            if request.to_owner_id not in owners:
                raise HTTPException(
                    status_code=422,
                    detail=f"Owner {request.to_owner_id} not found",
                )
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Team not found for owner {request.to_owner_id} in draft state"
                ),
            )

        # Validate destination budget
        price = target_pick.price
        if price > dest_team.budget_remaining:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Insufficient budget. Need ${price} but "
                    f"destination team only has "
                    f"${dest_team.budget_remaining}"
                ),
            )

        # Validate destination max-bid reserve rule
        mb = max_bid(dest_team, config)
        if mb is None:
            raise HTTPException(
                status_code=422,
                detail="Destination team roster is full",
            )
        if price > mb:
            spots = remaining_roster_spots(dest_team, config)
            remaining_after = dest_team.budget_remaining - price
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Insufficient budget. After ${price} transfer, "
                    f"destination would have ${remaining_after} left "
                    f"but need at least ${spots - 1} to fill "
                    f"remaining {spots - 1} roster spots"
                ),
            )

        # Validate destination position limit
        players = load_players()
        player = next((p for p in players if p.id == target_pick.player_id), None)
        if player is not None:
            pos_err = check_position_limit(dest_team, player, players, config)
            if pos_err is not None:
                raise HTTPException(status_code=422, detail=pos_err)

        # --- Atomic mutation: remove from source, add to dest ---

        # Remove pick from source team and refund budget
        source_team.picks.remove(target_pick)
        source_team.budget_remaining += price

        # Create a new pick for the destination team
        new_pick = DraftPick(
            pick_id=next_pick_id(draft_state),
            player_id=target_pick.player_id,
            owner_id=request.to_owner_id,
            price=price,
        )
        dest_team.picks.append(new_pick)
        dest_team.budget_remaining -= price

        # Repair the nominator pointer
        nxt = next_eligible_nominator(
            draft_state,
            config,
            from_id=draft_state.next_to_nominate,
            inclusive=True,
        )
        if nxt is not None:
            draft_state.next_to_nominate = nxt

        # Save state with version increment
        draft_state.save_to_file(_persistence.DRAFT_STATE_FILE)

        # Log with names
        owners = load_owners()
        player_name = (
            f"{player.first_name} {player.last_name}"
            if player
            else f"ID:{target_pick.player_id}"
        )
        src_name = owners.get(source_team.owner_id, {}).get(
            "owner_name", f"ID:{source_team.owner_id}"
        )
        dst_name = owners.get(request.to_owner_id, {}).get(
            "owner_name", f"ID:{request.to_owner_id}"
        )
        logger.info(f"TRANSFER: {player_name} (${price}) from {src_name} to {dst_name}")

        return {
            "success": True,
            "pick": new_pick.model_dump(),
            "from_owner_id": source_team.owner_id,
            "to_owner_id": request.to_owner_id,
            "new_version": draft_state.version,
        }


@admin_router.patch("/api/v1/teams/{owner_id}")
async def update_team(owner_id: int, request: TeamUpdateRequest):
    """Set or clear a team's manually-done flag (admin action)."""
    async with _state_lock:
        draft_state = load_draft_state()
        check_version(draft_state.version, request.expected_version)

        team = next((t for t in draft_state.teams if t.owner_id == owner_id), None)
        if not team:
            raise HTTPException(
                status_code=404,
                detail=f"Team not found for owner {owner_id}",
            )

        team.manually_done = request.manually_done

        # Repair the nominator pointer.
        config = load_configuration()
        nxt = next_eligible_nominator(
            draft_state,
            config,
            from_id=draft_state.next_to_nominate,
            inclusive=True,
        )
        if nxt is not None:
            draft_state.next_to_nominate = nxt

        draft_state.save_to_file(_persistence.DRAFT_STATE_FILE)

        owners = load_owners()
        owner_name = owners.get(owner_id, {}).get("owner_name", f"ID:{owner_id}")
        logger.info(f"Team for {owner_name} manually_done set to {team.manually_done}")

        return {
            "success": True,
            "owner_id": owner_id,
            "manually_done": team.manually_done,
            "next_to_nominate": draft_state.next_to_nominate,
            "new_version": draft_state.version,
        }


@admin_router.delete("/api/v1/nominate")
async def cancel_nomination(
    if_match: str = Header(
        ..., description="ETag for optimistic locking (expected version)"
    ),
):
    """Cancel current nomination (admin action)."""
    async with _state_lock:
        # Load current state
        draft_state = load_draft_state()

        # Parse ETag and check version for optimistic locking
        expected_version = parse_etag_version(if_match)
        check_version(draft_state.version, expected_version)

        # Validate nomination exists
        if draft_state.nominated is None:
            raise HTTPException(
                status_code=422,
                detail="No nomination to cancel",
            )

        # Clear nomination
        cancelled_player = draft_state.nominated.player_id
        draft_state.nominated = None

        # Save state with version increment
        draft_state.save_to_file(_persistence.DRAFT_STATE_FILE)

        # Get player name for logging
        players = load_players()
        player = next((p for p in players if p.id == cancelled_player), None)
        player_name = (
            f"{player.first_name} {player.last_name}"
            if player
            else f"ID:{cancelled_player}"
        )

        logger.info(f"Nomination for {player_name} cancelled")

        return {
            "success": True,
            "cancelled_player_id": cancelled_player,
            "new_version": draft_state.version,
        }


@admin_router.delete("/api/v1/draft/{pick_id}")
async def remove_draft_pick(
    pick_id: int,
    if_match: str = Header(
        ..., description="ETag for optimistic locking (expected version)"
    ),
):
    """Remove a draft pick and restore player to available pool."""
    async with _state_lock:
        # Load current state
        draft_state = load_draft_state()

        # Parse ETag and check version for optimistic locking
        expected_version = parse_etag_version(if_match)
        check_version(draft_state.version, expected_version)

        # Find the pick and team
        pick_found = False
        target_team = None
        target_pick = None

        for team in draft_state.teams:
            for pick in team.picks:
                if pick.pick_id == pick_id:
                    target_team = team
                    target_pick = pick
                    pick_found = True
                    break
            if pick_found:
                break

        if not pick_found:
            raise HTTPException(
                status_code=404,
                detail=f"Pick with ID {pick_id} not found",
            )

        # Critical integrity check
        if target_pick.player_id in draft_state.available_player_ids:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Data integrity error: Player "
                    f"{target_pick.player_id} is drafted but also "
                    f"in available pool. Manual intervention "
                    f"required."
                ),
            )

        # Remove pick from team
        target_team.picks.remove(target_pick)

        # Restore budget
        target_team.budget_remaining += target_pick.price

        # Add player back to available pool
        draft_state.available_player_ids.append(target_pick.player_id)
        draft_state.available_player_ids.sort()

        # Save state with version increment
        draft_state.save_to_file(_persistence.DRAFT_STATE_FILE)

        # Get player name for logging
        players = load_players()
        player = next((p for p in players if p.id == target_pick.player_id), None)
        player_name = (
            f"{player.first_name} {player.last_name}"
            if player
            else f"ID:{target_pick.player_id}"
        )

        logger.info(f"Removed pick {pick_id}, returned {player_name} to available pool")

        return {
            "success": True,
            "removed_pick_id": pick_id,
            "restored_player_id": target_pick.player_id,
            "new_version": draft_state.version,
        }


@admin_router.post("/api/v1/reset")
async def reset_draft(request: ResetRequest):
    """Reset draft to initial state (admin action)."""
    async with _state_lock:
        # Load configuration for initial state
        config = load_configuration()
        players = load_players()
        owners = load_owners()

        # If not forcing, require and check version
        if not request.force:
            if request.expected_version is None:
                raise HTTPException(
                    status_code=422,
                    detail=("expected_version is required unless force=true"),
                )
            current_state = load_draft_state()
            check_version(current_state.version, request.expected_version)

        # Create fresh draft state
        owner_ids = sorted(owners.keys()) if owners else []
        initial_state = DraftState(
            nominated=None,
            available_player_ids=[p.id for p in players],
            teams=[
                Team(
                    owner_id=owner_id,
                    budget_remaining=config.initial_budget,
                    picks=[],
                )
                for owner_id in owner_ids
            ],
            next_to_nominate=owner_ids[0] if owner_ids else 1,
            version=1,
        )

        # Save without incrementing version (fresh start at v1)
        # NB: data/analyst-comments.jsonl is not cleared; its state_version
        # tags will collide with the new v1+ sequence.
        initial_state.save_to_file(
            _persistence.DRAFT_STATE_FILE, increment_version=False
        )

        logger.info("Draft reset to initial state")

        return {
            "success": True,
            "message": "Draft reset to initial state",
            "new_version": 1,
        }
