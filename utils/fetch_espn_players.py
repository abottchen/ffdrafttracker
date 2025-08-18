#!/usr/bin/env python3
"""
Fetch NFL player data from ESPN and generate players.json file.

Usage:
    python fetch_espn_players.py          # Fetch all teams
    python fetch_espn_players.py KC       # Fetch only Kansas City Chiefs
"""

import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# Add parent directory to path to import our enums
sys.path.append(str(Path(__file__).parent.parent))
from src.enums.position import Position

# ESPN team URLs mapping
TEAM_URLS = {
    "ARI": "https://www.espn.com/nfl/team/roster/_/name/ari/arizona-cardinals",
    "ATL": "https://www.espn.com/nfl/team/roster/_/name/atl/atlanta-falcons",
    "BAL": "https://www.espn.com/nfl/team/roster/_/name/bal/baltimore-ravens",
    "BUF": "https://www.espn.com/nfl/team/roster/_/name/buf/buffalo-bills",
    "CAR": "https://www.espn.com/nfl/team/roster/_/name/car/carolina-panthers",
    "CHI": "https://www.espn.com/nfl/team/roster/_/name/chi/chicago-bears",
    "CIN": "https://www.espn.com/nfl/team/roster/_/name/cin/cincinnati-bengals",
    "CLE": "https://www.espn.com/nfl/team/roster/_/name/cle/cleveland-browns",
    "DAL": "https://www.espn.com/nfl/team/roster/_/name/dal/dallas-cowboys",
    "DEN": "https://www.espn.com/nfl/team/roster/_/name/den/denver-broncos",
    "DET": "https://www.espn.com/nfl/team/roster/_/name/det/detroit-lions",
    "GB": "https://www.espn.com/nfl/team/roster/_/name/gb/green-bay-packers",
    "HOU": "https://www.espn.com/nfl/team/roster/_/name/hou/houston-texans",
    "IND": "https://www.espn.com/nfl/team/roster/_/name/ind/indianapolis-colts",
    "JAX": "https://www.espn.com/nfl/team/roster/_/name/jax/jacksonville-jaguars",
    "KC": "https://www.espn.com/nfl/team/roster/_/name/kc/kansas-city-chiefs",
    "LAC": "https://www.espn.com/nfl/team/roster/_/name/lac/los-angeles-chargers",
    "LAR": "https://www.espn.com/nfl/team/roster/_/name/lar/los-angeles-rams",
    "LV": "https://www.espn.com/nfl/team/roster/_/name/lv/las-vegas-raiders",
    "MIA": "https://www.espn.com/nfl/team/roster/_/name/mia/miami-dolphins",
    "MIN": "https://www.espn.com/nfl/team/roster/_/name/min/minnesota-vikings",
    "NE": "https://www.espn.com/nfl/team/roster/_/name/ne/new-england-patriots",
    "NO": "https://www.espn.com/nfl/team/roster/_/name/no/new-orleans-saints",
    "NYG": "https://www.espn.com/nfl/team/roster/_/name/nyg/new-york-giants",
    "NYJ": "https://www.espn.com/nfl/team/roster/_/name/nyj/new-york-jets",
    "PHI": "https://www.espn.com/nfl/team/roster/_/name/phi/philadelphia-eagles",
    "PIT": "https://www.espn.com/nfl/team/roster/_/name/pit/pittsburgh-steelers",
    "SEA": "https://www.espn.com/nfl/team/roster/_/name/sea/seattle-seahawks",
    "SF": "https://www.espn.com/nfl/team/roster/_/name/sf/san-francisco-49ers",
    "TB": "https://www.espn.com/nfl/team/roster/_/name/tb/tampa-bay-buccaneers",
    "TEN": "https://www.espn.com/nfl/team/roster/_/name/ten/tennessee-titans",
    "WAS": "https://www.espn.com/nfl/team/roster/_/name/wsh/washington-commanders",
}


# Position mapping from ESPN to our enum
POSITION_MAP = {
    "QB": Position.QB,
    "RB": Position.RB,
    "WR": Position.WR,
    "TE": Position.TE,
    "PK": Position.K,  # ESPN uses PK for kickers
    "K": Position.K,   # Just in case
}


