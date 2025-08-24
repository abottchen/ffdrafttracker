#!/usr/bin/env python
"""
Generate a static HTML draft recap page for GitHub Pages.

This script fetches draft data from the running API server and creates
a beautiful static HTML page with all team rosters, prices, and stats.
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

import requests
from requests.exceptions import ConnectionError, RequestException

API_BASE = "http://localhost:8175/api/v1"
YEAR = datetime.now().year

def fetch_api_data(endpoint: str) -> dict:
    """Fetch data from API endpoint."""
    try:
        response = requests.get(f"{API_BASE}{endpoint}")
        response.raise_for_status()
        return response.json()
    except ConnectionError:
        print(f"\nERROR: Cannot connect to API server at {API_BASE}")
        print("\nPlease start the API server first:")
        print("  python main.py")
        print("\nThen run this script again.")
        sys.exit(1)
    except RequestException as e:
        print(f"\nERROR: Failed to fetch data from {API_BASE}{endpoint}")
        print(f"Request error: {e}")
        sys.exit(1)

def download_image(url: str, output_path: Path) -> bool:
    """Download an image from URL to local path."""
    if output_path.exists():
        return True  # Skip if already downloaded
    try:
        response = requests.get(url, stream=True, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'wb') as f:
            shutil.copyfileobj(response.raw, f)
        print(f"  Downloaded: {output_path.name}")
        return True
    except Exception as e:
        print(f"  Failed to download {url}: {e}")
        return False

def download_all_team_logos(assets_dir: Path) -> dict[str, str]:
    """Download all NFL team logos and return mapping to local paths."""
    logos_dir = assets_dir / "logos"
    logos_dir.mkdir(parents=True, exist_ok=True)

    team_mappings = {
        'ARI': 'https://a.espncdn.com/i/teamlogos/nfl/500/ari.png',
        'ATL': 'https://a.espncdn.com/i/teamlogos/nfl/500/atl.png',
        'BAL': 'https://a.espncdn.com/i/teamlogos/nfl/500/bal.png',
        'BUF': 'https://a.espncdn.com/i/teamlogos/nfl/500/buf.png',
        'CAR': 'https://a.espncdn.com/i/teamlogos/nfl/500/car.png',
        'CHI': 'https://a.espncdn.com/i/teamlogos/nfl/500/chi.png',
        'CIN': 'https://a.espncdn.com/i/teamlogos/nfl/500/cin.png',
        'CLE': 'https://a.espncdn.com/i/teamlogos/nfl/500/cle.png',
        'DAL': 'https://a.espncdn.com/i/teamlogos/nfl/500/dal.png',
        'DEN': 'https://a.espncdn.com/i/teamlogos/nfl/500/den.png',
        'DET': 'https://a.espncdn.com/i/teamlogos/nfl/500/det.png',
        'GB': 'https://a.espncdn.com/i/teamlogos/nfl/500/gb.png',
        'HOU': 'https://a.espncdn.com/i/teamlogos/nfl/500/hou.png',
        'IND': 'https://a.espncdn.com/i/teamlogos/nfl/500/ind.png',
        'JAX': 'https://a.espncdn.com/i/teamlogos/nfl/500/jax.png',
        'KC': 'https://a.espncdn.com/i/teamlogos/nfl/500/kc.png',
        'LV': 'https://a.espncdn.com/i/teamlogos/nfl/500/lv.png',
        'LAC': 'https://a.espncdn.com/i/teamlogos/nfl/500/lac.png',
        'LAR': 'https://a.espncdn.com/i/teamlogos/nfl/500/lar.png',
        'MIA': 'https://a.espncdn.com/i/teamlogos/nfl/500/mia.png',
        'MIN': 'https://a.espncdn.com/i/teamlogos/nfl/500/min.png',
        'NE': 'https://a.espncdn.com/i/teamlogos/nfl/500/ne.png',
        'NO': 'https://a.espncdn.com/i/teamlogos/nfl/500/no.png',
        'NYG': 'https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png',
        'NYJ': 'https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png',
        'PHI': 'https://a.espncdn.com/i/teamlogos/nfl/500/phi.png',
        'PIT': 'https://a.espncdn.com/i/teamlogos/nfl/500/pit.png',
        'SF': 'https://a.espncdn.com/i/teamlogos/nfl/500/sf.png',
        'SEA': 'https://a.espncdn.com/i/teamlogos/nfl/500/sea.png',
        'TB': 'https://a.espncdn.com/i/teamlogos/nfl/500/tb.png',
        'TEN': 'https://a.espncdn.com/i/teamlogos/nfl/500/ten.png',
        'WAS': 'https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png'
    }

    local_mappings = {}
    print("Downloading NFL team logos...")

    for team_abbr, url in team_mappings.items():
        filename = f"{team_abbr.lower()}.png"
        local_path = logos_dir / filename
        if download_image(url, local_path):
            # Return relative path from the HTML file location
            local_mappings[team_abbr] = f"{YEAR}/assets/logos/{filename}"

    return local_mappings

def get_team_logo_url(team_abbr: str) -> str:
    """Get ESPN CDN URL for NFL team logo."""
    team_mappings = {
        'ARI': 'https://a.espncdn.com/i/teamlogos/nfl/500/ari.png',
        'ATL': 'https://a.espncdn.com/i/teamlogos/nfl/500/atl.png',
        'BAL': 'https://a.espncdn.com/i/teamlogos/nfl/500/bal.png',
        'BUF': 'https://a.espncdn.com/i/teamlogos/nfl/500/buf.png',
        'CAR': 'https://a.espncdn.com/i/teamlogos/nfl/500/car.png',
        'CHI': 'https://a.espncdn.com/i/teamlogos/nfl/500/chi.png',
        'CIN': 'https://a.espncdn.com/i/teamlogos/nfl/500/cin.png',
        'CLE': 'https://a.espncdn.com/i/teamlogos/nfl/500/cle.png',
        'DAL': 'https://a.espncdn.com/i/teamlogos/nfl/500/dal.png',
        'DEN': 'https://a.espncdn.com/i/teamlogos/nfl/500/den.png',
        'DET': 'https://a.espncdn.com/i/teamlogos/nfl/500/det.png',
        'GB': 'https://a.espncdn.com/i/teamlogos/nfl/500/gb.png',
        'HOU': 'https://a.espncdn.com/i/teamlogos/nfl/500/hou.png',
        'IND': 'https://a.espncdn.com/i/teamlogos/nfl/500/ind.png',
        'JAX': 'https://a.espncdn.com/i/teamlogos/nfl/500/jax.png',
        'KC': 'https://a.espncdn.com/i/teamlogos/nfl/500/kc.png',
        'LV': 'https://a.espncdn.com/i/teamlogos/nfl/500/lv.png',
        'LAC': 'https://a.espncdn.com/i/teamlogos/nfl/500/lac.png',
        'LAR': 'https://a.espncdn.com/i/teamlogos/nfl/500/lar.png',
        'MIA': 'https://a.espncdn.com/i/teamlogos/nfl/500/mia.png',
        'MIN': 'https://a.espncdn.com/i/teamlogos/nfl/500/min.png',
        'NE': 'https://a.espncdn.com/i/teamlogos/nfl/500/ne.png',
        'NO': 'https://a.espncdn.com/i/teamlogos/nfl/500/no.png',
        'NYG': 'https://a.espncdn.com/i/teamlogos/nfl/500/nyg.png',
        'NYJ': 'https://a.espncdn.com/i/teamlogos/nfl/500/nyj.png',
        'PHI': 'https://a.espncdn.com/i/teamlogos/nfl/500/phi.png',
        'PIT': 'https://a.espncdn.com/i/teamlogos/nfl/500/pit.png',
        'SF': 'https://a.espncdn.com/i/teamlogos/nfl/500/sf.png',
        'SEA': 'https://a.espncdn.com/i/teamlogos/nfl/500/sea.png',
        'TB': 'https://a.espncdn.com/i/teamlogos/nfl/500/tb.png',
        'TEN': 'https://a.espncdn.com/i/teamlogos/nfl/500/ten.png',
        'WAS': 'https://a.espncdn.com/i/teamlogos/nfl/500/wsh.png'
    }
    return team_mappings.get(team_abbr, f"https://a.espncdn.com/i/teamlogos/nfl/500/{team_abbr.lower()}.png")

def get_player_image_url(player_name: str) -> str:
    """Get ESPN CDN URL for player headshot."""
    # ESPN player image URLs need player IDs which we don't have
    # So we'll use a placeholder or generate initials
    return None

def get_position_color(position: str) -> str:
    """Get color for position badge - matches draft UI colors."""
    colors = {
        'QB': '#7b6bb5',  # Bright purple
        'RB': '#5fb572',  # Bright green
        'WR': '#b5a55f',  # Bright gold
        'TE': '#b5725f',  # Bright orange
        'K': '#5f82b5',   # Bright blue
        'DST': '#9f5f75', # Bright burgundy
        'D/ST': '#9f5f75' # Bright burgundy (alternate format)
    }
    return colors.get(position, '#666')

def generate_html(
    draft_state: dict,
    owners: list[dict],
    players: list[dict],
    config: dict,
    player_stats: dict,
    logo_mappings: dict[str, str]
) -> str:
    """Generate the HTML page with local assets."""

    # Create lookup dictionaries
    owners_by_id = {o['id']: o for o in owners}
    players_by_id = {p['id']: p for p in players}

    # Build team data
    teams_data = []
    for team in draft_state['teams']:
        owner = owners_by_id.get(team['owner_id'], {})
        team_players = []
        total_spent = 0
        position_counts = {}

        for pick in team['picks']:
            player = players_by_id.get(pick['player_id'], {})
            position = player.get('position', 'Unknown')
            position_counts[position] = position_counts.get(position, 0) + 1
            total_spent += pick['price']

            # Get player stats if available
            stats = player_stats.get(str(pick['player_id']), {})
            stats_summary = stats.get('stats_summary', '')

            team_players.append({
                'player': player,
                'pick': pick,
                'stats': stats_summary
            })

        # Sort players by pick_id (order they were drafted)
        team_players.sort(key=lambda x: x['pick']['pick_id'])

        teams_data.append({
            'owner': owner,
            'team': team,
            'players': team_players,
            'total_spent': total_spent,
            'position_counts': position_counts
        })

    # Sort teams by owner name
    teams_data.sort(key=lambda x: x['owner'].get('owner_name', ''))

    # Calculate draft summary stats before HTML generation
    total_money = sum(team['total_spent'] for team in teams_data)
    total_players = sum(len(team['players']) for team in teams_data)
    avg_price = total_money / total_players if total_players > 0 else 0

    # Calculate additional interesting stats
    all_picks = []
    nfl_team_counts = {}
    position_stats = {}

    for team_data in teams_data:
        owner = team_data['owner']
        for player_data in team_data['players']:
            player = player_data['player']
            pick = player_data['pick']

            pick_info = {
                'owner_name': owner.get('owner_name', 'Unknown'),
                'team_name': owner.get('team_name', 'Unknown'),
                'player_name': f"{player.get('first_name', '')} "
                              f"{player.get('last_name', '')}".strip(),
                'position': player.get('position', 'Unknown'),
                'nfl_team': player.get('team', ''),
                'price': pick['price']
            }
            all_picks.append(pick_info)

            # Track NFL team counts per owner
            owner_key = owner.get('owner_name', 'Unknown')
            nfl_team = player.get('team', '')
            if nfl_team:
                if owner_key not in nfl_team_counts:
                    nfl_team_counts[owner_key] = {}
                nfl_team_counts[owner_key][nfl_team] = (
                    nfl_team_counts[owner_key].get(nfl_team, 0) + 1
                )

            # Track position stats
            position = player.get('position', 'Unknown')
            if position not in position_stats:
                position_stats[position] = []
            position_stats[position].append(pick['price'])

    # Find highest paid player at each position
    highest_by_position = {}
    for position, prices in position_stats.items():
        max_price = max(prices)
        highest_pick = next(pick for pick in all_picks if pick['position'] == position and pick['price'] == max_price)
        highest_by_position[position] = {
            'player': highest_pick['player_name'],
            'price': max_price,
            'owner': highest_pick['team_name']
        }

    # Calculate average price per position
    avg_by_position = {}
    for position, prices in position_stats.items():
        avg_by_position[position] = sum(prices) / len(prices) if prices else 0

    # Find owner with highest priced player
    highest_pick = max(all_picks, key=lambda x: x['price'])

    # Find owner with most players from same NFL team - handle ties
    max_same_team = 0
    team_loyalty_ties = []

    for owner_name, teams in nfl_team_counts.items():
        for nfl_team, count in teams.items():
            if count > max_same_team:
                max_same_team = count
                team_loyalty_ties = [(owner_name, nfl_team, count)]
            elif count == max_same_team and max_same_team > 0:
                team_loyalty_ties.append((owner_name, nfl_team, count))

    # Most expensive picks overall - handle ties
    if all_picks:
        max_price = max(pick['price'] for pick in all_picks)
        most_expensive_picks = [pick for pick in all_picks if pick['price'] == max_price]
    else:
        most_expensive_picks = []

    # Calculate bargains based on fantasy value vs price
    def calculate_fantasy_points(player_id, stats):
        """Calculate approximate fantasy points from player stats"""
        if not stats:
            return 0

        points = 0
        # Stats are at the root level, not in stats_summary
        stats_data = stats

        if not stats_data:
            return 0

        try:
            # Passing stats (QB)
            if 'passing' in stats_data:
                passing = stats_data['passing']
                if isinstance(passing, dict):
                    yards = int(passing.get('yards', '0').replace(',', ''))
                    tds = int(passing.get('tds', '0'))
                    ints = int(passing.get('ints', '0'))
                    points += yards * 0.04 + tds * 4 - ints * 2

            # Rushing stats
            if 'rushing' in stats_data:
                rushing = stats_data['rushing']
                if isinstance(rushing, dict):
                    yards = int(rushing.get('yards', '0').replace(',', ''))
                    tds = int(rushing.get('tds', '0'))
                    points += yards * 0.1 + tds * 6

            # Receiving stats
            if 'receiving' in stats_data:
                receiving = stats_data['receiving']
                if isinstance(receiving, dict):
                    receptions = int(receiving.get('receptions', '0'))
                    yards = int(receiving.get('yards', '0').replace(',', ''))
                    tds = int(receiving.get('tds', '0'))
                    points += receptions * 0.5 + yards * 0.1 + tds * 6

            # Kicking stats
            if 'kicking' in stats_data:
                kicking = stats_data['kicking']
                if isinstance(kicking, dict):
                    fg_made = int(kicking.get('fg_made', '0'))
                    xp_made = int(kicking.get('xp_made', '0'))
                    points += fg_made * 3 + xp_made * 1

            # Defense stats
            if 'defense' in stats_data:
                defense = stats_data['defense']
                if isinstance(defense, dict):
                    sacks = float(defense.get('sacks', '0'))
                    ints = int(defense.get('ints', '0'))
                    fumbles = int(defense.get('fumble_recoveries', '0'))
                    tds = int(defense.get('tds', '0'))
                    points += sacks * 1 + ints * 2 + fumbles * 2 + tds * 6

        except (ValueError, TypeError, KeyError):
            pass

        return max(0, points)

    # Calculate value picks (fantasy points per dollar)
    bargain_picks = []

    for pick in all_picks:
        if pick['price'] > 0:  # Only consider picks that cost money
            player_id = str(next((p['id'] for p in players if f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() == pick['player_name']), 0))
            player_stats_data = player_stats.get(player_id, {})
            fantasy_points = calculate_fantasy_points(player_id, player_stats_data)

            if fantasy_points > 0:  # Only include players who have actual stats (excludes rookies/no data)
                value_ratio = fantasy_points / pick['price']
                bargain_picks.append({
                    **pick,
                    'fantasy_points': fantasy_points,
                    'value_ratio': value_ratio
                })

    print(f"  Found {len(bargain_picks)} players with stats for value analysis")

    # Find best bargain (highest fantasy points per dollar)
    best_bargain = max(bargain_picks, key=lambda x: x['value_ratio']) if bargain_picks else None

    # Find biggest bounce-back bet (lowest fantasy points per dollar, but only for expensive picks with stats)
    expensive_picks = [pick for pick in bargain_picks if pick['price'] >= 15]  # Only picks $15+ to avoid cheap flyers
    bounce_back_pick = min(expensive_picks, key=lambda x: x['value_ratio']) if expensive_picks else None

    if best_bargain:
        print(f"  Best bargain: {best_bargain['player_name']} - {best_bargain['fantasy_points']:.1f} pts for ${best_bargain['price']} ({best_bargain['value_ratio']:.2f} pts/$)")
    if bounce_back_pick:
        print(f"  Bounce-back bet: {bounce_back_pick['player_name']} - {bounce_back_pick['fantasy_points']:.1f} pts for ${bounce_back_pick['price']} ({bounce_back_pick['value_ratio']:.2f} pts/$)")

    # Still keep cheapest pick as backup
    cheapest_picks = [pick for pick in all_picks if pick['price'] > 0]
    cheapest = min(cheapest_picks, key=lambda x: x['price']) if cheapest_picks else None

    # Owner with most expensive average per player - handle ties
    owner_averages = {}
    for team_data in teams_data:
        owner_name = team_data['owner'].get('team_name', 'Unknown')
        if team_data['players']:
            owner_averages[owner_name] = team_data['total_spent'] / len(team_data['players'])

    if owner_averages:
        max_avg = max(owner_averages.values())
        biggest_spenders = [(name, avg) for name, avg in owner_averages.items() if avg == max_avg]
    else:
        biggest_spenders = []

    # Most popular NFL team (most players drafted from) - handle ties
    all_nfl_teams = {}
    for pick in all_picks:
        if pick['nfl_team']:
            all_nfl_teams[pick['nfl_team']] = all_nfl_teams.get(pick['nfl_team'], 0) + 1

    if all_nfl_teams:
        max_count = max(all_nfl_teams.values())
        [(team, count) for team, count in all_nfl_teams.items() if count == max_count]
    else:
        pass

    # Position with highest total spending - handle ties
    position_totals = {}
    for position, prices in position_stats.items():
        position_totals[position] = sum(prices)

    if position_totals:
        max_total = max(position_totals.values())
        biggest_position_spends = [(pos, total) for pos, total in position_totals.items() if total == max_total]
    else:
        biggest_position_spends = []

    # Bargain hunter (owner who spent least on average) - handle ties
    if owner_averages:
        min_avg = min(owner_averages.values())
        bargain_hunters = [(name, avg) for name, avg in owner_averages.items() if avg == min_avg]
    else:
        bargain_hunters = []

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="darkreader-lock" />
    <title>{YEAR} Fantasy Football Draft Recap</title>
    <style>
        :root {{
            /* Light theme (default) */
            --bg-gradient-start: #667eea;
            --bg-gradient-end: #764ba2;
            --card-bg: rgba(255, 255, 255, 0.95);
            --text-primary: #333;
            --text-secondary: #666;
            --text-muted: #999;
            --border-color: #f0f0f0;
            --hover-bg: #f8f9fa;
            --alt-bg: #e9ecef;
            --header-gradient-start: #667eea;
            --header-gradient-end: #764ba2;
            --bar-gradient-start: #667eea;
            --bar-gradient-end: #764ba2;
            --summary-value-gradient-start: #667eea;
            --summary-value-gradient-end: #764ba2;
            --tab-active-gradient-start: #667eea;
            --tab-active-gradient-end: #764ba2;
        }}

        [data-theme="dark"] {{
            /* Dark theme */
            --bg-gradient-start: #1a1a2e;
            --bg-gradient-end: #16213e;
            --card-bg: rgba(30, 30, 45, 0.95);
            --text-primary: #f0f0f0;
            --text-secondary: #b0b0b0;
            --text-muted: #808080;
            --border-color: #404050;
            --hover-bg: #2a2a3e;
            --alt-bg: #252538;
            --header-gradient-start: #4a5568;
            --header-gradient-end: #2d3748;
            --bar-gradient-start: #60a5fa;
            --bar-gradient-end: #3b82f6;
            --summary-value-gradient-start: #60a5fa;
            --summary-value-gradient-end: #f59e0b;
            --tab-active-gradient-start: #60a5fa;
            --tab-active-gradient-end: #3b82f6;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, var(--bg-gradient-start) 0%, var(--bg-gradient-end) 100%);
            min-height: 100vh;
            padding: 20px;
            transition: background 0.3s ease;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        .header {{
            background: var(--card-bg);
            border-radius: 20px;
            padding: 30px;
            text-align: center;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
            position: relative;
        }}

        .header h1 {{
            font-size: 3em;
            background: linear-gradient(135deg, var(--header-gradient-start) 0%, var(--header-gradient-end) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }}

        .header p {{
            color: var(--text-secondary);
            font-size: 1.2em;
        }}

        .theme-toggle {{
            position: absolute;
            top: 20px;
            right: 20px;
            background: transparent;
            border: 2px solid var(--text-secondary);
            border-radius: 20px;
            padding: 8px 15px;
            cursor: pointer;
            font-size: 1.2em;
            transition: all 0.3s ease;
        }}

        .theme-toggle:hover {{
            background: var(--text-secondary);
            color: var(--card-bg);
        }}

        .layout-controls {{
            text-align: center;
            margin: 20px 0;
        }}

        .layout-toggle {{
            background: var(--card-bg);
            border: 2px solid var(--text-secondary);
            border-radius: 8px;
            padding: 10px 20px;
            cursor: pointer;
            font-size: 1em;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: var(--text-primary);
        }}

        .layout-toggle:hover {{
            background: var(--text-secondary);
            color: var(--card-bg);
        }}

        .layout-icon {{
            font-size: 1.2em;
        }}

        .teams-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}

        .teams-grid.list-layout {{
            display: flex;
            flex-direction: column;
            max-width: 800px;
            margin: 0 auto 30px;
        }}

        .team-card {{
            background: var(--card-bg);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }}

        .team-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);
        }}

        .team-header {{
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 15px;
            margin-bottom: 20px;
        }}

        .team-name {{
            font-size: 1.5em;
            font-weight: bold;
            color: var(--text-primary);
            margin-bottom: 5px;
        }}

        .owner-name {{
            color: var(--text-secondary);
            font-size: 1.1em;
        }}

        .team-stats {{
            display: flex;
            justify-content: space-between;
            margin: 10px 0;
            padding: 10px;
            background: var(--hover-bg);
            border-radius: 8px;
        }}

        .stat-item {{
            text-align: center;
        }}

        .stat-value {{
            font-size: 1.3em;
            font-weight: bold;
            color: var(--text-primary);
        }}

        .stat-label {{
            font-size: 0.9em;
            color: var(--text-secondary);
            margin-top: 2px;
        }}

        .position-badges {{
            display: flex;
            flex-wrap: wrap;
            justify-content: space-between;
            gap: 5px;
            margin: 15px 0;
        }}

        .position-badge {{
            padding: 4px 8px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: bold;
            color: white;
        }}

        .player-list {{
            margin-top: 20px;
        }}

        .player-item {{
            display: grid;
            grid-template-columns: 30px 1fr 45px 60px;
            align-items: center;
            gap: 10px;
            padding: 10px;
            margin: 5px 0;
            background: var(--hover-bg);
            border-radius: 8px;
            transition: background 0.2s ease;
        }}

        .player-item:hover {{
            background: var(--alt-bg);
        }}

        .team-logo {{
            width: 30px;
            height: 30px;
            object-fit: contain;
        }}

        .player-name {{
            font-weight: bold;
            color: var(--text-primary);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .player-position {{
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.75em;
            font-weight: bold;
            color: white;
            text-align: center;
            white-space: nowrap;
            justify-self: center;
        }}


        .player-price {{
            font-weight: bold;
            color: var(--text-primary);
            font-size: 1.1em;
            text-align: right;
        }}

        .draft-summary {{
            background: var(--card-bg);
            border-radius: 15px;
            padding: 30px;
            margin-top: 30px;
            text-align: center;
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            min-height: 800px;
            display: flex;
            flex-direction: column;
        }}

        .draft-summary h2 {{
            margin-bottom: 20px;
            color: var(--text-primary);
        }}

        .summary-stats {{
            display: flex;
            justify-content: center;
            gap: 40px;
            flex-wrap: wrap;
        }}

        .summary-stat {{
            text-align: center;
        }}

        .summary-value {{
            font-size: 2em;
            font-weight: bold;
            background: linear-gradient(135deg, var(--header-gradient-start) 0%, var(--header-gradient-end) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .summary-label {{
            color: var(--text-secondary);
            margin-top: 5px;
        }}

        .summary-context {{
            font-size: 0.85em;
            color: var(--text-muted);
            margin-top: 3px;
        }}

        /* Tab Interface Styles */
        .summary-tabs {{
            display: flex;
            background: var(--hover-bg);
            border-radius: 12px;
            padding: 6px;
            margin-bottom: 30px;
            border: 1px solid var(--border-color);
        }}

        .tab-btn {{
            flex: 1;
            padding: 12px 20px;
            border: none;
            background: transparent;
            border-radius: 8px;
            font-size: 1em;
            font-weight: 600;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }}

        .tab-btn:hover {{
            background: var(--alt-bg);
            color: var(--text-primary);
        }}

        .tab-btn.active {{
            background: linear-gradient(135deg, var(--tab-active-gradient-start), var(--tab-active-gradient-end));
            color: white;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
        }}

        .tab-content {{
            display: none;
            flex: 1;
            overflow-y: auto;
        }}

        .tab-content.active {{
            display: flex;
            flex-direction: column;
            animation: fadeIn 0.3s ease-in-out;
        }}

        @keyframes fadeIn {{
            from {{ opacity: 0; transform: translateY(10px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

        /* Enhanced Summary Stats */
        .summary-stats {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 0;
        }}

        .summary-stat {{
            background: var(--card-bg);
            border: 2px solid var(--border-color);
            border-radius: 15px;
            padding: 25px 20px;
            text-align: center;
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }}

        .summary-stat::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: linear-gradient(90deg, var(--header-gradient-start), var(--header-gradient-end));
        }}

        .summary-stat:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
            border-color: var(--header-gradient-start);
        }}

        .summary-value {{
            font-size: 2.5em;
            font-weight: 900;
            background: linear-gradient(135deg, var(--summary-value-gradient-start), var(--summary-value-gradient-end));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
            line-height: 1;
        }}

        .fun-facts {{
            margin-top: 40px;
        }}

        .fun-facts h3 {{
            text-align: center;
            color: var(--text-primary);
            margin-bottom: 20px;
        }}

        .facts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            flex: 1;
            align-content: start;
        }}

        .fact-item {{
            background: var(--card-bg);
            border-left: 4px solid;
            border-radius: 8px;
            padding: 16px 20px;
            transition: all 0.3s ease;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        }}

        .fact-item:hover {{
            transform: translateX(4px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }}

        .fact-item.money {{ border-color: #10b981; }}
        .fact-item.value {{ border-color: #f59e0b; }}
        .fact-item.bounce {{ border-color: #8b5cf6; }}
        .fact-item.spender {{ border-color: #ef4444; }}
        .fact-item.bargain {{ border-color: #3b82f6; }}
        .fact-item.loyalty {{ border-color: #ec4899; }}
        .fact-item.popular {{ border-color: #14b8a6; }}
        .fact-item.position {{ border-color: #84cc16; }}

        .fact-content h4 {{
            font-size: 0.9em;
            margin: 0 0 6px 0;
            color: var(--text-secondary);
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .fact-details {{
            color: var(--text-primary);
            line-height: 1.5;
            font-size: 1.05em;
        }}

        .fact-highlight {{
            color: var(--text-primary);
            font-weight: 700;
        }}

        .position-breakdown-section {{
            margin-top: 30px;
        }}

        .position-breakdown-section h3 {{
            text-align: center;
            color: var(--text-primary);
            margin-bottom: 20px;
        }}

        .position-stats {{
            display: flex;
            flex-direction: column;
            gap: 15px;
            flex: 1;
        }}

        .position-stat {{
            display: grid;
            grid-template-columns: 80px 1fr auto;
            gap: 20px;
            align-items: center;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            transition: all 0.3s ease;
        }}

        .position-stat:hover {{
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            border-color: var(--header-gradient-start);
        }}

        .position-badge {{
            border-radius: 8px;
            padding: 12px 8px;
            font-weight: bold;
            text-align: center;
            font-size: 1em;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }}

        .position-info {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}

        .position-detail {{
            color: var(--text-primary);
            line-height: 1.4;
        }}

        .position-price-display {{
            font-size: 1.5em;
            font-weight: bold;
            color: var(--text-primary);
            text-align: right;
        }}

        /* Chart Layout Styles */
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 30px;
            padding: 20px;
        }}

        .chart-container {{
            background: var(--card-bg);
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        }}

        .chart-container.full-width {{
            grid-column: 1 / -1;
        }}

        .chart-container h3 {{
            text-align: center;
            color: var(--text-primary);
            margin-bottom: 8px;
            font-size: 1.1em;
        }}

        .chart-subtitle {{
            text-align: center;
            color: var(--text-secondary);
            margin-bottom: 20px;
            font-size: 0.85em;
        }}

        .bar-chart {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            max-width: 800px;
            margin: 0 auto;
        }}

        .bar-item {{
            display: grid;
            grid-template-columns: 60px 1fr 40px;
            gap: 12px;
            align-items: center;
        }}

        .bar-label {{
            font-weight: 600;
            color: var(--text-primary);
            text-align: right;
            font-size: 0.9em;
        }}

        .bar-container {{
            background: var(--hover-bg);
            border-radius: 4px;
            height: 28px;
            position: relative;
            overflow: hidden;
        }}

        .bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--bar-gradient-start), var(--bar-gradient-end));
            border-radius: 4px;
            transition: width 0.6s ease;
            display: flex;
            align-items: center;
            padding-left: 8px;
        }}

        .bar-value {{
            color: var(--text-primary);
            font-weight: 600;
            font-size: 0.9em;
        }}

        /* Scatter Plot Styles */
        .scatter-plot {{
            position: relative;
            height: 400px;
            margin: 20px 0;
        }}

        .scatter-canvas {{
            width: 100%;
            height: 100%;
            border: 1px solid var(--border-color);
            border-radius: 8px;
        }}

        /* Heatmap Styles */
        .heatmap {{
            display: grid;
            gap: 2px;
            margin: 20px 0;
            border-radius: 8px;
            overflow: hidden;
        }}

        .heatmap-row {{
            display: grid;
            gap: 2px;
        }}

        .heatmap-cell {{
            padding: 8px 4px;
            text-align: center;
            font-size: 0.8em;
            font-weight: 600;
            border-radius: 3px;
            min-height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .heatmap-header {{
            background: var(--header-gradient-start);
            color: white;
            font-weight: 700;
        }}

        .heatmap-label {{
            background: var(--alt-bg);
            color: var(--text-primary);
            font-weight: 700;
            text-align: right;
            padding-right: 8px;
        }}

        /* Stacked Bar Chart Styles */
        .stacked-bar-chart {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin: 20px 0;
        }}

        .stacked-bar-item {{
            display: grid;
            grid-template-columns: 150px 1fr 80px;
            gap: 12px;
            align-items: center;
            margin-bottom: 4px;
        }}

        .stacked-bar-label {{
            font-weight: 600;
            color: var(--text-primary);
            text-align: right;
            font-size: 0.9em;
        }}

        .stacked-bar-container {{
            height: 24px;
            border-radius: 4px;
            overflow: hidden;
            display: flex;
            border: 1px solid var(--border-color);
        }}

        .stacked-bar-segment {{
            height: 100%;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75em;
            font-weight: 600;
            color: white;
            text-shadow: 0 1px 2px rgba(0,0,0,0.5);
        }}

        .stacked-bar-total {{
            font-weight: 600;
            color: var(--text-primary);
            font-size: 0.9em;
            text-align: center;
        }}

        .stacked-legend {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            justify-content: center;
            margin: 20px 0 10px 0;
            padding: 15px;
            background: var(--hover-bg);
            border-radius: 8px;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 0.85em;
        }}

        .legend-color {{
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }}

        @media (max-width: 768px) {{
            .teams-grid {{
                grid-template-columns: 1fr;
            }}

            .header h1 {{
                font-size: 2em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <button class="theme-toggle" id="themeToggle" aria-label="Toggle theme">🌙</button>
            <h1>{YEAR} Fantasy Football Draft Recap</h1>
            <p>Auction Draft Results</p>
        </div>

        <div class="draft-summary">
            <h2>Draft Summary & Analysis</h2>

            <!-- Tab Navigation -->
            <div class="summary-tabs">
                <button class="tab-btn active" data-tab="overview">Overview</button>
                <button class="tab-btn" data-tab="highlights">Highlights</button>
                <button class="tab-btn" data-tab="market">Market Analysis</button>
                <button class="tab-btn" data-tab="teams">Team Strategy</button>
                <button class="tab-btn" data-tab="value">Value Analysis</button>
            </div>

            <!-- Overview Tab -->
            <div class="tab-content active" id="overview">
                <div class="summary-stats">
                    <div class="summary-stat">
                        <div class="summary-value">{len(teams_data)}</div>
                        <div class="summary-label">Teams</div>
                        <div class="summary-context">{len(teams_data)} teams competing</div>
                    </div>
                    <div class="summary-stat">
                        <div class="summary-value">{total_players}</div>
                        <div class="summary-label">Players Drafted</div>
                        <div class="summary-context">From available player pool</div>
                    </div>
                    <div class="summary-stat">
                        <div class="summary-value">${total_money:,}</div>
                        <div class="summary-label">Total Spent</div>
                        <div class="summary-context">Across all teams</div>
                    </div>
                    <div class="summary-stat">
                        <div class="summary-value">${avg_price:.1f}</div>
                        <div class="summary-label">Average Price</div>
                        <div class="summary-context">Per player drafted</div>
                    </div>
                </div>
            </div>

            <!-- Draft Highlights Tab -->
            <div class="tab-content" id="highlights">
                <div class="facts-grid">
                    <div class="fact-item money">
                        <div class="fact-content">
                            <h4>Most Expensive Pick{' (tie)' if len(most_expensive_picks) > 1 else ''}</h4>
                            <div class="fact-details">
                                {f'<span class="fact-highlight">{", ".join([p["player_name"] for p in most_expensive_picks])}</span> (${most_expensive_picks[0]["price"]})<br>' if len(most_expensive_picks) <= 3 else f'{len(most_expensive_picks)} players tied at <span class="fact-highlight">${most_expensive_picks[0]["price"]}</span><br>'}
                                <small>{'→ ' + ', '.join(list(set([p["team_name"] for p in most_expensive_picks]))) if len(set([p["team_name"] for p in most_expensive_picks])) == 1 else '→ ' + ', '.join([p["team_name"] for p in most_expensive_picks])}</small>
                            </div>
                        </div>
                    </div>
                    {f'''<div class="fact-item value">
                        <div class="fact-content">
                            <h4>Best Value Pick</h4>
                            <div class="fact-details">
                                <span class="fact-highlight">{best_bargain['player_name']}</span> ({best_bargain['fantasy_points']:.1f} pts, ${best_bargain['price']}) to {best_bargain['team_name']}<br>
                                <small>{best_bargain['value_ratio']:.2f} pts/$</small>
                            </div>
                        </div>
                    </div>''' if best_bargain else f'''<div class="fact-item value">
                        <div class="fact-content">
                            <h4>Cheapest Pick</h4>
                            <div class="fact-details">
                                <span class="fact-highlight">{cheapest['player_name']}</span> (${cheapest['price']}) to {cheapest['team_name']}
                            </div>
                        </div>
                    </div>''' if cheapest else ''}
                    {f'''<div class="fact-item bounce">
                        <div class="fact-content">
                            <h4>Bounce-Back Bet</h4>
                            <div class="fact-details">
                                <span class="fact-highlight">{bounce_back_pick['player_name']}</span> ({bounce_back_pick['fantasy_points']:.1f} pts, ${bounce_back_pick['price']}) to {bounce_back_pick['team_name']}<br>
                                <small>{bounce_back_pick['value_ratio']:.2f} pts/$</small>
                            </div>
                        </div>
                    </div>''' if bounce_back_pick else ''}
                    {f'''<div class="fact-item spender">
                        <div class="fact-content">
                            <h4>Biggest Spender{' (tie)' if len(biggest_spenders) > 1 else ''}</h4>
                            <div class="fact-details">
                                {', '.join([f'<span class="fact-highlight">{name}</span>' for name, _ in biggest_spenders[:3]])} (${biggest_spenders[0][1]:.1f} per player avg)
                                {f'<br><small>and {len(biggest_spenders) - 3} more...</small>' if len(biggest_spenders) > 3 else ''}
                            </div>
                        </div>
                    </div>''' if biggest_spenders else ''}
                    {f'''<div class="fact-item bargain">
                        <div class="fact-content">
                            <h4>Bargain Hunter{' (tie)' if len(bargain_hunters) > 1 else ''}</h4>
                            <div class="fact-details">
                                {', '.join([f'<span class="fact-highlight">{name}</span>' for name, _ in bargain_hunters[:3]])} (${bargain_hunters[0][1]:.1f} per player avg)
                                {f'<br><small>and {len(bargain_hunters) - 3} more...</small>' if len(bargain_hunters) > 3 else ''}
                            </div>
                        </div>
                    </div>''' if bargain_hunters else ''}
                    {f'''<div class="fact-item loyalty">
                        <div class="fact-content">
                            <h4>Team Loyalty Award{' (tie)' if len(team_loyalty_ties) > 1 else ''}</h4>
                            <div class="fact-details">
                                {', '.join([f'<span class="fact-highlight">{owner}</span> ({count} {team} players)' for owner, team, count in team_loyalty_ties[:3]])}
                                {f'<br><small>and {len(team_loyalty_ties) - 3} more...</small>' if len(team_loyalty_ties) > 3 else ''}
                            </div>
                        </div>
                    </div>''' if team_loyalty_ties else ''}
                    {f'''<div class="fact-item position">
                        <div class="fact-content">
                            <h4>Biggest Position Investment{' (tie)' if len(biggest_position_spends) > 1 else ''}</h4>
                            <div class="fact-details">
                                {', '.join([f'<span class="fact-highlight">{pos}</span>' for pos, _ in biggest_position_spends[:3]])} (${biggest_position_spends[0][1]:,} total spent)
                                {f'<br><small>and {len(biggest_position_spends) - 3} more...</small>' if len(biggest_position_spends) > 3 else ''}
                            </div>
                        </div>
                    </div>''' if biggest_position_spends else ''}
                </div>
            </div>

            <!-- Market Analysis Tab -->
            <div class="tab-content" id="market">
                <div class="charts-grid">
                    <div class="chart-container">
                        <h3>Budget Distribution by Position</h3>
                        <p class="chart-subtitle">Total league spending per position</p>
                        <div class="bar-chart" id="positionBudgetChart"></div>
                    </div>
                    <div class="chart-container">
                        <h3>Average Price by Position</h3>
                        <p class="chart-subtitle">Mean auction price with min/max range</p>
                        <div class="bar-chart" id="positionAvgChart"></div>
                    </div>
                    <div class="chart-container">
                        <h3>Top 10 Most Expensive Players</h3>
                        <p class="chart-subtitle">Highest auction prices paid</p>
                        <div class="bar-chart" id="topPlayersChart"></div>
                    </div>
                    <div class="chart-container">
                        <h3>NFL Team Popularity</h3>
                        <p class="chart-subtitle">Number of players drafted from each team</p>
                        <div class="bar-chart" id="teamChart"></div>
                    </div>
                </div>
            </div>

            <!-- Team Strategy Tab -->
            <div class="tab-content" id="teams">
                <div class="charts-grid">
                    <div class="chart-container full-width">
                        <h3>Team Roster Construction (Heatmap)</h3>
                        <p class="chart-subtitle">Spending breakdown by position for each team</p>
                        <div class="heatmap" id="rosterHeatmap"></div>
                    </div>
                    <div class="chart-container full-width">
                        <h3>Team Roster Construction (Stacked Bars)</h3>
                        <p class="chart-subtitle">Visual comparison of roster spending strategies</p>
                        <div class="stacked-bar-chart" id="rosterStackedChart"></div>
                    </div>
                    <div class="chart-container full-width">
                        <h3>NFL Team Stacking Patterns</h3>
                        <p class="chart-subtitle">Which fantasy teams drafted players from each NFL team</p>
                        <div class="stacked-bar-chart" id="nflStackingChart"></div>
                    </div>
                </div>
            </div>

            <!-- Value Analysis Tab -->
            <div class="tab-content" id="value">
                <div class="charts-grid">
                    <div class="chart-container full-width">
                        <h3>Price vs Fantasy Performance</h3>
                        <p class="chart-subtitle">Auction price compared to previous year fantasy points</p>
                        <div class="scatter-plot" id="valueScatter"></div>
                    </div>
                </div>
            </div>
        </div>

        <div class="layout-controls">
            <button class="layout-toggle" id="layoutToggle" aria-label="Toggle layout">
                <span class="layout-icon">⊞</span>
                <span class="layout-text">Grid View</span>
            </button>
        </div>

        <div class="teams-grid" id="teamsGrid">
'''

    # Add each team card
    for team_data in teams_data:
        owner = team_data['owner']
        team = team_data['team']
        team_players = team_data['players']

        html += f'''
            <div class="team-card">
                <div class="team-header">
                    <div class="team-name">{owner.get('team_name', 'Unknown Team')}</div>
                    <div class="owner-name">{owner.get('owner_name', 'Unknown Owner')}</div>
                </div>

                <div class="team-stats">
                    <div class="stat-item">
                        <div class="stat-value">{len(team_players)}</div>
                        <div class="stat-label">Players</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${team_data['total_spent']}</div>
                        <div class="stat-label">Spent</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${team['budget_remaining']}</div>
                        <div class="stat-label">Remaining</div>
                    </div>
                </div>

                <div class="position-badges">'''

        # Add position badges in proper order
        position_order = ['QB', 'RB', 'WR', 'TE', 'K', 'DST', 'D/ST']
        sorted_positions = []
        for pos in position_order:
            if pos in team_data['position_counts']:
                sorted_positions.append((pos, team_data['position_counts'][pos]))
        # Add any positions not in the standard order
        for pos, count in team_data['position_counts'].items():
            if pos not in position_order:
                sorted_positions.append((pos, count))

        for position, count in sorted_positions:
            color = get_position_color(position)
            # Use dark text for light backgrounds (RB and WR)
            text_color = '#2a2a2a' if position in ['RB', 'WR', 'TE'] else 'white'
            html += f'''
                    <span class="position-badge" style="background: {color}; color: {text_color}">{position} ({count})</span>'''

        html += '''
                </div>

                <div class="player-list">'''

        # Add players
        for player_data in team_players:
            player = player_data['player']
            pick = player_data['pick']
            stats = player_data['stats']

            position = player.get('position', 'Unknown')
            team_abbr = player.get('team', '')

            # Get local team logo path
            logo_path = logo_mappings.get(team_abbr, '') if team_abbr else ''

            # Use dark text for light backgrounds (RB, WR, TE)
            position_text_color = '#2a2a2a' if position in ['RB', 'WR', 'TE'] else 'white'

            html += f'''
                    <div class="player-item">
                        {f'<img src="{logo_path}" class="team-logo" alt="{team_abbr}" onerror="this.style.display=\'none\'">' if logo_path else '<div class="team-logo"></div>'}
                        <span class="player-name">{player.get('first_name', '')} {player.get('last_name', '')}</span>
                        <span class="player-position" style="background: {get_position_color(position)}; color: {position_text_color}">{position}</span>
                        <span class="player-price">${pick['price']}</span>
                    </div>'''

        html += '''
                </div>
            </div>'''

    # Calculate draft summary stats
    total_money = sum(team['total_spent'] for team in teams_data)
    total_players = sum(len(team['players']) for team in teams_data)
    avg_price = total_money / total_players if total_players > 0 else 0

    # Calculate additional interesting stats
    all_picks = []
    nfl_team_counts = {}
    position_stats = {}

    for team_data in teams_data:
        owner = team_data['owner']
        for player_data in team_data['players']:
            player = player_data['player']
            pick = player_data['pick']

            pick_info = {
                'owner_name': owner.get('owner_name', 'Unknown'),
                'team_name': owner.get('team_name', 'Unknown'),
                'player_name': f"{player.get('first_name', '')} "
                              f"{player.get('last_name', '')}".strip(),
                'position': player.get('position', 'Unknown'),
                'nfl_team': player.get('team', ''),
                'price': pick['price']
            }
            all_picks.append(pick_info)

            # Track NFL team counts per owner
            owner_key = owner.get('owner_name', 'Unknown')
            nfl_team = player.get('team', '')
            if nfl_team:
                if owner_key not in nfl_team_counts:
                    nfl_team_counts[owner_key] = {}
                nfl_team_counts[owner_key][nfl_team] = (
                    nfl_team_counts[owner_key].get(nfl_team, 0) + 1
                )

            # Track position stats
            position = player.get('position', 'Unknown')
            if position not in position_stats:
                position_stats[position] = []
            position_stats[position].append(pick['price'])

    # Find highest paid player at each position
    highest_by_position = {}
    for position, prices in position_stats.items():
        max_price = max(prices)
        highest_pick = next(pick for pick in all_picks if pick['position'] == position and pick['price'] == max_price)
        highest_by_position[position] = {
            'player': highest_pick['player_name'],
            'price': max_price,
            'owner': highest_pick['team_name']
        }

    # Calculate average price per position
    avg_by_position = {}
    for position, prices in position_stats.items():
        avg_by_position[position] = sum(prices) / len(prices) if prices else 0

    # Find owner with highest priced player
    highest_pick = max(all_picks, key=lambda x: x['price'])

    # Find owner with most players from same NFL team - handle ties
    max_same_team = 0
    team_loyalty_ties = []

    for owner_name, teams in nfl_team_counts.items():
        for nfl_team, count in teams.items():
            if count > max_same_team:
                max_same_team = count
                team_loyalty_ties = [(owner_name, nfl_team, count)]
            elif count == max_same_team and max_same_team > 0:
                team_loyalty_ties.append((owner_name, nfl_team, count))

    # Most expensive picks overall - handle ties
    if all_picks:
        max_price = max(pick['price'] for pick in all_picks)
        most_expensive_picks = [pick for pick in all_picks if pick['price'] == max_price]
    else:
        most_expensive_picks = []

    # Calculate bargains based on fantasy value vs price
    def calculate_fantasy_points(player_id, stats):
        """Calculate approximate fantasy points from player stats"""
        if not stats:
            return 0

        points = 0
        # Stats are at the root level, not in stats_summary
        stats_data = stats

        if not stats_data:
            return 0

        try:
            # Passing stats (QB)
            if 'passing' in stats_data:
                passing = stats_data['passing']
                if isinstance(passing, dict):
                    yards = int(passing.get('yards', '0').replace(',', ''))
                    tds = int(passing.get('tds', '0'))
                    ints = int(passing.get('ints', '0'))
                    points += yards * 0.04 + tds * 4 - ints * 2

            # Rushing stats
            if 'rushing' in stats_data:
                rushing = stats_data['rushing']
                if isinstance(rushing, dict):
                    yards = int(rushing.get('yards', '0').replace(',', ''))
                    tds = int(rushing.get('tds', '0'))
                    points += yards * 0.1 + tds * 6

            # Receiving stats
            if 'receiving' in stats_data:
                receiving = stats_data['receiving']
                if isinstance(receiving, dict):
                    receptions = int(receiving.get('receptions', '0'))
                    yards = int(receiving.get('yards', '0').replace(',', ''))
                    tds = int(receiving.get('tds', '0'))
                    points += receptions * 0.5 + yards * 0.1 + tds * 6

            # Kicking stats
            if 'kicking' in stats_data:
                kicking = stats_data['kicking']
                if isinstance(kicking, dict):
                    fg_made = int(kicking.get('fg_made', '0'))
                    xp_made = int(kicking.get('xp_made', '0'))
                    points += fg_made * 3 + xp_made * 1

            # Defense stats
            if 'defense' in stats_data:
                defense = stats_data['defense']
                if isinstance(defense, dict):
                    sacks = float(defense.get('sacks', '0'))
                    ints = int(defense.get('ints', '0'))
                    fumbles = int(defense.get('fumble_recoveries', '0'))
                    tds = int(defense.get('tds', '0'))
                    points += sacks * 1 + ints * 2 + fumbles * 2 + tds * 6

        except (ValueError, TypeError, KeyError):
            pass

        return max(0, points)

    # Calculate value picks (fantasy points per dollar)
    bargain_picks = []

    for pick in all_picks:
        if pick['price'] > 0:  # Only consider picks that cost money
            player_id = str(next((p['id'] for p in players if f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() == pick['player_name']), 0))
            player_stats_data = player_stats.get(player_id, {})
            fantasy_points = calculate_fantasy_points(player_id, player_stats_data)

            if fantasy_points > 0:  # Only include players who have actual stats (excludes rookies/no data)
                value_ratio = fantasy_points / pick['price']
                bargain_picks.append({
                    **pick,
                    'fantasy_points': fantasy_points,
                    'value_ratio': value_ratio
                })

    print(f"  Found {len(bargain_picks)} players with stats for value analysis")

    # Find best bargain (highest fantasy points per dollar)
    best_bargain = max(bargain_picks, key=lambda x: x['value_ratio']) if bargain_picks else None

    # Find biggest bounce-back bet (lowest fantasy points per dollar, but only for expensive picks with stats)
    expensive_picks = [pick for pick in bargain_picks if pick['price'] >= 15]  # Only picks $15+ to avoid cheap flyers
    bounce_back_pick = min(expensive_picks, key=lambda x: x['value_ratio']) if expensive_picks else None

    if best_bargain:
        print(f"  Best bargain: {best_bargain['player_name']} - {best_bargain['fantasy_points']:.1f} pts for ${best_bargain['price']} ({best_bargain['value_ratio']:.2f} pts/$)")
    if bounce_back_pick:
        print(f"  Bounce-back bet: {bounce_back_pick['player_name']} - {bounce_back_pick['fantasy_points']:.1f} pts for ${bounce_back_pick['price']} ({bounce_back_pick['value_ratio']:.2f} pts/$)")

    # Still keep cheapest pick as backup
    cheapest_picks = [pick for pick in all_picks if pick['price'] > 0]
    cheapest = min(cheapest_picks, key=lambda x: x['price']) if cheapest_picks else None

    # Owner with most expensive average per player - handle ties
    owner_averages = {}
    for team_data in teams_data:
        owner_name = team_data['owner'].get('team_name', 'Unknown')
        if team_data['players']:
            owner_averages[owner_name] = team_data['total_spent'] / len(team_data['players'])

    if owner_averages:
        max_avg = max(owner_averages.values())
        biggest_spenders = [(name, avg) for name, avg in owner_averages.items() if avg == max_avg]
    else:
        biggest_spenders = []

    # Most popular NFL team (most players drafted from) - handle ties
    all_nfl_teams = {}
    for pick in all_picks:
        if pick['nfl_team']:
            all_nfl_teams[pick['nfl_team']] = all_nfl_teams.get(pick['nfl_team'], 0) + 1

    if all_nfl_teams:
        max_count = max(all_nfl_teams.values())
        [(team, count) for team, count in all_nfl_teams.items() if count == max_count]
    else:
        pass

    # Position with highest total spending - handle ties
    position_totals = {}
    for position, prices in position_stats.items():
        position_totals[position] = sum(prices)

    if position_totals:
        max_total = max(position_totals.values())
        biggest_position_spends = [(pos, total) for pos, total in position_totals.items() if total == max_total]
    else:
        biggest_position_spends = []

    # Bargain hunter (owner who spent least on average) - handle ties
    if owner_averages:
        min_avg = min(owner_averages.values())
        bargain_hunters = [(name, avg) for name, avg in owner_averages.items() if avg == min_avg]
    else:
        bargain_hunters = []

    # Prepare chart data

    # Position budget data
    position_budgets = [(pos, total) for pos, total in position_totals.items()]
    position_budgets.sort(key=lambda x: x[1], reverse=True)

    # Position averages with min/max
    position_ranges = []
    for position, prices in position_stats.items():
        if prices:
            position_ranges.append({
                'position': position,
                'avg': sum(prices) / len(prices),
                'min': min(prices),
                'max': max(prices),
                'color': get_position_color(position)
            })
    position_ranges.sort(key=lambda x: x['avg'], reverse=True)

    # Top 10 expensive players
    top_expensive_players = sorted(all_picks, key=lambda x: x['price'], reverse=True)[:10]

    # Team budget remaining
    team_budgets = [(team_data['owner'].get('team_name', 'Unknown'), team_data['team']['budget_remaining'])
                   for team_data in teams_data]
    team_budgets.sort(key=lambda x: x[1], reverse=True)

    # Roster construction heatmap data
    roster_matrix = {}
    position_order = ['QB', 'RB', 'WR', 'TE', 'K', 'DST']
    for team_data in teams_data:
        team_name = team_data['owner'].get('team_name', 'Unknown')
        roster_matrix[team_name] = {}
        for pos in position_order:
            # Handle both DST and D/ST variations
            if pos == 'DST':
                pos_spending = sum(pick['price'] for player_data in team_data['players']
                                 for pick in [player_data['pick']]
                                 if player_data['player'].get('position') in ['DST', 'D/ST'])
            else:
                pos_spending = sum(pick['price'] for player_data in team_data['players']
                                 for pick in [player_data['pick']]
                                 if player_data['player'].get('position') == pos)
            roster_matrix[team_name][pos] = pos_spending

    # NFL Team Stacking data - which fantasy teams drafted from each NFL team
    nfl_stacking_data = {}
    for pick in all_picks:
        nfl_team = pick['nfl_team']
        fantasy_team = pick['team_name']
        if nfl_team and fantasy_team:
            if nfl_team not in nfl_stacking_data:
                nfl_stacking_data[nfl_team] = {}
            if fantasy_team not in nfl_stacking_data[nfl_team]:
                nfl_stacking_data[nfl_team][fantasy_team] = 0
            nfl_stacking_data[nfl_team][fantasy_team] += 1

    # Only include NFL teams with at least 3 total players drafted
    nfl_stacking_filtered = {nfl_team: teams for nfl_team, teams in nfl_stacking_data.items()
                           if sum(teams.values()) >= 3}

    # Sort by total players drafted
    nfl_stacking_sorted = dict(sorted(nfl_stacking_filtered.items(),
                                    key=lambda x: sum(x[1].values()), reverse=True))

    # Value scatter plot data (price vs fantasy points)
    value_scatter_data = []
    for pick in all_picks:
        player_id = str(next((p['id'] for p in players if f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() == pick['player_name']), 0))
        player_stats_data = player_stats.get(player_id, {})
        fantasy_points = calculate_fantasy_points(player_id, player_stats_data)
        if fantasy_points > 0 and pick['price'] > 0:
            # Get position for coloring
            position = next((p.get('position', 'Unknown') for p in players if f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() == pick['player_name']), 'Unknown')
            value_scatter_data.append({
                'name': pick['player_name'],
                'price': pick['price'],
                'points': fantasy_points,
                'position': position,
                'team': pick['team_name']
            })

    # Generate JavaScript data
    team_data_json = json.dumps(sorted(all_nfl_teams.items(), key=lambda x: x[1], reverse=True)[:10]) if all_nfl_teams else '[]'
    position_budget_json = json.dumps(position_budgets)
    position_ranges_json = json.dumps(position_ranges)
    top_players_json = json.dumps(top_expensive_players)
    team_budgets_json = json.dumps(team_budgets)
    roster_matrix_json = json.dumps(roster_matrix)
    nfl_stacking_json = json.dumps(nfl_stacking_sorted)
    value_scatter_json = json.dumps(value_scatter_data)

    # Close the HTML structure and add JavaScript
    html += '''
        </div>
    </div>

    <script>
        // Theme toggle functionality
        const themeToggle = document.getElementById('themeToggle');
        const html = document.documentElement;

        // Check for saved theme preference or default to light
        const currentTheme = localStorage.getItem('theme') || 'light';
        html.setAttribute('data-theme', currentTheme);
        updateToggleButton(currentTheme);

        // Toggle theme on button click
        themeToggle.addEventListener('click', () => {
            const theme = html.getAttribute('data-theme');
            const newTheme = theme === 'light' ? 'dark' : 'light';

            html.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateToggleButton(newTheme);
        });

        function updateToggleButton(theme) {
            themeToggle.textContent = theme === 'light' ? '🌙' : '☀️';
            themeToggle.setAttribute('aria-label',
                theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode');
        }

        // Layout toggle functionality
        const layoutToggle = document.getElementById('layoutToggle');
        const teamsGrid = document.getElementById('teamsGrid');

        // Check for saved layout preference or default to grid
        const currentLayout = localStorage.getItem('layout') || 'grid';
        if (currentLayout === 'list') {
            teamsGrid.classList.add('list-layout');
            updateLayoutButton('list');
        }

        // Toggle layout on button click
        layoutToggle.addEventListener('click', () => {
            const isListLayout = teamsGrid.classList.contains('list-layout');
            const newLayout = isListLayout ? 'grid' : 'list';

            if (newLayout === 'list') {
                teamsGrid.classList.add('list-layout');
            } else {
                teamsGrid.classList.remove('list-layout');
            }

            localStorage.setItem('layout', newLayout);
            updateLayoutButton(newLayout);
        });

        function updateLayoutButton(layout) {
            const icon = layoutToggle.querySelector('.layout-icon');
            const text = layoutToggle.querySelector('.layout-text');

            if (layout === 'grid') {
                icon.textContent = '⊞';
                text.textContent = 'Grid View';
                layoutToggle.setAttribute('aria-label', 'Switch to list view');
            } else {
                icon.textContent = '☰';
                text.textContent = 'List View';
                layoutToggle.setAttribute('aria-label', 'Switch to grid view');
            }
        }

        // Tab functionality for draft summary
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                // Remove active class from all tabs and content
                document.querySelectorAll('.tab-btn, .tab-content').forEach(el =>
                    el.classList.remove('active'));

                // Add active class to clicked tab and corresponding content
                btn.classList.add('active');
                document.getElementById(btn.dataset.tab).classList.add('active');

                // Initialize charts when tabs are opened
                if (btn.dataset.tab === 'market') {
                    initializeMarketCharts();
                } else if (btn.dataset.tab === 'teams') {
                    initializeTeamCharts();
                } else if (btn.dataset.tab === 'value') {
                    initializeValueCharts();
                }
            });
        });

        // Chart data
        const teamData = ''' + team_data_json + ''';
        const positionBudgetData = ''' + position_budget_json + ''';
        const positionRangeData = ''' + position_ranges_json + ''';
        const topPlayersData = ''' + top_players_json + ''';
        const teamBudgetData = ''' + team_budgets_json + ''';
        const rosterMatrixData = ''' + roster_matrix_json + ''';
        const nflStackingData = ''' + nfl_stacking_json + ''';
        const valueScatterData = ''' + value_scatter_json + ''';

        function createBarChart(containerId, data, labelKey, valueKey, title) {
            const container = document.getElementById(containerId);
            if (container.children.length > 0) return;

            const maxValue = data.length > 0 ? Math.max(...data.map(item => typeof item === 'object' ? item[valueKey] : item[1])) : 0;

            data.forEach((item, index) => {
                const label = typeof item === 'object' ? item[labelKey] : item[0];
                const value = typeof item === 'object' ? item[valueKey] : item[1];
                const percentage = maxValue > 0 ? (value / maxValue) * 100 : 0;

                const barItem = document.createElement('div');
                barItem.className = 'bar-item';

                const barHtml = '<div class="bar-label">' + label + '</div>' +
                    '<div class="bar-container">' +
                    '<div class="bar-fill" style="width: 0%"></div>' +
                    '</div>' +
                    '<div class="bar-value">' + (typeof value === 'number' && value > 100 ? '$' + value.toLocaleString() : value) + '</div>';

                barItem.innerHTML = barHtml;
                container.appendChild(barItem);

                setTimeout(() => {
                    barItem.querySelector('.bar-fill').style.width = percentage + '%';
                }, 100 + index * 50);
            });
        }

        function initializeMarketCharts() {
            createBarChart('positionBudgetChart', positionBudgetData, 0, 1, 'Position Budget');
            createBarChart('topPlayersChart', topPlayersData.map(p => [p.player_name, p.price]), 0, 1, 'Top Players');
            createBarChart('teamChart', teamData, 0, 1, 'NFL Teams');
            initializePositionRangeChart();
        }

        function initializeTeamCharts() {
            initializeRosterHeatmap();
            initializeRosterStackedChart();
            initializeNFLStackingChart();
        }

        function initializeValueCharts() {
            initializeScatterPlot();
        }

        function initializePositionRangeChart() {
            const container = document.getElementById('positionAvgChart');
            if (container.children.length > 0) return;

            const maxValue = Math.max(...positionRangeData.map(p => p.max));

            positionRangeData.forEach((item, index) => {
                const percentage = maxValue > 0 ? (item.avg / maxValue) * 100 : 0;

                const barItem = document.createElement('div');
                barItem.className = 'bar-item';

                const barHtml = '<div class="bar-label">' + item.position + '</div>' +
                    '<div class="bar-container">' +
                    '<div class="bar-fill" style="width: 0%; background: ' + item.color + '"></div>' +
                    '</div>' +
                    '<div class="bar-value">$' + Math.round(item.avg) + '</div>';

                barItem.innerHTML = barHtml;
                container.appendChild(barItem);

                setTimeout(() => {
                    barItem.querySelector('.bar-fill').style.width = percentage + '%';
                }, 100 + index * 50);
            });
        }

        function initializeRosterHeatmap() {
            const container = document.getElementById('rosterHeatmap');
            if (container.children.length > 0) return;

            const positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DST'];
            const teams = Object.keys(rosterMatrixData);
            const maxSpending = Math.max(...teams.flatMap(team => positions.map(pos => rosterMatrixData[team][pos] || 0)));

            // Create header row
            const headerRow = document.createElement('div');
            headerRow.className = 'heatmap-row';
            headerRow.style.gridTemplateColumns = '150px repeat(' + positions.length + ', 1fr)';

            headerRow.innerHTML = '<div class="heatmap-cell heatmap-header">Team</div>' +
                positions.map(pos => '<div class="heatmap-cell heatmap-header">' + pos + '</div>').join('');
            container.appendChild(headerRow);

            // Create team rows
            teams.forEach(team => {
                const row = document.createElement('div');
                row.className = 'heatmap-row';
                row.style.gridTemplateColumns = '150px repeat(' + positions.length + ', 1fr)';

                let rowHtml = '<div class="heatmap-cell heatmap-label">' + team + '</div>';
                positions.forEach(pos => {
                    const spending = rosterMatrixData[team][pos] || 0;
                    const intensity = maxSpending > 0 ? spending / maxSpending : 0;
                    const color = 'rgba(102, 126, 234, ' + intensity + ')';
                    rowHtml += '<div class="heatmap-cell" style="background: ' + color + '; color: ' + (intensity > 0.5 ? 'white' : 'var(--text-primary)') + '">$' + spending + '</div>';
                });

                row.innerHTML = rowHtml;
                container.appendChild(row);
            });
        }

        function initializeRosterStackedChart() {
            const container = document.getElementById('rosterStackedChart');
            if (container.children.length > 0) return;

            const positions = ['QB', 'RB', 'WR', 'TE', 'K', 'DST'];
            const positionColors = {
                'QB': '#7b6bb5', 'RB': '#5fb572', 'WR': '#b5a55f',
                'TE': '#b5725f', 'K': '#5f82b5', 'DST': '#9f5f75'
            };

            // Create legend
            const legend = document.createElement('div');
            legend.className = 'stacked-legend';
            positions.forEach(pos => {
                const legendItem = document.createElement('div');
                legendItem.className = 'legend-item';
                legendItem.innerHTML = `
                    <div class="legend-color" style="background: ${positionColors[pos]}"></div>
                    <span>${pos}</span>
                `;
                legend.appendChild(legendItem);
            });
            container.appendChild(legend);

            const teams = Object.keys(rosterMatrixData);
            teams.forEach(teamName => {
                const teamData = rosterMatrixData[teamName];
                const totalSpending = positions.reduce((sum, pos) => sum + (teamData[pos] || 0), 0);

                if (totalSpending === 0) return;

                const barItem = document.createElement('div');
                barItem.className = 'stacked-bar-item';

                const label = document.createElement('div');
                label.className = 'stacked-bar-label';
                label.textContent = teamName;

                const barContainer = document.createElement('div');
                barContainer.className = 'stacked-bar-container';

                const total = document.createElement('div');
                total.className = 'stacked-bar-total';
                total.textContent = '$' + totalSpending;

                positions.forEach(pos => {
                    const spending = teamData[pos] || 0;
                    if (spending > 0) {
                        const percentage = (spending / totalSpending) * 100;
                        const segment = document.createElement('div');
                        segment.className = 'stacked-bar-segment';
                        segment.style.width = percentage + '%';
                        segment.style.background = positionColors[pos];

                        // Only show text if segment is wide enough
                        if (percentage > 8) {
                            segment.textContent = '$' + spending;
                        }

                        // Add tooltip
                        segment.title = `${pos}: $${spending} (${percentage.toFixed(1)}%)`;

                        barContainer.appendChild(segment);
                    }
                });

                barItem.appendChild(label);
                barItem.appendChild(barContainer);
                barItem.appendChild(total);
                container.appendChild(barItem);
            });
        }

        function initializeNFLStackingChart() {
            const container = document.getElementById('nflStackingChart');
            if (container.children.length > 0) return;

            // Generate colors for fantasy teams
            const fantasyTeams = new Set();
            Object.values(nflStackingData).forEach(teams => {
                Object.keys(teams).forEach(team => fantasyTeams.add(team));
            });

            const teamColors = {};
            const colors = ['#7b6bb5', '#5fb572', '#b5a55f', '#b5725f', '#5f82b5', '#9f5f75', '#8b7355', '#6b8bb5', '#75b55f', '#b58b5f'];
            Array.from(fantasyTeams).forEach((team, i) => {
                teamColors[team] = colors[i % colors.length];
            });

            // Create legend
            const legend = document.createElement('div');
            legend.className = 'stacked-legend';
            Array.from(fantasyTeams).forEach(team => {
                const legendItem = document.createElement('div');
                legendItem.className = 'legend-item';
                legendItem.innerHTML = `
                    <div class="legend-color" style="background: ${teamColors[team]}"></div>
                    <span>${team}</span>
                `;
                legend.appendChild(legendItem);
            });
            container.appendChild(legend);

            Object.entries(nflStackingData).forEach(([nflTeam, fantasyTeamCounts]) => {
                const totalPlayers = Object.values(fantasyTeamCounts).reduce((sum, count) => sum + count, 0);

                const barItem = document.createElement('div');
                barItem.className = 'stacked-bar-item';

                const label = document.createElement('div');
                label.className = 'stacked-bar-label';
                label.textContent = nflTeam;

                const barContainer = document.createElement('div');
                barContainer.className = 'stacked-bar-container';

                const total = document.createElement('div');
                total.className = 'stacked-bar-total';
                total.textContent = totalPlayers + ' players';

                Object.entries(fantasyTeamCounts).forEach(([fantasyTeam, count]) => {
                    const percentage = (count / totalPlayers) * 100;
                    const segment = document.createElement('div');
                    segment.className = 'stacked-bar-segment';
                    segment.style.width = percentage + '%';
                    segment.style.background = teamColors[fantasyTeam];

                    // Only show count if segment is wide enough
                    if (percentage > 15) {
                        segment.textContent = count;
                    }

                    // Add tooltip
                    segment.title = `${fantasyTeam}: ${count} players (${percentage.toFixed(1)}%)`;

                    barContainer.appendChild(segment);
                });

                barItem.appendChild(label);
                barItem.appendChild(barContainer);
                barItem.appendChild(total);
                container.appendChild(barItem);
            });
        }

        function initializeScatterPlot() {
            const container = document.getElementById('valueScatter');
            if (container.children.length > 0) return;

            // Create SVG instead of canvas for better interactivity
            const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            svg.setAttribute('width', '100%');
            svg.setAttribute('height', '500');
            svg.style.border = '1px solid var(--border-color)';
            svg.style.borderRadius = '8px';
            svg.style.background = 'var(--card-bg)';

            const width = 1200;
            const height = 500;
            const padding = 60;
            const plotWidth = width - 2 * padding;
            const plotHeight = height - 2 * padding;

            svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
            container.appendChild(svg);

            const maxPrice = Math.max(...valueScatterData.map(d => d.price));
            const maxPoints = Math.max(...valueScatterData.map(d => d.points));

            // Position colors
            const positionColors = {
                'QB': '#7b6bb5', 'RB': '#5fb572', 'WR': '#b5a55f',
                'TE': '#b5725f', 'K': '#5f82b5'
            };

            // Create tooltip element
            const tooltip = document.createElement('div');
            tooltip.style.position = 'absolute';
            tooltip.style.background = 'rgba(0, 0, 0, 0.8)';
            tooltip.style.color = 'white';
            tooltip.style.padding = '8px 12px';
            tooltip.style.borderRadius = '4px';
            tooltip.style.fontSize = '12px';
            tooltip.style.pointerEvents = 'none';
            tooltip.style.opacity = '0';
            tooltip.style.transition = 'opacity 0.2s';
            tooltip.style.zIndex = '1000';
            document.body.appendChild(tooltip);

            // Draw axes
            const axisGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            axisGroup.setAttribute('stroke', 'rgba(100, 100, 100, 0.3)');
            axisGroup.setAttribute('stroke-width', '2');

            // Y axis
            const yAxis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            yAxis.setAttribute('x1', padding);
            yAxis.setAttribute('y1', padding);
            yAxis.setAttribute('x2', padding);
            yAxis.setAttribute('y2', height - padding);
            axisGroup.appendChild(yAxis);

            // X axis
            const xAxis = document.createElementNS('http://www.w3.org/2000/svg', 'line');
            xAxis.setAttribute('x1', padding);
            xAxis.setAttribute('y1', height - padding);
            xAxis.setAttribute('x2', width - padding);
            xAxis.setAttribute('y2', height - padding);
            axisGroup.appendChild(xAxis);

            svg.appendChild(axisGroup);

            // Add axis labels
            const xLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            xLabel.setAttribute('x', width / 2);
            xLabel.setAttribute('y', height - 10);
            xLabel.setAttribute('text-anchor', 'middle');
            xLabel.setAttribute('font-size', '14');
            xLabel.setAttribute('fill', 'var(--text-primary)');
            xLabel.textContent = 'Auction Price ($)';
            svg.appendChild(xLabel);

            const yLabel = document.createElementNS('http://www.w3.org/2000/svg', 'text');
            yLabel.setAttribute('x', 20);
            yLabel.setAttribute('y', height / 2);
            yLabel.setAttribute('text-anchor', 'middle');
            yLabel.setAttribute('font-size', '14');
            yLabel.setAttribute('fill', 'var(--text-primary)');
            yLabel.setAttribute('transform', `rotate(-90, 20, ${height / 2})`);
            yLabel.textContent = 'Fantasy Points';
            svg.appendChild(yLabel);

            // Draw points
            valueScatterData.forEach(point => {
                const x = padding + (point.price / maxPrice) * plotWidth;
                const y = height - padding - (point.points / maxPoints) * plotHeight;

                const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                circle.setAttribute('cx', x);
                circle.setAttribute('cy', y);
                circle.setAttribute('r', 6);
                circle.setAttribute('fill', positionColors[point.position] || '#666');
                circle.style.cursor = 'pointer';
                circle.style.transition = 'r 0.2s';

                // Add hover effects and tooltip
                circle.addEventListener('mouseenter', (e) => {
                    circle.setAttribute('r', 8);
                    tooltip.innerHTML = `
                        <strong>${point.name}</strong><br>
                        Position: ${point.position}<br>
                        Price: $${point.price}<br>
                        Fantasy Points: ${point.points.toFixed(1)}<br>
                        Team: ${point.team}
                    `;
                    tooltip.style.opacity = '1';
                });

                circle.addEventListener('mousemove', (e) => {
                    tooltip.style.left = (e.pageX + 10) + 'px';
                    tooltip.style.top = (e.pageY - 10) + 'px';
                });

                circle.addEventListener('mouseleave', () => {
                    circle.setAttribute('r', 6);
                    tooltip.style.opacity = '0';
                });

                svg.appendChild(circle);
            });

            // Add position legend
            const legend = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            legend.setAttribute('transform', `translate(${width - 120}, 30)`);

            const positions = Object.keys(positionColors);
            positions.forEach((pos, i) => {
                const legendItem = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                legendItem.setAttribute('transform', `translate(0, ${i * 20})`);

                const legendCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
                legendCircle.setAttribute('cx', 6);
                legendCircle.setAttribute('cy', 6);
                legendCircle.setAttribute('r', 4);
                legendCircle.setAttribute('fill', positionColors[pos]);
                legendItem.appendChild(legendCircle);

                const legendText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                legendText.setAttribute('x', 16);
                legendText.setAttribute('y', 10);
                legendText.setAttribute('font-size', '12');
                legendText.setAttribute('fill', 'var(--text-primary)');
                legendText.textContent = pos;
                legendItem.appendChild(legendText);

                legend.appendChild(legendItem);
            });

            svg.appendChild(legend);
        }
    </script>
</body>
</html>'''

    return html

def main():
    """Main function to generate draft recap."""
    print(f"Generating {YEAR} Draft Recap...")

    # Create output directory and assets directory
    output_dir = Path(f"docs/{YEAR}")
    output_dir.mkdir(parents=True, exist_ok=True)
    assets_dir = output_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Download team logos
    logo_mappings = download_all_team_logos(assets_dir)

    # Fetch all data from API
    print("Fetching data from API...")
    draft_state = fetch_api_data("/draft-state")
    owners = fetch_api_data("/owners")
    players = fetch_api_data("/players")
    config = fetch_api_data("/config")

    print(f"  Loaded {len(players)} players from API")
    if players:
        print(f"  Sample player: {players[0]}")
        first_name = players[0].get('first_name', '')
        last_name = players[0].get('last_name', '')
        print(f"  Sample player name: '{first_name} {last_name}'")

    # Load player stats if available
    player_stats = {}
    stats_file = Path("data/player_stats.json")
    if stats_file.exists():
        with open(stats_file) as f:
            player_stats = json.load(f)

    # Generate HTML
    print("Generating HTML page...")
    html_content = generate_html(
        draft_state, owners, players, config, player_stats, logo_mappings
    )

    # Save HTML file
    output_file = Path(f"docs/{YEAR}_draft_recap.html")
    output_file.write_text(html_content, encoding='utf-8')

    print("Draft recap generated successfully!")
    print(f"Output: {output_file}")
    print(f"View at: https://[your-github-username].github.io/ffdrafttracker/{YEAR}_draft_recap.html")

if __name__ == "__main__":
    main()
