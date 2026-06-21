"""Auction-price archive models.

Per-season auction results for the league (2016-2024): what each owner paid for
each player. A standalone dataset from the league history -- prices come from the
league's draft sheets, while player identity, keeper status, and the ESPN player
id come from ESPN's draft data.

Picks are grouped by owner within each season (``seasons[year].owners[owner]``)
so the owner name isn't repeated on every pick.

``espn_id`` keys ESPN resources such as headshots
(``https://a.espncdn.com/i/headshots/nfl/players/full/{espn_id}.png``) and joins
to ``league_history`` by ``player`` name. Every current pick has one; the field
stays nullable for any future pick that can't be matched to ESPN.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuctionPick(BaseModel):
    """One player bought at auction: the player and what was paid."""

    player: str  # ESPN official name where known, else the draft-sheet name
    price: int  # auction salary
    keeper: bool = False  # kept from the prior season (vs. freshly auctioned)
    espn_id: int | None = None  # ESPN player id; null if ESPN lacks the pick


class SeasonAuction(BaseModel):
    """One season's auction, grouped by owner (league first name)."""

    owners: dict[str, list[AuctionPick]] = Field(default_factory=dict)


class AuctionPrices(BaseModel):
    """The full archive: each season's auction, keyed by year."""

    seasons: dict[str, SeasonAuction] = Field(default_factory=dict)