def fetch_team_roster(team_abbr: str, url: str) -> list[dict]:
    """Fetch roster data for a single team from ESPN."""
    print(f"Fetching roster for {team_abbr}...")

    try:
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error fetching {team_abbr}: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    players = []

    # Find all player links with names (not empty ones)
    player_links = soup.find_all('a', href=re.compile(r'/nfl/player/_/id/(\d+)/'))
    named_links = [link for link in player_links if link.text.strip()]

    print(f"  Found {len(named_links)} named player links")

    processed_ids = set()  # Track processed player IDs to avoid duplicates

    for link in named_links:
        # Extract player ID from link
        href = link.get('href', '')
        match = re.search(r'/id/(\d+)/', href)
        if not match:
            continue

        player_id = int(match.group(1))

        # Get player name from the link text
        full_name = link.text.strip()
        if not full_name:
            continue

        # Skip if we've already processed this player
        if player_id in processed_ids:
            print(f"    DUPLICATE SKIPPED: {full_name} (ID: {player_id}) - {team_abbr}")
            continue
        processed_ids.add(player_id)

        # Split name into first and last
        name_parts = full_name.split(' ', 1)
        if len(name_parts) >= 2:
            first_name, last_name = name_parts[0], name_parts[1]
        else:
            first_name = full_name
            last_name = ""

        # Find the table row containing this link to get position
        row = link.find_parent('tr')
        position = None

        if row:
            # Get all text content from this row
            row_text = row.get_text()

            # Look for position patterns in the text using regex
            # Look for positions clearly separated from names by numbers (jersey#)
            # Pattern: number + position + number (jersey# + position + age)
            for pos_key in ['QB', 'RB', 'WR', 'TE', 'PK']:
                # Look for position pattern: digit + position + digit (like 15QB29)
                pattern = f'\\d{pos_key}\\d'
                if re.search(pattern, row_text.upper()):
                    position = POSITION_MAP[pos_key].value
                    break

            # Special case for single-letter position "K" - need to be extra careful
            if not position:
                # For K, look for patterns like "7PK30" first (prefer PK over K)
                # If no PK found, then look for K pattern but be more strict
                k_pattern = r'\d+K\d+'  # digit(s) + K + digit(s)
                if re.search(k_pattern, row_text.upper()):
                    # Additional validation: make sure this isn't part of a name
                    # Check if the K is preceded by a name character
                    k_match = re.search(r'(\w)K\d', row_text.upper())
                    if k_match:
                        preceding_char = k_match.group(1)
                        # If preceded by a letter that could be part of a name, skip
                        if preceding_char.isalpha():
                            pass  # Skip - K is likely part of a name, not a position
                        else:
                            position = POSITION_MAP['K'].value
                    else:
                        position = POSITION_MAP['K'].value

        # If no position found in table row, skip this player
        if not position:
            continue

        # Additional validation: only include if we found a valid fantasy position
        if position in [pos.value for pos in Position]:
            players.append({
                "id": player_id,
                "first_name": first_name,
                "last_name": last_name,
                "team": team_abbr,
                "position": position
            })
            print(f"    Found: {first_name} {last_name} ({position}) - ID: {player_id}")

    print(f"  Found {len(players)} fantasy-relevant players for {team_abbr}")
    return players


def fetch_all_players(team_filter: str | None = None) -> list[dict]:
    """Fetch all players from ESPN, optionally filtered by team."""
    all_players = []

    if team_filter:
        # Fetch only the specified team
        team_filter = team_filter.upper()
        if team_filter not in TEAM_URLS:
            print(f"Error: Team '{team_filter}' not found")
            print(f"Valid teams: {', '.join(sorted(TEAM_URLS.keys()))}")
            return []

        players = fetch_team_roster(team_filter, TEAM_URLS[team_filter])
        all_players.extend(players)
    else:
        # Fetch all teams
        for team_abbr, url in sorted(TEAM_URLS.items()):
            players = fetch_team_roster(team_abbr, url)
            all_players.extend(players)
            time.sleep(1)  # Be polite to ESPN servers

    return all_players


