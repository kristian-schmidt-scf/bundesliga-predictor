"""
Service layer for The Odds API.

Docs: https://the-odds-api.com/liveapi/guides/v4/
Free tier: 500 requests/month. We cache aggressively to avoid burning quota.
"""

import httpx
from app.config import settings
from app.models.schemas import MatchOdds
import logging

logger = logging.getLogger(__name__)


async def get_bundesliga_odds() -> dict[str, MatchOdds]:
    """
    Fetch current h2h odds for all upcoming Bundesliga matches.
    Returns a dict keyed by a normalised match key: "home_team vs away_team"
    so we can join against fixtures from football-data.org.
    """
    url = f"{settings.odds_api_base_url}/sports/{settings.odds_sport_key}/odds"
    params = {
        "apiKey": settings.odds_api_key,
        "regions": settings.odds_regions,
        "markets": settings.odds_markets,
        "oddsFormat": settings.odds_format,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=10)
        resp.raise_for_status()

    data = resp.json()
    odds_map: dict[str, MatchOdds] = {}

    for event in data:
        home_team = event.get("home_team", "")
        away_team = event.get("away_team", "")
        bookmakers = event.get("bookmakers", [])

        if not bookmakers:
            continue

        # Use the first available bookmaker (you could average across all)
        bookie = bookmakers[0]
        bookie_name = bookie.get("title", "unknown")
        markets = bookie.get("markets", [])

        h2h_outcomes = None
        for market in markets:
            if market["key"] == "h2h":
                h2h_outcomes = {o["name"]: o["price"] for o in market["outcomes"]}
                break

        if not h2h_outcomes:
            continue

        home_odds = h2h_outcomes.get(home_team)
        away_odds = h2h_outcomes.get(away_team)
        draw_odds = h2h_outcomes.get("Draw")

        if not all([home_odds, away_odds, draw_odds]):
            continue

        # Implied probabilities (raw, will sum to > 1 due to bookmaker margin)
        raw_home = 1 / home_odds
        raw_draw = 1 / draw_odds
        raw_away = 1 / away_odds
        total = raw_home + raw_draw + raw_away

        match_odds = MatchOdds(
            home_win=home_odds,
            draw=draw_odds,
            away_win=away_odds,
            implied_home_prob=round(raw_home / total, 4),
            implied_draw_prob=round(raw_draw / total, 4),
            implied_away_prob=round(raw_away / total, 4),
            bookmaker=bookie_name,
        )

        # Store under both orderings to make matching easier
        key = _match_key(home_team, away_team)
        odds_map[key] = match_odds

    logger.info(f"Fetched odds for {len(odds_map)} Bundesliga matches")
    return odds_map


def _match_key(home: str, away: str) -> str:
    """Normalised key for matching across different data sources."""
    return f"{home.lower().strip()}||{away.lower().strip()}"


def find_odds_for_fixture(
    odds_map: dict[str, MatchOdds],
    home_team_name: str,
    away_team_name: str,
) -> MatchOdds | None:
    """
    Try to match a fixture to odds. Team names may differ slightly between
    football-data.org and The Odds API, so we do a fuzzy search.
    """
    # Exact match first
    key = _match_key(home_team_name, away_team_name)
    if key in odds_map:
        return odds_map[key]

    # Fuzzy: check if either name contains the other
    home_lower = home_team_name.lower()
    away_lower = away_team_name.lower()
    for stored_key, odds in odds_map.items():
        stored_home, stored_away = stored_key.split("||")
        if (
            _names_match(home_lower, stored_home)
            and _names_match(away_lower, stored_away)
        ):
            return odds

    return None


def _names_match(name_a: str, name_b: str) -> bool:
    """Loose name matching — handles 'Bayern Munich' vs 'FC Bayern München' etc."""
    # Strip common prefixes
    for prefix in ["fc ", "bv ", "sv ", "1. ", "vfb ", "vfl ", "tsg "]:
        name_a = name_a.replace(prefix, "")
        name_b = name_b.replace(prefix, "")
    return name_a in name_b or name_b in name_a or name_a[:5] == name_b[:5]
