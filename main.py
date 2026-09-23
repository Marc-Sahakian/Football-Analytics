"""
main.py — LangChain agent using Gemini, wired to the Dixon-Coles Poisson model
(validated via backtest: lower log loss than plain Poisson on real 2023-24 results).
"""

import os
import streamlit as st
from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

from config import SEASON, MAJOR_LEAGUES, AS_OF_DATE

from data.fetching_data import (
    find_team_id,
    find_league_id,
    get_league_id,
    get_recent_form,
    find_player_id,
    get_player_stats,
    get_fixture_stats,
    get_standing,
    get_matchday_fixtures,
    get_season_fixtures,
    get_all_league_fixtures,
    get_head_to_head,
    get_team_squad,
    resolve_league_for_team,
)

from analysis.analysis import (
    calculate_league_averages,
    compute_team_strengths_weighted,
    calculate_win_probability_dixon_coles,
)

load_dotenv()

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key= st.secrets["GEMINI_API_KEY"],
    temperature=0,
)

# ---------------------------------------------------------------------------
# One-time setup: league data needed by the Dixon-Coles model.
# Computed once at startup so tools don't re-fetch it on every call.
# ---------------------------------------------------------------------------
LEAGUE_AVERAGES = {}
for league_id, league_name in MAJOR_LEAGUES.items():
    fixtures = get_all_league_fixtures(league_name, SEASON, as_of_date=AS_OF_DATE)
    if isinstance(fixtures, dict) and "error" in fixtures:
        print(f"Warning: could not compute average for {league_name}")
        continue
    LEAGUE_AVERAGES[league_name] = calculate_league_averages(fixtures)
# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def _find_team_id(team_name: str) -> dict:
    """
    Look up a team's internal numeric ID by its name.
    Must be called first for any team mentioned, unless already known from
    earlier in the conversation.
    """
    return find_team_id(team_name)


@tool
def _league_id(league_name: str)-> dict:
    """
    Look of a league's internal numeric ID by its name.
    Must be called first for any league mentioned, unless already known from earlier in the conversation
    """
    return find_league_id(league_name)


@tool
def team_league_id(team_name: str, season: int) -> dict:
    """
    Look of a league's internal numeric ID that the team mentioned is in.
    Must be called first for any team mentioned in order to get the league that the team is in, unless already
    known from earlier in the conversation
    """
    return get_league_id(team_name, season)

@tool
def get_head_to_head_summary(team_a: str, team_b: str) -> dict:
    """
    Get a summarized head-to-head record between two teams: total matches,
    wins for each team, and draws, using all available history up to the
    simulated current date.
    """
    return get_head_to_head(team_a, team_b, as_of_date=AS_OF_DATE)

@tool 
def _player_id(player_name: str, season: int)->dict:
    """
    Look for a player's id. Must be called first whenever a player's name is mentioned in order to get it's ID to access further information
    """
    return find_player_id(player_name, season)

@tool
def get_form_summary(team_name: str, season: int) -> dict:
    """
    Get a team's recent form: results (W/D/L) of their last 5 matches
    before the simulated current date, plus goals scored and conceded.
    """
    return get_recent_form(team_name, season)


@tool
def get_squad_summary(team_name: str, season: int) -> dict:
    """
    Get a team's squad, grouped by position
    (Goalkeeper, Defender, Midfielder, Attacker).
    """
    return get_team_squad(team_name, season)

@tool
def fixture_stats(team_name: str, season: int) -> dict:
    """
    Get a all fixture's of specific team during a specific season. 
    """
    return get_fixture_stats(team_name, season)

@tool
def all_fixture_stats(league_name: str, season:str, as_of_date = AS_OF_DATE) -> dict:
    """
    Get all the fixtures of a specific league during a specific season.
    """
    return get_all_league_fixtures(league_name, season, as_of_date)

