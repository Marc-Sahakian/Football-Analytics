import requests
import os
import sqlite3
from dotenv import load_dotenv
from pathlib import Path
from config import SEASON, ALLOWED_SEASONS, AS_OF_DATE, MAJOR_LEAGUES
from difflib import get_close_matches


DB_PATH = str(Path(__file__).resolve().parent.parent / "football.db")

load_dotenv(dotenv_path= Path(__file__).resolve().parent.parent / ".env")

API_KEY = os.getenv("SPORTS_API_KEY")
BASE_URL = "https://v3.football.api-sports.io"
Headers = {'x-apisports-key': API_KEY}


def find_team_id(team_name: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT name, team_id FROM teams WHERE LOWER(name) LIKE ?",
        (f"%{team_name.lower()}%",)
    )
    results = cursor.fetchall()
    conn.close()

    if not results:
        return {"error": f"No team found matching '{team_name}'"}
    if len(results) > 1:
        return {"possible_matches": [{"id": r[1], "name": r[0]} for r in results]}
    return {"id": results[0][1], "name": results[0][0]}


def find_league_id(league_name: str) -> dict:
    matches = [
        {"id": lid, "name": lname}
        for lid, lname in MAJOR_LEAGUES.items()
        if league_name.lower() in lname.lower()
    ]
    if not matches:
        return {"error": f"No league found matching '{league_name}'"}
    if len(matches) > 1:
        return {"possible_matches": matches}
    return matches[0]

def get_league_id(team_name: str, season: int) -> dict:
    team_result = find_team_id(team_name)
    if "error" in team_result:
        return {"error": "Could not find team"}
    if "possible_matches" in team_result:
        return team_result  # let the agent see the ambiguity and ask the user to clarify
    team_id = team_result["id"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT league_id FROM teams WHERE team_id = ? AND season = ?", (team_id, season))
    results = cursor.fetchall()
    conn.close()

    possible_leagues = []  # build this up across the loop instead of returning inside it
    for r in results:
        league_id = r[0]  # each row is a tuple like (39,) — grab the actual value
        league_name = MAJOR_LEAGUES[league_id]  # look this up from MAJOR_LEAGUES using league_id
        possible_leagues.append({"id": league_id, "league_name": league_name})

    if len(possible_leagues) > 1:
        return {"possible_leagues": possible_leagues}
    
    return possible_leagues[0]

def resolve_league_for_team(team_name: str, season: int):
    """
    Resolves a team name to a single league dict {"id":, "league_name":}.
    Handles all of get_league_id's possible return shapes in one place.
    Prefers a domestic league over Champions League when ambiguous.
    """
    league = get_league_id(team_name, season)

    if "error" in league:
        return league
    if "possible_matches" in league:
        return league  #let the agent handle it
    if "possible_leagues" in league:
        leagues = league["possible_leagues"]
        domestic = [l for l in leagues if l["league_name"] != "UEFA Champions League"]
        return domestic[0] if domestic else leagues[0]
    return league  


def get_recent_form(team_name: str, season: int) -> dict:
    team_result = find_team_id(team_name)
    if "error" in team_result:
        return {"error": "Could not find team"}
    if "possible_matches" in team_result:
        return team_result  # let the agent see the ambiguity and ask the user to clarify
    team_id = team_result["id"]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT round,home_team_id, home_team_name,away_team_id, away_team_name, home_goals, away_goals FROM fixtures WHERE (home_team_id = ? OR away_team_id = ?)  AND season = ? AND timestamp < ? ORDER BY timestamp DESC limit 5",
                   (team_id, team_id, season, (int(AS_OF_DATE.timestamp()))))
    results = cursor.fetchall()
    conn.close()
    games = []
    goals_for = 0
    goals_against = 0
    for f in results:
        if f[1] == team_id:
            gf = f[5]
            ga = f[6]
        else:
            gf = f[6]
            ga = f[5]
        goals_for += gf
        goals_against += ga
        if gf > ga:
            games.append("W")
        elif gf < ga:
            games.append("L")
        else:
            games.append("D")


    return {"last_results": games, "goals_for": goals_for, "goals_against": goals_against}


def find_player_id(player_name: str, season: int) -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT player_id, first_name, last_name FROM players WHERE (LOWER(first_name) LIKE ?) OR (LOWER(last_name) LIKE ?) AND season = ?",
        (f"%{player_name.lower()}%", f"%{player_name.lower()}%", season)
    )
    results = cursor.fetchall()
    conn.close()

    if not results:
        return {"error": f"No player found matching '{player_name}'"}
    if len(results) > 1:
        return {"possible_matches": [{"id": r[0], "name": r[1]} for r in results]}
    return {"id": results[0][0], "name": results[0][1]}



def get_player_stats(player_id, season):
    response = requests.get(f"{BASE_URL}/players", headers=Headers, params={"id": player_id, "season": season})
    return response.json()

def get_fixture_stats(team_name:str, season: int) -> dict:
    team_result = find_team_id(team_name)
    if "error" in team_result:
        return {"error": "Could not find team"}
    if "possible_matches" in team_result:
        return team_result  # let the agent see the ambiguity and ask the user to clarify
    team_id = team_result["id"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT home_team_name, home_goals, away_team_name, away_goals FROM fixtures WHERE (home_team_id = ? OR away_team_id = ?) AND season = ?", 
                   (team_id, team_id, season, ))
    results = cursor.fetchall()
    conn.close()
    fixtures = []
    for r in results:
         fixtures.append({
              "fixture": {
                   "home":{ "name":r[0], "goals": r[1] }},
                   "away":{ "name":r[2], "goals":r[3]}
                   })

    return fixtures

