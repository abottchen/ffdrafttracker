"""Pure draft-math helpers. No file I/O: callers pass loaded state/config in."""

from src.models import Configuration, DraftState, Team


def remaining_roster_spots(team: Team, config: Configuration) -> int:
    """How many roster slots this team has yet to fill."""
    return config.total_rounds - len(team.picks)


def max_bid(team: Team, config: Configuration) -> int | None:
    """Most this team may bid and still afford $1 for every other open slot.

    Reserves a hardcoded $1 per remaining slot (explicitly NOT config.min_bid).
    Returns None when the roster is already full (nothing left to bid on).
    """
    spots = remaining_roster_spots(team, config)
    if spots <= 0:
        return None
    return team.budget_remaining - (spots - 1)  # reserve $1 per other open slot


def position_count(
    team: Team, position: str, player_positions: dict[int, str]
) -> int:
    """Count a team's picks at `position`, resolving player_id -> position
    via the supplied lookup (e.g. {p.id: p.position for p in players})."""
    return sum(
        1
        for pick in team.picks
        if player_positions.get(pick.player_id) == position
    )


def _is_eligible(team: Team | None, config: Configuration) -> bool:
    return (
        team is not None
        and len(team.picks) < config.total_rounds
        and not team.manually_done
    )


def next_eligible_nominator(
    state: DraftState, config: Configuration, from_id: int, *, inclusive: bool
) -> int | None:
    """The next owner_id eligible to nominate, cycling in owner_id order.

    inclusive=True  -> may return from_id itself if still eligible (repair).
    inclusive=False -> starts at the next owner; only returns from_id if it is
                       the sole eligible team (advance / up_next).
    Returns None when no team is eligible.
    """
    owner_ids = sorted(t.owner_id for t in state.teams)
    if not owner_ids:
        return None
    start = owner_ids.index(from_id) if from_id in owner_ids else 0
    offsets = range(len(owner_ids)) if inclusive else range(1, len(owner_ids) + 1)
    for off in offsets:
        cand_id = owner_ids[(start + off) % len(owner_ids)]
        team = next((t for t in state.teams if t.owner_id == cand_id), None)
        if _is_eligible(team, config):
            return cand_id
    return None
