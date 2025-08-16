"""
Player statistics model for fantasy football draft tracker.

This module defines the data models for player statistics including
2024 season stats and 2025 bye weeks.
"""

from pydantic import BaseModel, Field, RootModel


class PassingStats(BaseModel):
    """Passing statistics for quarterbacks."""

    completions: str = Field(..., description="Number of completions")
    attempts: str = Field(..., description="Number of passing attempts")
    pct: str = Field(..., description="Completion percentage")
    yards: str = Field(..., description="Passing yards")
    avg: str = Field(..., description="Yards per attempt")
    tds: str = Field(..., description="Passing touchdowns")
    ints: str = Field(..., description="Interceptions thrown")
    sacks: str = Field(..., description="Times sacked")
    rating: str = Field(..., description="Passer rating")


class RushingStats(BaseModel):
    """Rushing statistics for running backs, wide receivers, and quarterbacks."""

    carries: str = Field(..., description="Number of rushing attempts")
    yards: str = Field(..., description="Rushing yards")
    avg: str = Field(..., description="Yards per carry")
    tds: str = Field(..., description="Rushing touchdowns")
    long: str = Field(..., description="Longest rush")
    fumbles: str = Field(..., description="Fumbles")


class ReceivingStats(BaseModel):
    """Receiving statistics for wide receivers, tight ends, and running backs."""

    receptions: str = Field(..., description="Number of receptions")
    targets: str = Field(..., description="Number of targets")
    yards: str = Field(..., description="Receiving yards")
    avg: str = Field(..., description="Yards per reception")
    tds: str = Field(..., description="Receiving touchdowns")
    long: str = Field(..., description="Longest reception")
    fumbles: str = Field(..., description="Fumbles")


class KickingStats(BaseModel):
    """Kicking statistics for kickers."""

    fgm: str = Field(..., description="Field goals made")
    fga: str = Field(..., description="Field goals attempted")
    fg_pct: str = Field(..., description="Field goal percentage")
    long: str = Field(..., description="Longest field goal")
    xpm: str = Field(..., description="Extra points made")
    xpa: str = Field(..., description="Extra points attempted")
    points: str = Field(..., description="Total points scored")


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
