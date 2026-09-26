"""
analysis/poisson_model.py — Dixon-Coles Poisson model for match outcome prediction.
Time-weighted team strengths + low-score correction, validated via backtest
against real 2023-24 Premier League results.
"""

import numpy as np
from scipy.stats import poisson


def calculate_league_averages(all_league_fixtures):
    """Compute the league-wide average goals scored per team per game."""
    total_goals = 0
    total_team_games = 0
    for f in all_league_fixtures:
        total_goals += f['goals']['home'] + f['goals']['away']
        total_team_games += 2
    return total_goals / total_team_games


def calculate_time_weight(match_timestamp, as_of_date, xi=0.0018):
    """
    xi controls decay speed — higher xi means older matches lose influence faster.
    0.0018 is a standard Dixon-Coles starting value.
    """
    days_since = (as_of_date.timestamp() - match_timestamp) / 86400
    return np.exp(-xi * days_since)


def compute_team_strengths_weighted(team_fixtures, team_id, league_avg_goals, as_of_date, xi=0.0018):
    """Time-weighted attack/defense strength relative to league average."""
    weighted_goals_for = 0
    weighted_goals_against = 0
    total_weight = 0

    for f in team_fixtures:
        is_home = f['teams']['home']['id'] == team_id
        gf = f['goals']['home'] if is_home else f['goals']['away']
        ga = f['goals']['away'] if is_home else f['goals']['home']

        w = calculate_time_weight(f['timestamp'], as_of_date, xi)
        weighted_goals_for += gf * w
        weighted_goals_against += ga * w
        total_weight += w

    return {
        "attack": (weighted_goals_for / total_weight) / league_avg_goals,
        "defense": (weighted_goals_against / total_weight) / league_avg_goals,
        "effective_games": total_weight,
    }


def dixon_coles_tau(home_goals, away_goals, home_expected, away_expected, rho=-0.13):
    """Low-score correction for the four cells where Poisson underestimates football reality."""
    if home_goals == 0 and away_goals == 0:
        return 1 - (home_expected * away_expected * rho)
    elif home_goals == 0 and away_goals == 1:
        return 1 + (home_expected * rho)
    elif home_goals == 1 and away_goals == 0:
        return 1 + (away_expected * rho)
    elif home_goals == 1 and away_goals == 1:
        return 1 - rho
    return 1.0


def calculate_win_probability_dixon_coles(home_strength, away_strength, league_avg_goals,
                                            max_goals=6, home_advantage=1.35, rho=-0.2):
    """
    Full Dixon-Coles prediction: time-weighted strengths + low-score correction.
    This is the validated production model (backtested against real results,
    outperformed plain Poisson on log loss).
    """
    home_expected = league_avg_goals * home_strength["attack"] * away_strength["defense"] * home_advantage
    away_expected = league_avg_goals * away_strength["attack"] * home_strength["defense"]

    score_matrix = np.zeros((max_goals + 1, max_goals + 1))
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            base_prob = poisson.pmf(h, home_expected) * poisson.pmf(a, away_expected)
            tau = dixon_coles_tau(h, a, home_expected, away_expected, rho)
            score_matrix[h][a] = base_prob * tau

    score_matrix = score_matrix / score_matrix.sum()

    home_win_prob = np.sum(np.tril(score_matrix, -1))
    draw_prob = np.sum(np.diag(score_matrix))
    away_win_prob = np.sum(np.triu(score_matrix, 1))

    # NEW: find the top 3 most likely scorelines
    # think: score_matrix is a 2D grid where score_matrix[h][a] = probability
    # of that exact scoreline. You want the 3 highest values and their (h, a) positions.
    
    flat_indices = np.argsort(score_matrix.ravel())[::-1][:3]  # top 3, highest first
    top_scorelines = []
    for idx in flat_indices:
        h, a = np.unravel_index(idx, score_matrix.shape)
        top_scorelines.append({
            "score": f"{h}-{a}",
            "probability": float(round(score_matrix[h][a] * 100, 1))
        })

    return {
        "home_win_probability": float(round(home_win_prob * 100, 1)),
        "draw_probability": float(round(draw_prob * 100, 1)),
        "away_win_probability": float(round(away_win_prob * 100, 1)),
        "home_expected_goals": float(round(home_expected, 2)),
        "away_expected_goals": float(round(away_expected, 2)),
        "top_scorelines": top_scorelines,
    }