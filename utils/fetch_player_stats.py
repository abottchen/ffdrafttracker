#!/usr/bin/env python3
"""
Fetch NFL player stats and bye weeks from ESPN and generate player_stats.json file.

This script reads the existing players.json and fetches additional stats for each player.

Usage:
    python fetch_player_stats.py          # Fetch stats for all players
    python fetch_player_stats.py --limit 50  # Fetch only first 50 players (for testing)
"""

import json
import re
import sys
import time
import argparse
from pathlib import Path
from typing import Optional, Dict, List
import requests
from bs4 import BeautifulSoup


def extract_player_id_from_url(url: str) -> Optional[int]:
    """Extract player ID from ESPN URL."""
    match = re.search(r'/id/(\d+)/', url)
    return int(match.group(1)) if match else None


def fetch_player_stats(player_id: int, player_name: str, position: str) -> Optional[Dict]:
    """Fetch stats for a single player from their ESPN page."""
    url = f"https://www.espn.com/nfl/player/stats/_/id/{player_id}"
    
    try:
        response = requests.get(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"  Error fetching stats for {player_name}: {e}")
        return None
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    stats_data = {}
    
    # Look for ResponsiveTable divs (ESPN's structure)
    responsive_tables = soup.find_all('div', class_='ResponsiveTable')
    
    for div in responsive_tables:
        # Get the section title
        title_elem = div.find('div', class_='Table__Title')
        section_title = title_elem.get_text().strip().upper() if title_elem else ""
        
        # Find the two tables in this section
        tables = div.find_all('table')
        if len(tables) < 2:
            continue
            
        season_table = tables[0]  # Contains seasons/teams
        stats_table = tables[1]   # Contains actual stats
        
        # Find 2024 row index from season table
        season_rows = season_table.find_all('tr')[1:]  # Skip header
        target_row_idx = None
        
        for idx, row in enumerate(season_rows):
            cells = row.find_all(['td', 'th'])
            if cells and '2024' in cells[0].get_text().strip():
                target_row_idx = idx
                break
        
        if target_row_idx is None:
            continue  # No 2024 data in this section
        
        # Get headers from stats table
        stats_header_row = stats_table.find('tr')
        if not stats_header_row:
            continue
            
        headers = [th.get_text().strip().upper() for th in stats_header_row.find_all(['th', 'td'])]
        
        # Get 2024 stats from the corresponding row
        stats_rows = stats_table.find_all('tr')[1:]  # Skip header
        if target_row_idx >= len(stats_rows):
            continue
            
        target_stats_row = stats_rows[target_row_idx]
        cells = target_stats_row.find_all(['td', 'th'])
        cell_values = [cell.get_text().strip() for cell in cells]
        
        # Helper function to safely get value by header
        def get_stat(header_keywords):
            for keyword in header_keywords:
                idx = next((i for i, h in enumerate(headers) if keyword in h), None)
                if idx and idx < len(cell_values):
                    return cell_values[idx]
            return "0"
        
        # Parse based on section title and position
        if "PASSING" in section_title and position == "QB":
            passing_stats = {
                "completions": get_stat(['CMP', 'COMP']),
                "attempts": get_stat(['ATT']),
                "pct": get_stat(['PCT', 'CMP%']),
                "yards": get_stat(['YDS', 'YARD']),
                "avg": get_stat(['AVG', 'Y/A']),
                "tds": get_stat(['TD']),
                "ints": get_stat(['INT']),
                "sacks": get_stat(['SACK', 'SK']),
                "rating": get_stat(['RTG', 'RAT'])
            }
            stats_data["passing"] = passing_stats
            
        elif "RUSHING" in section_title and position in ["RB", "WR", "QB"]:
            rushing_stats = {
                "carries": get_stat(['CAR', 'ATT']),
                "yards": get_stat(['YDS', 'YARD']),
                "avg": get_stat(['AVG', 'Y/A']),
                "tds": get_stat(['TD']),
                "long": get_stat(['LNG', 'LONG']),
                "fumbles": get_stat(['FUM'])
            }
            stats_data["rushing"] = rushing_stats
            
        elif "RECEIVING" in section_title and position in ["RB", "WR", "TE", "QB"]:
            receiving_stats = {
                "receptions": get_stat(['REC']),
                "targets": get_stat(['TGTS', 'TGT']),
                "yards": get_stat(['YDS', 'YARD']),
                "avg": get_stat(['AVG', 'Y/R']),
                "tds": get_stat(['TD']),
                "long": get_stat(['LNG', 'LONG']),
                "fumbles": get_stat(['FUM'])
            }
            stats_data["receiving"] = receiving_stats
            
        elif "KICKING" in section_title and position == "K":
            # Handle the FG column that contains "made-attempted" format (e.g., "40-47")
            fg_combined = get_stat(['FG'])
            fgm, fga = "0", "0"
            if fg_combined and '-' in fg_combined:
                try:
                    fgm, fga = fg_combined.split('-')
                except ValueError:
                    pass  # Keep defaults of "0", "0"
            
            kicking_stats = {
                "fgm": fgm,
                "fga": fga,
                "fg_pct": get_stat(['FG%', 'PCT']),
                "long": get_stat(['LNG', 'LONG']),
                "xpm": get_stat(['XPM', 'PAT MADE']),
                "xpa": get_stat(['XPA', 'PAT ATT']),
                "points": get_stat(['PTS', 'POINTS'])
            }
            
            # Validation: warn if FG% > 0 but either FGM or FGA is 0
            fg_pct = kicking_stats['fg_pct']
            try:
                fg_pct_float = float(fg_pct)
                if fg_pct_float > 0 and (fgm == "0" or fga == "0"):
                    print(f"  ⚠️  WARNING: FG% is {fg_pct}% but FGM/FGA parsed as {fgm}/{fga} - possible parsing error!")
            except (ValueError, TypeError):
                pass  # Ignore if FG% is not a valid number
            
            stats_data["kicking"] = kicking_stats
    
    # Format consolidated stats string based on position
    if stats_data:
        if position == "QB" and "passing" in stats_data:
            p = stats_data["passing"]
            stats_data["stats_summary"] = f"{p['completions']}/{p['attempts']} {p['yards']}yds {p['tds']}TD {p['ints']}INT"
            
        elif position == "RB":
            summary_parts = []
            if "rushing" in stats_data:
                r = stats_data["rushing"]
                summary_parts.append(f"Rush: {r['carries']}att {r['yards']}yds {r['tds']}TD")
            if "receiving" in stats_data:
                rec = stats_data["receiving"]
                summary_parts.append(f"Rec: {rec['receptions']}rec {rec['yards']}yds {rec['tds']}TD")
            stats_data["stats_summary"] = " | ".join(summary_parts) if summary_parts else None
            
        elif position == "WR":
            summary_parts = []
            if "receiving" in stats_data:
                rec = stats_data["receiving"]
                summary_parts.append(f"Rec: {rec['receptions']}rec {rec['yards']}yds {rec['tds']}TD")
            if "rushing" in stats_data:
                r = stats_data["rushing"]
                summary_parts.append(f"Rush: {r['carries']}att {r['yards']}yds {r['tds']}TD")
            stats_data["stats_summary"] = " | ".join(summary_parts) if summary_parts else None
            
        elif position == "TE" and "receiving" in stats_data:
            rec = stats_data["receiving"]
            stats_data["stats_summary"] = f"{rec['receptions']}rec {rec['yards']}yds {rec['tds']}TD"
            
        elif position == "K" and "kicking" in stats_data:
            k = stats_data["kicking"]
            stats_data["stats_summary"] = f"{k['fgm']}/{k['fga']}FG {k['xpm']}/{k['xpa']}XP {k['points']}pts"
    
    return stats_data if stats_data else None


