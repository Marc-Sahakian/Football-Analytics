"""
data/build_database.py — One-time sync script. Fetches teams and fixtures for a
set of major leagues across seasons 2022-2024 from API-Football, and saves them
into a local SQLite database (football.db) so the app never has to re-fetch
this data again.

Run once: uv run python data/build_database.py
Re-run only if you want to refresh the data (e.g. add a new league/season).
"""

import sqlite3
import time
from pathlib import Path
import sys
import os
import streamlit as st
from dotenv import load_dotenv


sys.path.append(str(Path(__file__).resolve().parent.parent))

from config import SEASON, ALLOWED_SEASONS, AS_OF_DATE, MAJOR_LEAGUES
import requests

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

DB_PATH = Path(__file__).parent.parent / "football.db"

API_KEY = st.secrets["SPORTS_API_KEY"]
BASE_URL = "https://v3.football.api-sports.io"
Headers = {'x-apisports-key': API_KEY}
DELAY = 10  # seconds between API calls, stays safely under per-minute limits


# ---------------------------------------------------------------------------
# Fetch helpers (raw API calls, kept local to this script for a clean one-time run)
# ---------------------------------------------------------------------------

def fetch_teams(league_id, season):
    response = requests.get(
        f"{BASE_URL}/teams",
        headers=Headers,
        params={"league": league_id, "season": season}
    )
    data = response.json()
    if data.get('errors'):
        print(f"    ERROR fetching teams: {data['errors']}")
        return []
    return data['response']


def fetch_fixtures(league_id, season):
    response = requests.get(
        f"{BASE_URL}/fixtures",
        headers=Headers,
        params={"league": league_id, "season": season}
    )
    data = response.json()
    if data.get('errors'):
        print(f"    ERROR fetching fixtures: {data['errors']}")
        return []
    return [f for f in data['response'] if f['fixture']['status']['short'] == 'FT']

def fetch_squad(team_id, league_id, season):
    all_players = []
    page = 1
    while True:
        response = requests.get(f"{BASE_URL}/players", headers = Headers,
                                     params={"team": team_id, "season": season, "league": league_id, "page": page})
        data = response.json()
        if data.get('errors'):
                print(f"    ERROR fetching squad: {data['errors']}")
                return []
        all_players.extend(data['response'])
        if data['paging']['current'] >= data['paging']['total']:
            break
        page += 1
        time.sleep(DELAY) 
    return all_players

# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

