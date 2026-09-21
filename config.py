"""
config.py — single source of truth for constants used across fetching_data.py,
processing.py, poisson_model.py, and main.py.
"""

from datetime import datetime

SEASON = 2023  # 2023-24 season (API-Football labels by start year)
ALLOWED_SEASONS = [2022, 2023, 2024]  # what your free-tier plan covers
AS_OF_DATE = datetime(2024, 1, 1)  # simulated "current" point in time
MAJOR_LEAGUES = {
    39: "Premier League",
    140: "La Liga",
    135: "Serie A",
    78: "Bundesliga",
    61: "Ligue 1",
    2: "UEFA Champions League",
}