"""
Player statistics model for fantasy football draft tracker.

This module defines the data models for player statistics including
2024 season stats and 2025 bye weeks.

Stat fields are typed as ``int`` or ``float`` with ``BeforeValidator``
coercion so that raw JSON strings (including blanks, dashes, and
comma-separated numbers scraped from ESPN) are converted automatically.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, RootModel


def _coerce_int(v: object) -> int:
    """Coerce a stat value to ``int``; blanks / dashes / junk -> 0."""
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if not isinstance(v, str):
        return 0
    v = v.strip().replace(",", "")
    if not v or v == "-":
        return 0
    try:
        return int(v)
    except ValueError:
        try:
            return int(float(v))
        except ValueError:
            return 0


def _coerce_float(v: object) -> float:
    """Coerce a stat value to ``float``; blanks / dashes / junk -> 0.0."""
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str):
        return 0.0
    v = v.strip().replace(",", "")
    if not v or v == "-":
        return 0.0
    try:
        return float(v)
    except ValueError:
        return 0.0


StatInt = Annotated[int, BeforeValidator(_coerce_int)]
StatFloat = Annotated[float, BeforeValidator(_coerce_float)]


class PassingStats(BaseModel):
    """Passing statistics for quarterbacks."""

    completions: StatInt = Field(..., description="Number of completions")
    attempts: StatInt = Field(..., description="Number of passing attempts")
    pct: StatFloat = Field(..., description="Completion percentage")
    yards: StatInt = Field(..., description="Passing yards")
    avg: StatFloat = Field(..., description="Yards per attempt")
    tds: StatInt = Field(..., description="Passing touchdowns")
    ints: StatInt = Field(..., description="Interceptions thrown")
    sacks: StatInt = Field(..., description="Times sacked")
    rating: StatFloat = Field(..., description="Passer rating")


class RushingStats(BaseModel):
    """Rushing statistics for running backs, wide receivers, and quarterbacks."""

    carries: StatInt = Field(..., description="Number of rushing attempts")
    yards: StatInt = Field(..., description="Rushing yards")
    avg: StatFloat = Field(..., description="Yards per carry")
    tds: StatInt = Field(..., description="Rushing touchdowns")
    long: StatInt = Field(..., description="Longest rush")
    fumbles: StatInt = Field(..., description="Fumbles")


class ReceivingStats(BaseModel):
    """Receiving statistics for wide receivers, tight ends, and running backs."""

    receptions: StatInt = Field(..., description="Number of receptions")
    targets: StatInt = Field(..., description="Number of targets")
    yards: StatInt = Field(..., description="Receiving yards")
    avg: StatFloat = Field(..., description="Yards per reception")
    tds: StatInt = Field(..., description="Receiving touchdowns")
    long: StatInt = Field(..., description="Longest reception")
    fumbles: StatInt = Field(..., description="Fumbles")


class KickingStats(BaseModel):
    """Kicking statistics for kickers."""

    fgm: StatInt = Field(..., description="Field goals made")
    fga: StatInt = Field(..., description="Field goals attempted")
    fg_pct: StatFloat = Field(..., description="Field goal percentage")
    long: StatInt = Field(..., description="Longest field goal")
    xpm: StatInt = Field(..., description="Extra points made")
    xpa: StatInt = Field(..., description="Extra points attempted")
    points: StatInt = Field(..., description="Total points scored")


class PlayerStats(BaseModel):
    """Statistics for an individual player."""

    bye_week: int | None = Field(None, description="Bye week number (1-18)")
    position: str = Field(..., description="Player position")
    team: str = Field(..., description="NFL team abbreviation")

    # Optional stat categories based on position
    passing: PassingStats | None = Field(None, description="Passing statistics (QBs)")
    rushing: RushingStats | None = Field(
        None, description="Rushing statistics (RBs, WRs, QBs)"
    )
    receiving: ReceivingStats | None = Field(
        None, description="Receiving statistics (WRs, TEs, RBs)"
    )
    kicking: KickingStats | None = Field(None, description="Kicking statistics (Ks)")

    # Summary string for display
    stats_summary: str | None = Field(
        None, description="Formatted stats summary for UI display"
    )


class PlayerStatsCollection(RootModel[dict[str, PlayerStats]]):
    """Collection of player statistics keyed by player ID."""

    root: dict[str, PlayerStats] = Field(
        ..., description="Dictionary of player statistics keyed by player ID string"
    )

    def get_player_stats(self, player_id: int) -> PlayerStats | None:
        """Get stats for a specific player by ID."""
        return self.root.get(str(player_id))

    def has_player(self, player_id: int) -> bool:
        """Check if stats exist for a player."""
        return str(player_id) in self.root

    def get_all_stats(self) -> dict[str, PlayerStats]:
        """Get all player stats as a dictionary."""
        return self.root