def create_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER,
            name TEXT,
            season INTEGER,
            league_id INTEGER,
            PRIMARY KEY (team_id, season, league_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fixtures (
            fixture_id INTEGER PRIMARY KEY,
            season INTEGER,
            league_id INTEGER,
            round TEXT,
            timestamp INTEGER,
            status TEXT,
            home_team_id INTEGER,
            home_team_name TEXT,
            away_team_id INTEGER,
            away_team_name TEXT,
            home_goals INTEGER,
            away_goals INTEGER
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS players(
        player_id INTEGER,
        first_name TEXT,
        last_name TEXT,
        age INTEGER,
        nationality TEXT,
        team_id INTEGER,
        team_name TEXT,
        league_id INTEGER,
        league_name TEXT,
        appearance INTEGER,
        minutes INTEGER,
        position TEXT,
        rating REAL,
        goals INTEGER,
        assists INTEGER,
        shots_on_target INTEGER,
        total_shots INTEGER,
        season INTEGER,
        PRIMARY KEY( player_id, team_id, league_id, season)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fixtures_teams ON fixtures (home_team_id, away_team_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_fixtures_league_season ON fixtures (league_id, season)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_players_league_season ON players (league_id, season)")
    conn.commit()


# ---------------------------------------------------------------------------
# Sync logic
# ---------------------------------------------------------------------------

def sync_teams(conn, league_id, season):
    teams = fetch_teams(league_id, season)
    for t in teams:
        conn.execute(
            "INSERT OR REPLACE INTO teams (team_id, name, season, league_id) VALUES (?, ?, ?, ?)",
            (t['team']['id'], t['team']['name'], season, league_id)
        )
    conn.commit()
    print(f"    {len(teams)} teams saved.")
    time.sleep(DELAY)


def sync_fixtures(conn, league_id, season):
    fixtures = fetch_fixtures(league_id, season)
    for f in fixtures:
        conn.execute("""
            INSERT OR REPLACE INTO fixtures
            (fixture_id, season, league_id, round, timestamp, status,
             home_team_id, home_team_name, away_team_id, away_team_name,
             home_goals, away_goals)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f['fixture']['id'], season, league_id, f['league']['round'],
            f['fixture']['timestamp'], f['fixture']['status']['short'],
            f['teams']['home']['id'], f['teams']['home']['name'],
            f['teams']['away']['id'], f['teams']['away']['name'],
            f['goals']['home'], f['goals']['away']
        ))
    conn.commit()
    print(f"    {len(fixtures)} fixtures saved.")
    time.sleep(DELAY)

def sync_squad_for_league_season(conn, team_id, league_id, season):
    players = fetch_squad(team_id, league_id, season)
    for p in players:
        conn.execute("""INSERT OR REPLACE INTO players
        (player_id, first_name, last_name, age, nationality, team_id, team_name, league_id,
        league_name, appearance, minutes, position, rating, goals, assists,
        shots_on_target, total_shots, season)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ? ,? ,? ,? ,? ,? ,? ,? ,?)
        """,(
            p["player"]["id"], p["player"]["firstname"], p["player"]["lastname"], p["player"]["age"], p["player"]["nationality"],
            team_id, p["statistics"][0]["team"]["name"], league_id, p["statistics"][0]["league"]["name"], p["statistics"][0]["games"]["appearences"],
            p["statistics"][0]["games"]["minutes"], p["statistics"][0]["games"]["position"], p["statistics"][0]["games"]["rating"],
            p["statistics"][0]["goals"]["total"], p["statistics"][0]["goals"]["assists"], p["statistics"][0]["shots"]["on"],
            p["statistics"][0]["shots"]["total"], season
        ))
    conn.commit()
    print(f"  {len(players)} players saved.")
    time.sleep(DELAY)


def sync_squads_for_league(conn, league_id, league_name, season):
    cursor = conn.execute("SELECT team_id, league_id FROM teams WHERE season = ? AND league_id = ?", (season, league_id,))
    team_ids = cursor.fetchall()
    print(f"  Syncing squads for {league_name}, season {season} — {len(team_ids)} teams")

    for i, row in enumerate(team_ids):
        team_id = row[0]  # fetchall() gives tuples, even for one column
        print(f"    Team {i+1}/{len(team_ids)}")
        sync_squad_for_league_season(conn, team_id, league_id, season)



def already_synced_fixtures(conn, league_id, season, min_fixtures=100):
    """
    Check if we already have a reasonable amount of fixture data for this
    league/season, so re-running the script skips it instead of re-fetching.
    min_fixtures=100 is a safety threshold — a real season has 300+ fixtures
    for a normal league, so anything under 100 is treated as incomplete/failed.
    """
    cursor = conn.execute(
        "SELECT COUNT(*) FROM fixtures WHERE league_id = ? AND season = ?",
        (league_id, season)
    )
    count = cursor.fetchone()[0]
    return count >= min_fixtures

def sync_league_season(conn, league_id, league_name, season):
    print(f"  {league_name} ({league_id}), season {season}:")
    sync_teams(conn, league_id, season)
    sync_fixtures(conn, league_id, season)
    

def already_synced_squads(conn, league_id, season, min_players=300):
    """
    Check if we already have squad data for this league/season.
    min_players=300 assumes ~20 teams x ~15+ players each is a reasonable
    floor for "this league/season is done" — adjust if a league has fewer teams.
    """
    cursor = conn.execute(
        "SELECT COUNT(*) FROM players WHERE league_id = ? AND season = ?",
        (league_id, season)
    )
    count = cursor.fetchone()[0]
    return count >= min_players

def get_next_squad_sync_target(conn):
    for league_id, league_name in MAJOR_LEAGUES.items():
        for season in ALLOWED_SEASONS:
            if not already_synced_squads(conn, league_id, season):
                return league_id, league_name, season
    return None 

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    conn = sqlite3.connect(DB_PATH)
    create_tables(conn)

    total_jobs = len(MAJOR_LEAGUES) * len(ALLOWED_SEASONS)
    job_num = 0

    for league_id, league_name in MAJOR_LEAGUES.items():
        for season in ALLOWED_SEASONS:
            job_num += 1
            print(f"[{job_num}/{total_jobs}]")

            if already_synced_fixtures(conn, league_id, season):
                print(f"  {league_name} ({league_id}), season {season}: already synced, skipping.")
                continue

            sync_league_season(conn, league_id, league_name, season)

    # Squads: one league/season per run — OUTSIDE both loops now
    target = get_next_squad_sync_target(conn)
    if target is None:
        print("\nAll squads synced!")
    else:
        league_id, league_name, season = target
        print(f"\nSyncing squads: {league_name}, season {season}")
        sync_squads_for_league(conn, league_id, league_name, season)

    conn.close()
    print(f"\nDone. Database saved to {DB_PATH}")


if __name__ == "__main__":
    main()