@tool
def get_win_probability(home_team_name: str, away_team_name: str, season: int) -> dict:
    """
    Calculate win/draw/loss probability for a matchup using the Dixon-Coles
    Poisson model. Returns win/draw/loss percentages, each team's expected
    goals, and the top 3 most likely exact scorelines with their probabilities.
    This is the primary statistical prediction tool.
    home_team_name is the team playing at home.
    """
    home_team = find_team_id(home_team_name)
    if "error" in home_team:
        return {"error": "Could not find team"}
    if "possible_matches" in home_team:
        return home_team
    
    away_team = find_team_id(away_team_name)
    if "error" in away_team:
        return {"error": "Could not find team"}
    if "possible_matches" in away_team:
        return away_team

    league = resolve_league_for_team(team_name, season)
    if "id" not in league:
        return league  # error or unresolved ambiguity — bail out cleanly
    league_result = league["id"]

    if "possible_leagues" in league_result:
        leagues = league_result["possible_leagues"]
        domestic = [l for l in leagues if l["league_name"] != "UEFA Champions League"]
        league_name = domestic[0]["league_name"] if domestic else leagues[0]["league_name"]
    else:
        league_name = league_result["league_name"]
        
    if league_name not in LEAGUE_AVERAGES:
        return {"error": f"No league average data available for '{league_name}'"}
    league_avg = LEAGUE_AVERAGES[league_name]

    home_fixtures = get_season_fixtures(home_team_name, season, as_of_date=AS_OF_DATE)
    if isinstance(home_fixtures, dict) and "error" in home_fixtures:
        return home_fixtures
    away_fixtures = get_season_fixtures(away_team_name, season, as_of_date=AS_OF_DATE)
    if isinstance(away_fixtures, dict) and "error" in away_fixtures:
        return away_fixtures

    home_strength = compute_team_strengths_weighted(home_fixtures, home_team["id"], league_avg, AS_OF_DATE)
    away_strength = compute_team_strengths_weighted(away_fixtures, away_team["id"], league_avg, AS_OF_DATE)

    return calculate_win_probability_dixon_coles(home_strength, away_strength, league_avg)

# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = create_agent(
     tools=[
        _find_team_id,
        _league_id,
        team_league_id,
        get_head_to_head_summary,
        _player_id,
        get_form_summary,
        get_squad_summary,
        fixture_stats,
        all_fixture_stats,
        get_win_probability,
    ],
    model=llm,
    system_prompt=(
    "You are a football analyst assistant, working as if the current date is "
    "January 1, 2024. Predictions and analysis are based on historical statistics "
    "up to that point, not live data.\n\n"
    "For matchup questions ('who wins X vs Y'):\n"
    "1. Resolve team names if ambiguous.\n"
    "2. Call get_win_probability — this is your primary source for the probability.\n"
    "3. Gather head-to-head and recent form for context.\n"
    "4. Present the probability with a clear explanation.\n\n"
    "For general questions about a team (e.g. 'what do you think of X', "
    "'how has X been playing'), gather relevant data (recent form, squad, "
    "fixtures) and give a genuine analytical opinion — don't just list raw "
    "stats. Explain what the data suggests about the team's strengths, "
    "weaknesses, form, or trajectory, the way a real football analyst would.\n\n"
    "Always ground your analysis in the data from your tools, but synthesize "
    "it into an actual assessment, not just a data dump. Stay focused on "
    "football topics; politely redirect unrelated requests."
),
)


def ask(messages: list) -> str:
    """Send the full conversation history to the agent and return its final text answer."""
    result = agent.invoke({"messages": messages})
    content = result["messages"][-1].content

    if isinstance(content, str):
        return content

    # content is a list of blocks (Gemini sometimes returns this with grounding metadata)
    text_parts = [block["text"] for block in content if isinstance(block, dict) and block.get("type") == "text"]
    return "\n".join(text_parts)


if __name__ == "__main__":
    answer = ask("Who do you think wins between Manchester City and Arsenal?")
    print(answer)