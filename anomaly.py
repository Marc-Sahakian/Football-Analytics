import sys
sys.path.append("data")

from config import AS_OF_DATE
from fetching_data import find_team_id, get_league_id, get_season_fixtures
from analysis.analysis import compute_team_strengths_weighted, calculate_win_probability_dixon_coles

# reuse whatever LEAGUE_AVERAGES your main.py computes — paste that value here,
# or recompute it fresh:
from config import MAJOR_LEAGUES, SEASON
from fetching_data import get_all_league_fixtures
from analysis.analysis import calculate_league_averages

LEAGUE_AVERAGES = {}
for league_id, league_name in MAJOR_LEAGUES.items():
    fixtures = get_all_league_fixtures(league_name, SEASON, as_of_date=AS_OF_DATE)
    if fixtures and not (isinstance(fixtures, dict) and "error" in fixtures):
        LEAGUE_AVERAGES[league_name] = calculate_league_averages(fixtures)

home_name = "Manchester United"
away_name = "Liverpool"
season = 2023

home_team = find_team_id(home_name)
away_team = find_team_id(away_name)
print("home_team:", home_team)
print("away_team:", away_team)

league_result = get_league_id(home_name, season)
print("league_result:", league_result)

if "possible_leagues" in league_result:
    leagues = league_result["possible_leagues"]
    domestic = [l for l in leagues if l["league_name"] != "UEFA Champions League"]
    league_name = domestic[0]["league_name"] if domestic else leagues[0]["league_name"]
else:
    league_name = league_result["league_name"]
league_avg = LEAGUE_AVERAGES[league_name]
print("league_name:", league_name, "league_avg:", league_avg)

home_fixtures = get_season_fixtures(home_name, season, as_of_date=AS_OF_DATE)
away_fixtures = get_season_fixtures(away_name, season, as_of_date=AS_OF_DATE)
print("home_fixtures count:", len(home_fixtures))
print("away_fixtures count:", len(away_fixtures))

home_strength = compute_team_strengths_weighted(home_fixtures, home_team["id"], league_avg, AS_OF_DATE)
away_strength = compute_team_strengths_weighted(away_fixtures, away_team["id"], league_avg, AS_OF_DATE)
print("home_strength:", home_strength)
print("away_strength:", away_strength)

result = calculate_win_probability_dixon_coles(home_strength, away_strength, league_avg)
print("result:", result)

total = result["home_win_probability"] + result["draw_probability"] + result["away_win_probability"]
print("TOTAL (should be ~100):", total)