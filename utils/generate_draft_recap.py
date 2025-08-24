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

# NFL team abbreviation to ESPN CDN logo URL mapping
NFL_TEAM_LOGO_URLS = {
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
    'WAS': 'https://a.espncdn.com/i/teamlogos/nfl/500/was.png',
}

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

    # Use the global constant instead of duplicating the mapping
    team_mappings = NFL_TEAM_LOGO_URLS

    local_mappings = {}
    print("Downloading NFL team logos...")

    for team_abbr, url in team_mappings.items():
        filename = f"{team_abbr.lower()}.png"
        local_path = logos_dir / filename
        if download_image(url, local_path):
            # Return relative path from the HTML file location
            local_mappings[team_abbr] = f"{YEAR}/assets/logos/{filename}"

    return local_mappings

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

def load_template(filename: str) -> str:
    """Load template file from templates directory."""
    template_path = Path(__file__).parent / "templates" / filename
    return template_path.read_text(encoding='utf-8')


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
        highest_pick = next(
            pick for pick in all_picks
            if pick['position'] == position and pick['price'] == max_price
        )
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
        most_expensive_picks = [
            pick for pick in all_picks if pick['price'] == max_price
        ]
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
            player_id = str(next(
                (p['id'] for p in players
                 if f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
                 == pick['player_name']),
                0
            ))
            player_stats_data = player_stats.get(player_id, {})
            fantasy_points = calculate_fantasy_points(player_id, player_stats_data)

            # Only include players who have actual stats
            if fantasy_points > 0:
                value_ratio = fantasy_points / pick['price']
                bargain_picks.append({
                    **pick,
                    'fantasy_points': round(fantasy_points, 1),
                    'value_ratio': round(value_ratio, 2)
                })

    print(f"  Found {len(bargain_picks)} players with stats for value analysis")

    # Find best bargain (highest fantasy points per dollar)
    best_bargain = (
        max(bargain_picks, key=lambda x: x['value_ratio'])
        if bargain_picks else None
    )

    # Find biggest bounce-back bet (lowest points per dollar, expensive picks)
    expensive_picks = [
        pick for pick in bargain_picks if pick['price'] >= 15
    ]  # Only $15+ picks
    bounce_back_pick = (
        min(expensive_picks, key=lambda x: x['value_ratio'])
        if expensive_picks else None
    )

    if best_bargain:
        print(
            f"  Best bargain: {best_bargain['player_name']} - "
            f"{best_bargain['fantasy_points']:.1f} pts for "
            f"${best_bargain['price']} ({best_bargain['value_ratio']:.2f} pts/$)"
        )
    if bounce_back_pick:
        print(
            f"  Bounce-back bet: {bounce_back_pick['player_name']} - "
            f"{bounce_back_pick['fantasy_points']:.1f} pts for "
            f"${bounce_back_pick['price']} "
            f"({bounce_back_pick['value_ratio']:.2f} pts/$)"
        )

    # Still keep cheapest pick as backup
    cheapest_picks = [pick for pick in all_picks if pick['price'] > 0]
    cheapest = min(cheapest_picks, key=lambda x: x['price']) if cheapest_picks else None

    # Owner with most expensive average per player - handle ties
    owner_averages = {}
    for team_data in teams_data:
        owner_name = team_data['owner'].get('team_name', 'Unknown')
        if team_data['players']:
            owner_averages[owner_name] = (
                team_data['total_spent'] / len(team_data['players'])
            )

    if owner_averages:
        max_avg = max(owner_averages.values())
        biggest_spenders = [
            (name, avg) for name, avg in owner_averages.items()
            if avg == max_avg
        ]
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
        biggest_position_spends = [
            (pos, total) for pos, total in position_totals.items()
            if total == max_total
        ]
    else:
        biggest_position_spends = []

    # Bargain hunter (owner who spent least on average) - handle ties
    if owner_averages:
        min_avg = min(owner_averages.values())
        bargain_hunters = [
            (name, avg) for name, avg in owner_averages.items()
            if avg == min_avg
        ]
    else:
        bargain_hunters = []

    # Prepare chart data
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
    top_expensive_players = sorted(
        all_picks, key=lambda x: x['price'], reverse=True
    )[:10]

    # Team budget remaining
    team_budgets = [
        (team_data['owner'].get('team_name', 'Unknown'),
         team_data['team']['budget_remaining'])
        for team_data in teams_data
    ]
    team_budgets.sort(key=lambda x: x[1], reverse=True)

    # Roster construction heatmap data
    roster_matrix = {}
    position_order = ['QB', 'RB', 'WR', 'TE', 'K', 'D/ST']
    for team_data in teams_data:
        team_name = team_data['owner'].get('team_name', 'Unknown')
        roster_matrix[team_name] = {}

        for pick_data in team_data['players']:
            player = pick_data['player']
            pick = pick_data['pick']
            position = player.get('position', 'Unknown')
            if position in position_order:
                roster_matrix[team_name][position] = (
                    roster_matrix[team_name].get(position, 0) + pick['price']
                )

    # NFL Team Stacking data - fantasy teams drafted from each NFL team
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
    nfl_stacking_filtered = {
        nfl_team: teams
        for nfl_team, teams in nfl_stacking_data.items()
        if sum(teams.values()) >= 3
    }

    # Sort by total players drafted
    nfl_stacking_sorted = dict(sorted(nfl_stacking_filtered.items(),
                                    key=lambda x: sum(x[1].values()), reverse=True))

    # Generate JavaScript data
    team_data_json = json.dumps(
        sorted(all_nfl_teams.items(), key=lambda x: x[1], reverse=True)[:10]
    ) if all_nfl_teams else '[]'
    position_budget_json = json.dumps(position_budgets)
    position_ranges_json = json.dumps(position_ranges)
    top_players_json = json.dumps(top_expensive_players)
    team_budgets_json = json.dumps(team_budgets)
    roster_matrix_json = json.dumps(roster_matrix)
    nfl_stacking_json = json.dumps(nfl_stacking_sorted)

    # Value scatter plot data (price vs fantasy points) - original format
    value_scatter_data = []
    for pick in all_picks:
        player_id = str(next(
            (p['id'] for p in players
             if f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
             == pick['player_name']),
            0
        ))
        player_stats_data = player_stats.get(player_id, {})
        fantasy_points = calculate_fantasy_points(player_id, player_stats_data)

        if fantasy_points > 0:  # Only include players with fantasy points data
            value_scatter_data.append({
                'name': pick['player_name'],
                'price': pick['price'],
                'points': round(fantasy_points, 1),  # Round to avoid FP issues
                'position': pick.get('position', 'Unknown'),
                'team': pick['team_name']
            })

    value_scatter_json = json.dumps(value_scatter_data)

    def build_html_from_templates():
        """Build complete HTML using clean template system."""
        # Load templates
        base_template = load_template("base.html")
        css_content = load_template("style.css")
        js_template = load_template("script.js")

        # Generate teams content
        teams_content = ""
        for team_data in teams_data:
            teams_content += generate_team_card_html(team_data)

        # Generate summary stats content
        summary_stats_content = generate_summary_stats_html(
            len(teams_data), total_players, total_money, avg_price
        )

        # Generate tab content sections
        overview_content = ""  # Overview content is now just summary stats
        highlights_content = generate_highlights_content(
            most_expensive_picks, cheapest, biggest_spenders, bargain_hunters,
            best_bargain, bounce_back_pick, team_loyalty_ties, biggest_position_spends
        )
        market_content = generate_market_content(
            position_stats, biggest_position_spends
        )
        teams_tab_content = generate_teams_tab_content()
        value_content = generate_value_content()

        # Prepare JavaScript data using actual chart data
        js_content = js_template
        js_content = js_content.replace("{TEAM_DATA}", team_data_json)
        js_content = js_content.replace("{POSITION_BUDGET_DATA}", position_budget_json)
        js_content = js_content.replace("{POSITION_RANGE_DATA}", position_ranges_json)
        js_content = js_content.replace("{TOP_PLAYERS_DATA}", top_players_json)
        js_content = js_content.replace("{TEAM_BUDGET_DATA}", team_budgets_json)
        js_content = js_content.replace("{ROSTER_MATRIX_DATA}", roster_matrix_json)
        js_content = js_content.replace("{NFL_STACKING_DATA}", nfl_stacking_json)
        js_content = js_content.replace("{VALUE_SCATTER_DATA}", value_scatter_json)

        # Assemble final HTML
        return base_template.format(
            YEAR=YEAR,
            CSS_CONTENT=css_content,
            TEAMS_CONTENT=teams_content,
            SUMMARY_STATS_CONTENT=summary_stats_content,
            OVERVIEW_CONTENT=overview_content,
            HIGHLIGHTS_CONTENT=highlights_content,
            MARKET_CONTENT=market_content,
            TEAMS_TAB_CONTENT=teams_tab_content,
            VALUE_CONTENT=value_content,
            JS_CONTENT=js_content
        )

    def generate_team_card_html(team_data):
        """Generate HTML for a single team card using templates."""
        owner = team_data['owner']
        team = team_data['team']
        team_players = team_data['players']

        # Generate position badges
        position_order = ['QB', 'RB', 'WR', 'TE', 'K', 'DST', 'D/ST']
        sorted_positions = []
        for pos in position_order:
            if pos in team_data['position_counts']:
                sorted_positions.append((pos, team_data['position_counts'][pos]))
        for pos, count in team_data['position_counts'].items():
            if pos not in position_order:
                sorted_positions.append((pos, count))

        position_badge_template = load_template('position_badge.html')
        position_badges = []
        for position, count in sorted_positions:
            color = get_position_color(position)
            text_color = (
                "white" if position in ['QB', 'K', 'D/ST', 'DST'] else "#2a2a2a"
            )
            position_badge = position_badge_template.format(
                BACKGROUND_COLOR=color,
                TEXT_COLOR=text_color,
                POSITION=position,
                COUNT=count
            )
            position_badges.append(position_badge)

        position_badges_html = '\n                    '.join(position_badges)

        # Generate player items
        player_template = load_template('player_item.html')
        player_items = []

        for player_data in team_players:
            player = player_data['player']
            pick = player_data['pick']

            # Build player name
            first_name = player.get('first_name', '')
            last_name = player.get('last_name', '')
            player_name = f"{first_name} {last_name}".strip() or 'Unknown'

            # Get team and position
            nfl_team = player.get('team', '')
            position = player.get('position', '')
            price = pick.get('price', 0)

            if nfl_team:
                logo_url = f"2025/assets/logos/{nfl_team.lower()}.png"
            else:
                logo_url = (
                    "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
                    "width='20' height='20'%3E%3C/svg%3E"
                )

            position_color = get_position_color(position)
            position_text_color = (
                "white" if position in ['QB', 'K', 'D/ST', 'DST'] else "#2a2a2a"
            )

            player_item = player_template.format(
                LOGO_URL=logo_url,
                NFL_TEAM=nfl_team,
                PLAYER_NAME=player_name,
                POSITION_COLOR=position_color,
                POSITION_TEXT_COLOR=position_text_color,
                POSITION=position,
                PRICE=price
            )
            player_items.append(player_item)

        player_items_html = '\n'.join(player_items)

        # Use main team card template
        team_template = load_template('team_card.html')
        return team_template.format(
            TEAM_NAME=owner.get('team_name', 'Unknown Team'),
            OWNER_NAME=owner.get('owner_name', 'Unknown Owner'),
            PLAYER_COUNT=len(team_players),
            TOTAL_SPENT=team_data['total_spent'],
            REMAINING_BUDGET=team['budget_remaining'],
            POSITION_BADGES=position_badges_html,
            PLAYER_ITEMS=player_items_html
        )

    def generate_summary_stats_html(num_teams, total_players, total_money, avg_price):
        """Generate summary stats section HTML using template."""
        summary_template = load_template('summary_stats.html')
        return summary_template.format(
            NUM_TEAMS=num_teams,
            TOTAL_PLAYERS=total_players,
            TOTAL_MONEY=f"{total_money:,}",
            AVG_PRICE=f"{avg_price:.1f}"
        )

    def generate_highlights_content(
        most_expensive_picks, cheapest, biggest_spenders, bargain_hunters,
        best_bargain, bounce_back_pick, team_loyalty_ties,
        biggest_position_spends
    ):
        """Generate highlights tab content HTML using templates."""
        highlights_template = load_template('highlights.html')

        # Process most expensive picks
        expensive_tie = ' (tie)' if len(most_expensive_picks) > 1 else ''
        expensive_names = ', '.join([p["player_name"] for p in most_expensive_picks])
        expensive_price = (
            str(most_expensive_picks[0]["price"])
            if most_expensive_picks else '0'
        )
        expensive_teams = (
            ', '.join(list(set([p["team_name"] for p in most_expensive_picks])))
            if most_expensive_picks else ''
        )

        # Value pick section - use template
        value_section = ''
        if best_bargain:
            value_template = load_template('value_pick.html')
            value_section = value_template.format(
                PLAYER_NAME=best_bargain['player_name'],
                FANTASY_POINTS=f"{best_bargain['fantasy_points']:.1f}",
                PRICE=best_bargain['price'],
                TEAM_NAME=best_bargain['team_name'],
                VALUE_RATIO=f"{best_bargain['value_ratio']:.2f}"
            )

        # Bounce-back section - use template
        bounce_section = ''
        if bounce_back_pick:
            bounce_template = load_template('bounce_back.html')
            bounce_section = bounce_template.format(
                PLAYER_NAME=bounce_back_pick['player_name'],
                FANTASY_POINTS=f"{bounce_back_pick['fantasy_points']:.1f}",
                PRICE=bounce_back_pick['price'],
                TEAM_NAME=bounce_back_pick['team_name'],
                VALUE_RATIO=f"{bounce_back_pick['value_ratio']:.2f}"
            )

        # Team loyalty section - use template
        loyalty_section = ''
        if team_loyalty_ties:
            loyalty_template = load_template('team_loyalty.html')
            loyalty_tie = ' (tie)' if len(team_loyalty_ties) > 1 else ''
            loyalty_details = ', '.join([
                f'<span class="fact-highlight">{owner}</span> '
                f'({count} {nfl_team} players)'
                for owner, nfl_team, count in team_loyalty_ties[:3]
            ])
            loyalty_more = (
                f'<br><small>and {len(team_loyalty_ties) - 3} more...</small>'
                if len(team_loyalty_ties) > 3 else ''
            )
            loyalty_section = loyalty_template.format(
                TIE_INDICATOR=loyalty_tie,
                LOYALTY_DETAILS=loyalty_details,
                MORE_INDICATOR=loyalty_more
            )

        return highlights_template.format(
            EXPENSIVE_PICK_TIE=expensive_tie,
            EXPENSIVE_PICK_NAMES=expensive_names,
            EXPENSIVE_PICK_PRICE=expensive_price,
            EXPENSIVE_PICK_TEAMS=expensive_teams,
            VALUE_PICK_SECTION=value_section,
            BOUNCE_BACK_SECTION=bounce_section,
            BIGGEST_SPENDER_TIE=' (tie)' if len(biggest_spenders) > 1 else '',
            BIGGEST_SPENDER_NAME=(
                biggest_spenders[0][0] if biggest_spenders else 'N/A'
            ),
            BIGGEST_SPENDER_AVG=(
                f"{biggest_spenders[0][1]:.1f}" if biggest_spenders else '0'
            ),
            BIGGEST_SPENDER_MORE=(
                f'<br><small>and {len(biggest_spenders) - 1} more</small>'
                if len(biggest_spenders) > 1 else ''
            ),
            BARGAIN_HUNTER_TIE=' (tie)' if len(bargain_hunters) > 1 else '',
            BARGAIN_HUNTER_NAME=(
                bargain_hunters[0][0] if bargain_hunters else 'N/A'
            ),
            BARGAIN_HUNTER_AVG=(
                f"{bargain_hunters[0][1]:.1f}" if bargain_hunters else '0'
            ),
            BARGAIN_HUNTER_MORE=(
                f'<br><small>and {len(bargain_hunters) - 1} more</small>'
                if len(bargain_hunters) > 1 else ''
            ),
            TEAM_LOYALTY_SECTION=loyalty_section,
            POSITION_INVESTMENT_TIE=(
                ' (tie)' if len(biggest_position_spends) > 1 else ''
            ),
            POSITION_INVESTMENT_POSITIONS=(
                biggest_position_spends[0][0]
                if biggest_position_spends else 'N/A'
            ),
            POSITION_INVESTMENT_TOTAL=(
                f"{biggest_position_spends[0][1]:,}"
                if biggest_position_spends else '0'
            ),
            POSITION_INVESTMENT_MORE=(
                f'<br><small>and {len(biggest_position_spends) - 1} more</small>'
                if len(biggest_position_spends) > 1 else ''
            )
        )

    def generate_market_content(position_stats, biggest_position_spends):
        """Generate market analysis tab content HTML using template."""
        return load_template('market_analysis.html')

    def generate_teams_tab_content():
        """Generate teams strategy tab content HTML using template."""
        return load_template('team_strategy.html')

    def generate_value_content():
        """Generate value analysis tab content HTML using template."""
        return load_template('value_analysis.html')

    # Build the complete HTML using the template system
    html = build_html_from_templates()

    return html


def main():
    """Main function to generate draft recap."""
    print(f"Generating {YEAR} Draft Recap...")

    # Create output directory and assets directory (relative to project root)
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    output_dir = project_root / f"docs/{YEAR}"
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
    stats_file = project_root / "data/player_stats.json"
    if stats_file.exists():
        with open(stats_file) as f:
            player_stats = json.load(f)

    # Generate HTML
    print("Generating HTML page...")
    html_content = generate_html(
        draft_state, owners, players, config, player_stats, logo_mappings
    )

    # Save HTML file
    output_file = project_root / f"docs/{YEAR}_draft_recap.html"
    output_file.write_text(html_content, encoding='utf-8')

    print("Draft recap generated successfully!")
    print(f"Output: {output_file}")
    print(f"View at: https://[your-github-username].github.io/ffdrafttracker/{YEAR}_draft_recap.html")

if __name__ == "__main__":
    main()


