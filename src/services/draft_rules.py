"""Pure draft-math helpers. No file I/O: callers pass loaded state/config in."""

from src.models import Configuration, Team


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