def get_standing(league_id, season):
    response = requests.get(f"{BASE_URL}/standings", headers=Headers, params={"league": league_id, "season": season})
    return response.json()

def get_season_fixtures(team_name: str, season: int, as_of_date=AS_OF_DATE) -> dict:
    """All finished fixtures for a team in a season, up to the cutoff date."""

    league = resolve_league_for_team(team_name, season)
    if "id" not in league:
        return league  # error or unresolved ambiguity — bail out cleanly
    league_id = league["id"]

    team_result = find_team_id(team_name)
    if "error" in team_result:
        return {"error": "Could not find team"}
    if "possible_matches" in team_result:
        return team_result  # let the agent see the ambiguity and ask the user to clarify
    team_id = team_result["id"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT home_team_id, home_team_name, away_team_id, away_team_name,home_goals, away_goals, timestamp FROM fixtures WHERE (home_team_id = ? OR away_team_id = ?) AND (season = ?) AND (league_id = ?) AND timestamp < ?",
                   (team_id, team_id, season, league_id, int(as_of_date.timestamp())))
    results = cursor.fetchall()
    conn.close()

    fixtures = []
    for r in results:
         fixtures.append({"teams":
                          {"home":{"id": r[0], "name": r[1]},
                          "away": {"id": r[2], "name": r[3]}},
                          "goals":{"home": r[4], "away": r[5]},
                          "timestamp": r[6]})
    return fixtures


def get_matchday_fixtures(team_name: str, season: int, round_name: str) -> dict:
    """
    Get all fixtures for a specific matchday/round, e.g. 'Regular Season - 21'.
    Returns finished fixtures only, with real scores included for comparison.
    """
    league = resolve_league_for_team(team_name, season)
    if "id" not in league:
        return league  # error or unresolved ambiguity — bail out cleanly
    league_id = league["id"]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT home_team_id, home_team_name, away_team_id, away_team_name, home_goals, away_goals FROM fixtures WHERE league_id = ? AND round =? AND season =?",
                   (league_id, round_name, season, ))
    results = cursor.fetchall()
    conn.close()
    fixtures = []
    for r in results:
         fixtures.append({"teams":
                          {"home":{"id": r[0], "name": r[1]},
                          "away": {"id": r[2], "name": r[3]}},
                          "goals":{"home": r[4], "away": r[5]}})
    return fixtures

def get_all_league_fixtures(league_name: str, season:str, as_of_date = AS_OF_DATE) -> dict:

    league = find_league_id(league_name)
    if "error" in league:
        return league
    league_id = league["id"]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT home_team_id, home_team_name, away_team_id, away_team_name, home_goals, away_goals, season FROM fixtures WHERE league_id = ? AND timestamp < ? AND season = ?",
                   (league_id, int(as_of_date.timestamp()), season))
    results = cursor.fetchall()
    conn.close()

    fixtures = []
    for r in results:
         fixtures.append({"teams":
                          {"home":{"id": r[0], "name": r[1]},
                          "away": {"id": r[2], "name": r[3]}},
                          "goals":{"home": r[4], "away": r[5]}})
    return fixtures


def get_head_to_head(team_a_name: str, team_b_name: str, as_of_date=AS_OF_DATE) -> dict:
    """Fetch h2h fixtures and return a summary: total matches, wins for each team, draws."""
    team_a = find_team_id(team_a_name)
    if "error" in team_a:
        return {"error":"Could not find team"}
    if "possible_matches" in team_a:
        return team_a 
    team_a_id = team_a["id"]

    team_b = find_team_id(team_b_name)
    if "error" in team_b:
        return {"error": "Could not find team"}
    if "possible_matches" in team_b:
        return team_b
    team_b_id = team_b["id"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT home_team_id, home_goals, away_goals FROM fixtures "
        "WHERE (home_team_id = ? OR away_team_id = ?) AND (home_team_id = ? OR away_team_id = ?) AND timestamp < ?",
        (team_a_id, team_a_id, team_b_id, team_b_id, int(as_of_date.timestamp()))
    )
    results = cursor.fetchall()
    conn.close()

    team_a_wins = 0
    team_b_wins = 0
    draws = 0
    for home_id, home_goals, away_goals in results:
        if home_goals > away_goals:
            team_a_wins += 1 if home_id == team_a_id else 0
            team_b_wins += 1 if home_id == team_b_id else 0
        elif away_goals > home_goals:
            team_a_wins += 1 if home_id == team_b_id else 0
            team_b_wins += 1 if home_id == team_a_id else 0
        else:
            draws += 1

    return {
        "total_matches": len(results),
        "team_a_wins": team_a_wins,
        "team_b_wins": team_b_wins,
        "draws": draws
    }
    


def get_team_squad(team_name: str, season: int) -> dict:

    team_result = find_team_id(team_name)
    if "error" in team_result:
        return {"error": "Could not find team"}
    if "possible_matches" in team_result:
        return team_result  # let the agent see the ambiguity and ask the user to clarify
    team_id = team_result["id"]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT first_name, last_name, team_name, position FROM players WHERE team_id = ? AND season = ?",
                   (team_id, season))
    results = cursor.fetchall()
    conn.close()

    by_position = {"Goalkeeper": [], "Defender": [], "Midfielder": [], "Attacker": []}
    for p in results:
        full_name = p[0] + " " + p[1]
        position = p[3]
        if position in by_position:
            by_position[position].append(full_name)
    return {"total_players": len(results), "by_position": by_position}