def generate_defenses() -> list[dict]:
    """Generate all 32 NFL defense entries using IDs 1-32."""
    # Team city names in alphabetical order by team abbreviation
    team_cities = {
        "ARI": "Arizona",
        "ATL": "Atlanta",
        "BAL": "Baltimore",
        "BUF": "Buffalo",
        "CAR": "Carolina",
        "CHI": "Chicago",
        "CIN": "Cincinnati",
        "CLE": "Cleveland",
        "DAL": "Dallas",
        "DEN": "Denver",
        "DET": "Detroit",
        "GB": "Green Bay",
        "HOU": "Houston",
        "IND": "Indianapolis",
        "JAX": "Jacksonville",
        "KC": "Kansas City",
        "LAC": "Los Angeles",
        "LAR": "Los Angeles",
        "LV": "Las Vegas",
        "MIA": "Miami",
        "MIN": "Minnesota",
        "NE": "New England",
        "NO": "New Orleans",
        "NYG": "New York",
        "NYJ": "New York",
        "PHI": "Philadelphia",
        "PIT": "Pittsburgh",
        "SEA": "Seattle",
        "SF": "San Francisco",
        "TB": "Tampa Bay",
        "TEN": "Tennessee",
        "WAS": "Washington"
    }

    # Team names in alphabetical order by team abbreviation
    team_names = {
        "ARI": "Cardinals",
        "ATL": "Falcons",
        "BAL": "Ravens",
        "BUF": "Bills",
        "CAR": "Panthers",
        "CHI": "Bears",
        "CIN": "Bengals",
        "CLE": "Browns",
        "DAL": "Cowboys",
        "DEN": "Broncos",
        "DET": "Lions",
        "GB": "Packers",
        "HOU": "Texans",
        "IND": "Colts",
        "JAX": "Jaguars",
        "KC": "Chiefs",
        "LAC": "Chargers",
        "LAR": "Rams",
        "LV": "Raiders",
        "MIA": "Dolphins",
        "MIN": "Vikings",
        "NE": "Patriots",
        "NO": "Saints",
        "NYG": "Giants",
        "NYJ": "Jets",
        "PHI": "Eagles",
        "PIT": "Steelers",
        "SEA": "Seahawks",
        "SF": "49ers",
        "TB": "Buccaneers",
        "TEN": "Titans",
        "WAS": "Commanders"
    }

    defenses = []
    player_id = 1

    # Generate defenses in alphabetical order by team abbreviation
    for team_abbr in sorted(team_cities.keys()):
        defense = {
            "id": player_id,
            "first_name": team_cities[team_abbr],
            "last_name": team_names[team_abbr],
            "team": team_abbr,
            "position": "D/ST"
        }
        defenses.append(defense)
        player_id += 1

    return defenses


def main():
    """Main entry point."""
    # Check for team filter argument
    team_filter = None
    if len(sys.argv) > 1:
        team_filter = sys.argv[1]

    # Generate defenses first (IDs 1-32)
    print("Generating NFL defenses...")
    defenses = generate_defenses()
    print(f"Generated {len(defenses)} defenses")

    # Fetch player data from ESPN
    players = fetch_all_players(team_filter)

    if not players:
        print("No players fetched")
        return

    # Combine defenses and players
    all_players = defenses + players

    # Sort players by last name, then first name (defenses sort to top alphabetically)
    all_players.sort(key=lambda p: (p['last_name'], p['first_name']))

    # Write to players.json
    output_path = Path(__file__).parent.parent / 'data' / 'players.json'
    output_path.parent.mkdir(exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(all_players, f, indent=2)

    print(f"\nSuccessfully wrote {len(all_players)} players to {output_path}")
    print(f"  - {len(defenses)} defenses (IDs 1-32)")
    print(f"  - {len(players)} individual players")

    # Print summary by position
    position_counts = {}
    for player in all_players:
        pos = player['position']
        position_counts[pos] = position_counts.get(pos, 0) + 1

    print("\nPlayers by position:")
    for pos in sorted(position_counts.keys()):
        print(f"  {pos}: {position_counts[pos]}")


if __name__ == "__main__":
    main()
