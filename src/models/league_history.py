"""League history archive models.

Season-by-season record of the league (2003-2025): champion, runner-up, best
regular-season record, and -- where the source platform exposes it -- every
team's full standings and end-of-season roster with draft prices/picks.

Sourced from ESPN (2012-2025) and Yahoo (2003-2011). League members are stored
as first names only; no last names, emails, or account handles.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, Field


class RosterEntry(BaseModel):
    """One player on a team's end-of-season roster."""

    player_name: str
    position: str = ""
    nfl_team: str = ""
    slot: str = ""
    acquisition: str = "DRAFTED"  # DRAFTED | ADDED | TRADED
    draft_price: int | None = None  # auction salary, if drafted at auction
    draft_pick: int | None = None  # overall pick number, if drafted in a snake


class TeamSeason(BaseModel):
    """One team's season: record, final finish, and roster."""

    team_name: str
    owner: str  # league first name
    wins: int = 0
    losses: int = 0
    ties: int = 0
    points_for: float | None = None  # regular-season points (None if not captured)
    final_rank: int | None = None  # 1 = champion, 2 = runner-up, ...
    roster: list[RosterEntry] = Field(default_factory=list)


class Finisher(BaseModel):
    owner: str
    team_name: str


class BestRecord(Finisher):
    record: str  # "12-2" or "10-2-1"


class SeasonResult(BaseModel):
    year: int
    champion: Finisher
    runner_up: Finisher
    best_record: BestRecord
    shared_title: bool = False
    note: str | None = None
    source: str = "manual"  # "espn" | "yahoo" | "manual"
    draft_type: str | None = None  # "auction" | "snake"
    standings: list[TeamSeason] = Field(default_factory=list)


class ChampionCount(BaseModel):
    owner: str
    titles: int
    last_title_year: int


class LeagueHistory(BaseModel):
    seasons: list[SeasonResult] = Field(default_factory=list)

    def championship_counts(self) -> list[ChampionCount]:
        """Derived "Most Championships" leaderboard.

        Each season's champion gets +1; a ``shared_title`` season also credits
        its runner-up (the 2022 co-championship). Sorted by titles desc, then
        most-recent title, then owner name.
        """
        titles: dict[str, int] = defaultdict(int)
        last_year: dict[str, int] = {}
        for s in self.seasons:
            winners = [s.champion.owner]
            if s.shared_title:
                winners.append(s.runner_up.owner)
            for w in winners:
                titles[w] += 1
                last_year[w] = max(last_year.get(w, s.year), s.year)
        counts = [
            ChampionCount(owner=o, titles=t, last_title_year=last_year[o])
            for o, t in titles.items()
        ]
        counts.sort(key=lambda c: (-c.titles, -c.last_title_year, c.owner))
        return counts
