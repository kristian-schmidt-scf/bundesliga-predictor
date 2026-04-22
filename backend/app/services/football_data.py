"""
Service layer for football-data.org API.

Docs: https://www.football-data.org/documentation/quickstart
Free tier includes Bundesliga (BL1) fixtures, results, standings.
"""

import httpx
from datetime import datetime, timezone
from app.config import settings
from app.models.schemas import Fixture, Team
import logging

logger = logging.getLogger(__name__)

HEADERS = {"X-Auth-Token": settings.football_data_api_key}


async def get_upcoming_fixtures(matchdays_ahead: int = 5) -> list[Fixture]:
    """Fetch upcoming scheduled Bundesliga fixtures."""
    url = f"{settings.football_data_base_url}/competitions/{settings.bundesliga_competition_code}/matches"
    params = {"status": "SCHEDULED"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()

    data = resp.json()
    fixtures = []
    for match in data.get("matches", []):
        fixtures.append(_parse_fixture(match))

    fixtures.sort(key=lambda f: f.utc_date)
    return fixtures


async def get_current_and_upcoming_fixtures() -> list[Fixture]:
    """
    Fetch fixtures from the last 7 days through the end of scheduled matches.
    Includes FINISHED games from the current matchday alongside upcoming ones.
    """
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    date_from = f"{now.year}-01-01"
    date_to = (now + timedelta(days=60)).strftime("%Y-%m-%d")

    url = f"{settings.football_data_base_url}/competitions/{settings.bundesliga_competition_code}/matches"
    params = {"dateFrom": date_from, "dateTo": date_to}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()

    data = resp.json()
    fixtures = [_parse_fixture(m) for m in data.get("matches", [])]
    fixtures.sort(key=lambda f: f.utc_date)
    return fixtures


async def get_historical_results(num_seasons: int = 3) -> list[dict]:
    """
    Fetch historical match results across multiple seasons.
    Returns raw dicts with: home_team, away_team, home_goals, away_goals, date.
    Used to fit the Dixon-Coles model.
    """
    results = []
    current_year = datetime.now(timezone.utc).year

    async with httpx.AsyncClient() as client:
        for offset in range(num_seasons):
            season = current_year - offset - 1  # e.g. 2023 = 2023/24 season
            url = (
                f"{settings.football_data_base_url}/competitions/"
                f"{settings.bundesliga_competition_code}/matches"
            )
            params = {"season": season, "status": "FINISHED"}
            try:
                resp = await client.get(url, headers=HEADERS, params=params, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                for match in data.get("matches", []):
                    score = match.get("score", {}).get("fullTime", {})
                    home_goals = score.get("home")
                    away_goals = score.get("away")
                    if home_goals is None or away_goals is None:
                        continue
                    results.append({
                        "home_team": match["homeTeam"]["name"],
                        "away_team": match["awayTeam"]["name"],
                        "home_goals": int(home_goals),
                        "away_goals": int(away_goals),
                        "date": match["utcDate"],
                    })
            except httpx.HTTPError as e:
                logger.warning(f"Failed to fetch season {season}: {e}")

    logger.info(f"Fetched {len(results)} historical results across {num_seasons} seasons")
    return results


async def get_current_season_results() -> list[dict]:
    """Fetch finished matches from the current season (for recent form)."""
    url = f"{settings.football_data_base_url}/competitions/{settings.bundesliga_competition_code}/matches"
    params = {"status": "FINISHED"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS, params=params, timeout=10)
        resp.raise_for_status()

    data = resp.json()
    results = []
    for match in data.get("matches", []):
        score = match.get("score", {}).get("fullTime", {})
        home_goals = score.get("home")
        away_goals = score.get("away")
        if home_goals is None or away_goals is None:
            continue
        results.append({
            "home_team": match["homeTeam"]["name"],
            "away_team": match["awayTeam"]["name"],
            "home_goals": int(home_goals),
            "away_goals": int(away_goals),
            "date": match["utcDate"],
        })
    return results


async def get_standings() -> list[dict]:
    """Fetch current Bundesliga standings."""
    url = f"{settings.football_data_base_url}/competitions/{settings.bundesliga_competition_code}/standings"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()

    data = resp.json()
    table = data["standings"][0]["table"]  # [0] = overall standings
    return [
        {
            "position": row["position"],
            "team_id": row["team"]["id"],
            "team_name": row["team"]["name"],
            "team_short_name": row["team"].get("shortName", row["team"]["name"]),
            "team_crest": row["team"].get("crest"),
            "played": row["playedGames"],
            "won": row["won"],
            "draw": row["draw"],
            "lost": row["lost"],
            "goals_for": row["goalsFor"],
            "goals_against": row["goalsAgainst"],
            "goal_difference": row["goalDifference"],
            "points": row["points"],
            "form": row.get("form", ""),
        }
        for row in table
    ]


def _parse_fixture(match: dict) -> Fixture:
    home = match["homeTeam"]
    away = match["awayTeam"]
    full_time = match.get("score", {}).get("fullTime", {})
    return Fixture(
        id=match["id"],
        home_team=Team(
            id=home["id"],
            name=home["name"],
            short_name=home.get("shortName", home["name"]),
            crest_url=home.get("crest"),
        ),
        away_team=Team(
            id=away["id"],
            name=away["name"],
            short_name=away.get("shortName", away["name"]),
            crest_url=away.get("crest"),
        ),
        utc_date=datetime.fromisoformat(match["utcDate"].replace("Z", "+00:00")),
        matchday=match.get("matchday", 0),
        status=match["status"],
        home_score=full_time.get("home"),
        away_score=full_time.get("away"),
    )