def fetch_team_bye_weeks() -> Dict[str, int]:
    """Fetch bye weeks for all NFL teams."""
    # 2025 NFL bye weeks
    bye_weeks = {
        "ARI": 8,   # Week 8
        "ATL": 5,   # Week 5
        "BAL": 7,   # Week 7
        "BUF": 7,   # Week 7
        "CAR": 14,  # Week 14
        "CHI": 5,   # Week 5
        "CIN": 10,  # Week 10
        "CLE": 9,   # Week 9
        "DAL": 10,  # Week 10
        "DEN": 12,  # Week 12
        "DET": 8,   # Week 8
        "GB": 5,    # Week 5
        "HOU": 6,   # Week 6
        "IND": 11,  # Week 11
        "JAX": 8,   # Week 8
        "KC": 10,   # Week 10
        "LAC": 12,  # Week 12
        "LAR": 8,   # Week 8
        "LV": 8,    # Week 8
        "MIA": 12,  # Week 12
        "MIN": 6,   # Week 6
        "NE": 14,   # Week 14
        "NO": 11,   # Week 11
        "NYG": 14,  # Week 14
        "NYJ": 9,   # Week 9
        "PHI": 9,   # Week 9
        "PIT": 5,   # Week 5
        "SEA": 8,   # Week 8
        "SF": 14,   # Week 14
        "TB": 9,    # Week 9
        "TEN": 10,  # Week 10
        "WAS": 12   # Week 12
    }
    
    return bye_weeks


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Fetch player stats from ESPN')
    parser.add_argument('--limit', type=int, help='Limit number of players to fetch (for testing)')
    parser.add_argument('--skip-stats', action='store_true', help='Skip fetching individual stats')
    args = parser.parse_args()
    
    # Load existing players
    players_path = Path(__file__).parent.parent / 'data' / 'players.json'
    if not players_path.exists():
        print(f"Error: {players_path} not found. Run fetch_espn_players.py first.")
        return
    
    with open(players_path) as f:
        players = json.load(f)
    
    print(f"Loaded {len(players)} players from players.json")
    
    # Get bye weeks for all teams
    print("\nFetching team bye weeks...")
    bye_weeks = fetch_team_bye_weeks()
    print(f"Got bye weeks for {len(bye_weeks)} teams")
    
    # Prepare stats data
    player_stats = {}
    
    # Apply limit if specified
    if args.limit:
        players = players[:args.limit]
        print(f"Limited to first {args.limit} players for testing")
    
    # Process each player
    for i, player in enumerate(players, 1):
        player_id = player['id']
        player_name = f"{player['first_name']} {player['last_name']}"
        team = player['team']
        position = player['position']
        
        print(f"\n[{i}/{len(players)}] Processing {player_name} ({position}, {team})...")
        
        # Add bye week from team
        bye_week = bye_weeks.get(team)
        
        stats_entry = {
            "bye_week": bye_week,
            "position": position,
            "team": team
        }
        
        # Fetch individual stats if not skipped
        if not args.skip_stats:
            player_page_stats = fetch_player_stats(player_id, player_name, position)
            if player_page_stats:
                # Add all the detailed stats
                if "passing" in player_page_stats:
                    stats_entry["passing"] = player_page_stats["passing"]
                if "rushing" in player_page_stats:
                    stats_entry["rushing"] = player_page_stats["rushing"]
                if "receiving" in player_page_stats:
                    stats_entry["receiving"] = player_page_stats["receiving"]
                if "kicking" in player_page_stats:
                    stats_entry["kicking"] = player_page_stats["kicking"]
                if "stats_summary" in player_page_stats:
                    stats_entry["stats_summary"] = player_page_stats["stats_summary"]
                
                print(f"  Found 2024 stats: {player_page_stats.get('stats_summary', 'N/A')}")
            else:
                # No 2024 stats found - leave empty
                stats_entry["stats_summary"] = None
                print(f"  No 2024 stats found")
            
            # Be polite to ESPN servers
            if i < len(players):
                time.sleep(0.5)
        
        player_stats[str(player_id)] = stats_entry
    
    # Write to player_stats.json
    output_path = Path(__file__).parent.parent / 'data' / 'player_stats.json'
    with open(output_path, 'w') as f:
        json.dump(player_stats, f, indent=2)
    
    print(f"\n\nSuccessfully wrote stats for {len(player_stats)} players to {output_path}")
    
    # Print summary
    teams_with_bye = len(set(s['bye_week'] for s in player_stats.values() if s['bye_week']))
    players_with_stats = len([s for s in player_stats.values() if s.get('last_year_stats')])
    
    print(f"\nSummary:")
    print(f"  Players with bye weeks: {teams_with_bye}")
    print(f"  Players with stats: {players_with_stats}")


if __name__ == "__main__":
    main()