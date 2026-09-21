import sys
sys.path.append("data")

from config import MAJOR_LEAGUES, SEASON, AS_OF_DATE
from data.fetching_data import get_all_league_fixtures

for league_id, league_name in MAJOR_LEAGUES.items():
    fixtures = get_all_league_fixtures(league_name, SEASON, as_of_date=AS_OF_DATE)
    if isinstance(fixtures, dict) and "error" in fixtures:
        print(league_name, "-> ERROR:", fixtures)
    elif not fixtures:
        print(league_name, "-> EMPTY (0 fixtures)")
    else:
        print(league_name, "->", len(fixtures), "fixtures")