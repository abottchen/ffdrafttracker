"""Build the scrubbed league-history archive from raw ESPN/Yahoo captures.

Reads the gitignored ``data/raw_history/{espn,yahoo}/<year>.json`` captures,
resolves owners to first names, derives each season's headline (champion /
runner-up / best record), and emits a validated :class:`LeagueHistory`.

The raw captures are produced by the read-only browser capture step (see the
plan). This module is the pure, testable transform: no network access.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.models.league_history import (
    BestRecord,
    Finisher,
    LeagueHistory,
    RosterEntry,
    SeasonResult,
    TeamSeason,
)

# --- Yahoo team -> owner first name (2003-2011) ------------------------------
# Resolved from Yahoo manager hints + the manual table + ESPN team continuity.
# Teams whose manager was hidden and could not be resolved are left to
# UNKNOWN_OWNER and reported for the user to confirm.
YAHOO_OWNER: dict[str, str] = {
    # Steve
    "ARRR! imapirate": "Steve",
    "Cpt. Pimpslap": "Steve",
    "Notchocheez": "Steve",
    "Flying Hellfish": "Steve",
    "Mjr. Bwl. Mvmnet": "Steve",
    # Jackie
    "Blood Sweat & Beers": "Jackie",
    "BloodSweat&Beers": "Jackie",
    # Jodi
    "BurrestedDevelopment": "Jodi",
    "Favre's Flip Flops": "Jodi",
    "Forever Vince Young": "Jodi",
    "Mons Goblin Raiders": "Jodi",
    "Orton Hears a Boo": "Jodi",
    "Psycho Monkeys": "Jodi",
    "Waiver Wizards": "Jodi",
    # Raman
    "Fighting Roos": "Raman",
    "The Nightmare!": "Raman",
    # Rob
    "Fish & Chimps": "Rob",
    # Adam
    "Game Time Decisions": "Adam",
    "Healthy Scratches": "Adam",
    "Illegal Touching": "Adam",
    "Marty Ball": "Adam",
    "Random Morons": "Adam",
    "The Red Shirt Squad": "Adam",
    "Turf Burglars": "Adam",
    "Will Punt For Food": "Adam",
    # Angie
    "Bea Bea's Ballers": "Angie",
    "BeaBea's Ballers": "Angie",
    "Sparkling White Pain": "Angie",
    # Greg
    "Dwarf Tossers": "Greg",
    "The Juicers": "Greg",
    # Elisa
    "Cowboys Cheerleaders": "Elisa",
    "Cowboys Cheerleader": "Elisa",
    "Ashley Schaeffer BMW": "Elisa",
    # Jason
    "Sack Wranglers": "Jason",
    # Jen
    "Wet Bandanas": "Jen",
    # th3
    "Team GAAAAAAAAHHH!!!": "th3",
    "Wedding Day Ditkas": "th3",
    # Lance ("LD")
    "Ft Worth Fanatics": "Lance",
    "Rockin N Roanoke": "Lance",
    "Roanoke Rowers": "Lance",
    # Resolved with the user (hidden managers, by elimination):
    "Sweet Sundaes": "Jen",  # 2008
    "Wildcats": "Jen",  # 2005
    "FantasyGirl": "Elisa",  # 2005
    "Thunderbuns 3000": "Elisa",  # 2004
    # Inferred from core-member gap years, confirmed with the user:
    "Mississippi Mudcats": "Angie",  # 2007
    "Prestige Worldwide": "Greg",  # 2009
    "Alan's Wolf Pack": "Greg",  # 2010
    "Los Pollos Hermanos": "Elisa",  # 2011
}

UNKNOWN_OWNER = "UNKNOWN"

# Manual table headline owners for the pre-2012 reconciliation cross-check.
# (champion_owner, runner_up_owner, best_record_owner)
# 2011 best_record corrected to Greg: Yahoo points-for (the authoritative
# tiebreak) gives The Juicers 1783.28 over Mjr. Bwl. Mvmnet 1782.11 at 10-3.
MANUAL_PRE2012: dict[int, tuple[str, str, str]] = {
    2011: ("Steve", "Greg", "Greg"),
    2010: ("Adam", "Angie", "Adam"),
    2009: ("Jackie", "Steve", "Jackie"),
    2008: ("Angie", "th3", "th3"),
    2007: ("Elisa", "Steve", "Raman"),
    2006: ("Steve", "Adam", "Steve"),
    2005: ("Greg", "Jodi", "Jason"),
    2004: ("Jackie", "Greg", "Jackie"),
    2003: ("Greg", "Jackie", "Jen"),
}


def _record_str(t: dict | TeamSeason) -> str:
    w = t["wins"] if isinstance(t, dict) else t.wins
    losses = t["losses"] if isinstance(t, dict) else t.losses
    ties = t["ties"] if isinstance(t, dict) else t.ties
    return f"{w}-{losses}-{ties}" if ties else f"{w}-{losses}"


def _best_record_team(teams: list[TeamSeason]) -> TeamSeason:
    """Team with the best regular-season record (win pct, then wins, then
    points-for -- the same tiebreaker the league standings use)."""

    def key(t: TeamSeason):
        games = t.wins + t.losses + t.ties
        pct = (t.wins + 0.5 * t.ties) / games if games else 0.0
        return (pct, t.wins, t.points_for or 0.0)

    return max(teams, key=key)


def _team_seasons_espn(raw: dict) -> list[TeamSeason]:
    teams = []
    for t in raw["teams"]:
        teams.append(
            TeamSeason(
                source_team_id=t["source_team_id"],
                team_name=t["team_name"],
                owner=t["owner"],
                wins=t["wins"],
                losses=t["losses"],
                ties=t["ties"],
                points_for=t.get("points_for"),
                final_rank=t.get("final_rank"),
                roster=[RosterEntry(**r) for r in t["roster"]],
            )
        )
    return teams


def _team_seasons_yahoo(raw: dict, unresolved: set[str]) -> list[TeamSeason]:
    teams = []
    for t in raw["teams"]:
        owner = YAHOO_OWNER.get(t["team_name"])
        if owner is None:
            owner = UNKNOWN_OWNER
            unresolved.add(
                f"{raw['year']}: {t['team_name']} (hint={t.get('manager_hint', '')!r})"
            )
        teams.append(
            TeamSeason(
                source_team_id=t["source_team_id"],
                team_name=t["team_name"],
                owner=owner,
                wins=t["wins"],
                losses=t["losses"],
                ties=t["ties"],
                points_for=t.get("points_for"),
                final_rank=t.get("final_rank"),
                roster=[RosterEntry(**r) for r in t["roster"]],
            )
        )
    return teams


def _finisher(team: TeamSeason) -> Finisher:
    return Finisher(owner=team.owner, team_name=team.team_name)


def _season_from_standings(
    *, year: int, source: str, draft_type: str | None, teams: list[TeamSeason]
) -> SeasonResult:
    by_rank = {t.final_rank: t for t in teams if t.final_rank}
    champ = by_rank.get(1) or teams[0]
    runner = by_rank.get(2) or teams[0]
    best = _best_record_team(teams)
    season = SeasonResult(
        year=year,
        champion=_finisher(champ),
        runner_up=_finisher(runner),
        best_record=BestRecord(
            owner=best.owner, team_name=best.team_name, record=_record_str(best)
        ),
        source=source,
        draft_type=draft_type,
        standings=teams,
    )
    if year == 2022:  # league-side co-championship (credits the runner-up)
        season.shared_title = True
        season.note = "SPLIT TITLE"
    return season


def build(raw_dir: Path) -> tuple[LeagueHistory, list[str]]:
    """Build the archive from ``raw_dir`` (containing ``espn/`` and ``yahoo/``).

    Returns the validated history plus a list of unresolved Yahoo owners.
    """
    seasons: list[SeasonResult] = []
    unresolved: set[str] = set()

    for f in sorted((raw_dir / "espn").glob("*.json")):
        raw = json.loads(f.read_text())
        seasons.append(
            _season_from_standings(
                year=raw["year"],
                source="espn",
                draft_type=raw.get("draft_type", "auction"),
                teams=_team_seasons_espn(raw),
            )
        )
    for f in sorted((raw_dir / "yahoo").glob("*.json")):
        raw = json.loads(f.read_text())
        seasons.append(
            _season_from_standings(
                year=raw["year"],
                source="yahoo",
                draft_type=raw.get("draft_type"),
                teams=_team_seasons_yahoo(raw, unresolved),
            )
        )

    seasons.sort(key=lambda s: s.year, reverse=True)
    return LeagueHistory(seasons=seasons), sorted(unresolved)


def reconcile(history: LeagueHistory) -> list[str]:
    """Compare derived pre-2012 headline owners vs the manual table."""
    msgs: list[str] = []
    for s in history.seasons:
        exp = MANUAL_PRE2012.get(s.year)
        if not exp:
            continue
        got = (s.champion.owner, s.runner_up.owner, s.best_record.owner)
        labels = ("champion", "runner_up", "best_record")
        for label, e, g in zip(labels, exp, got):
            if e != g:
                team = getattr(s, label).team_name
                msgs.append(f"{s.year} {label}: manual={e} vs derived={g} ({team})")
    return msgs
