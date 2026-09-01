"""
Service layer for OpenLigaDB (api.openligadb.de) — used for 2. Bundesliga data.

football-data.org's free tier does not include 2. Bundesliga (BL2 -> 403),
so this second competition is sourced entirely from OpenLigaDB instead:
free, no API key, no rate limit, and the codebase already depends on it
for DFB-Pokal data (see recent_fixtures.py).

Every fixture ID produced here is offset by BL2_ID_OFFSET so it can never
collide with a football-data.org fixture ID (which are currently in the
low hundred-thousands and grow slowly) -- this lets user_picks,
prediction_cache_db, and every other int-keyed table treat BL2 fixtures
exactly like BL1 ones with zero schema changes.
"""

import httpx
import time
import logging
from datetime import datetime, timezone

from app.models.schemas import Fixture, Team

logger = logging.getLogger(__name__)

OPENLIGA_BASE = "https://api.openligadb.de"
LEAGUE_SHORTCUT = "bl2"

BL2_ID_OFFSET = 1_000_000_000

_fixtures_cache: list[Fixture] | None = None
_fixtures_cache_ts: float = 0.0
_FIXTURES_TTL = 60.0  # seconds, mirrors football_data.py's fixtures cache

_standings_cache: list[dict] | None = None
_standings_cache_ts: float = 0.0
_STANDINGS_TTL = 300.0  # 5 minutes, mirrors football_data.py's standings cache


def _current_season() -> int:
    """OpenLigaDB seasons are keyed by the year the season starts (e.g. 2026 = 2026/27)."""
    now = datetime.now(timezone.utc)
    return now.year if now.month >= 7 else now.year - 1


def _final_score(match: dict) -> tuple[int | None, int | None]:
    """
    Pick the most authoritative score available: the final result if the
    match has one, else the half-time result (for in-play matches), else
    no score yet.
    """
    results = match.get("matchResults") or []
    by_kind = {r["resultTypeKind"]: r for r in results}
    result = by_kind.get("After90Minutes") or by_kind.get("HalfTime")
    if result is None:
        return None, None
    return result["pointsTeam1"], result["pointsTeam2"]


def _status(match: dict) -> str:
    if match["matchIsFinished"]:
        return "FINISHED"
    kickoff = datetime.fromisoformat(match["matchDateTimeUTC"].replace("Z", "+00:00"))
    if datetime.now(timezone.utc) >= kickoff:
        return "IN_PLAY"
    return "SCHEDULED"


def _parse_fixture(match: dict) -> Fixture:
    team1, team2 = match["team1"], match["team2"]
    home_score, away_score = _final_score(match)
    return Fixture(
        id=BL2_ID_OFFSET + match["matchID"],
        home_team=Team(
            id=team1["teamId"],
            name=team1["teamName"],
            short_name=team1.get("shortName", team1["teamName"]),
            crest_url=team1.get("teamIconUrl"),
        ),
        away_team=Team(
            id=team2["teamId"],
            name=team2["teamName"],
            short_name=team2.get("shortName", team2["teamName"]),
            crest_url=team2.get("teamIconUrl"),
        ),
        utc_date=datetime.fromisoformat(match["matchDateTimeUTC"].replace("Z", "+00:00")),
        matchday=match.get("group", {}).get("groupOrderID", 0),
        status=_status(match),
        home_score=home_score,
        away_score=away_score,
    )


async def _fetch_season_matches(client: httpx.AsyncClient, season: int) -> list[dict]:
    url = f"{OPENLIGA_BASE}/getmatchdata/{LEAGUE_SHORTCUT}/{season}"
    resp = await client.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


async def get_historical_results_bl2(num_seasons: int) -> list[dict]:
    """
    Fetch finished-match results across multiple past seasons.
    Returns raw dicts with: home_team, away_team, home_goals, away_goals, date.
    Used to fit the Dixon-Coles model, same shape as football_data.get_historical_results().
    """
    current_season = _current_season()
    results = []
    async with httpx.AsyncClient() as client:
        for offset in range(1, num_seasons + 1):
            season = current_season - offset
            try:
                matches = await _fetch_season_matches(client, season)
            except httpx.HTTPError as e:
                logger.warning(f"Failed to fetch BL2 season {season}: {e}")
                continue
            for m in matches:
                if not m["matchIsFinished"]:
                    continue
                hg, ag = _final_score(m)
                if hg is None or ag is None:
                    continue
                results.append({
                    "home_team": m["team1"]["teamName"],
                    "away_team": m["team2"]["teamName"],
                    "home_goals": int(hg),
                    "away_goals": int(ag),
                    "date": m["matchDateTimeUTC"],
                })
    logger.info(f"Fetched {len(results)} BL2 historical results across {num_seasons} seasons")
    return results


async def get_current_season_results_bl2() -> list[dict]:
    """Fetch finished BL2 matches from the current season (for recent form)."""
    async with httpx.AsyncClient() as client:
        matches = await _fetch_season_matches(client, _current_season())
    results = []
    for m in matches:
        if not m["matchIsFinished"]:
            continue
        hg, ag = _final_score(m)
        if hg is None or ag is None:
            continue
        results.append({
            "home_team": m["team1"]["teamName"],
            "away_team": m["team2"]["teamName"],
            "home_goals": int(hg),
            "away_goals": int(ag),
            "date": m["matchDateTimeUTC"],
            "matchday": m.get("group", {}).get("groupOrderID", 0),
        })
    return results


async def get_current_and_upcoming_fixtures_bl2() -> list[Fixture]:
    """All fixtures (played + scheduled) for the current BL2 season. Cached for 60s."""
    global _fixtures_cache, _fixtures_cache_ts
    if _fixtures_cache is not None and (time.monotonic() - _fixtures_cache_ts) < _FIXTURES_TTL:
        return _fixtures_cache

    async with httpx.AsyncClient() as client:
        matches = await _fetch_season_matches(client, _current_season())

    fixtures = [_parse_fixture(m) for m in matches]
    fixtures.sort(key=lambda f: f.utc_date)

    _fixtures_cache = fixtures
    _fixtures_cache_ts = time.monotonic()
    return fixtures


async def get_standings_bl2() -> list[dict]:
    """
    Fetch current BL2 standings. Cached for 5 minutes.
    Shape matches football_data.get_standings() so table.py's logic can be mirrored as-is.
    OpenLigaDB's table endpoint has no explicit "form" field, so it's left absent here --
    callers should fall back to computing form from match results, same as table.py already
    does for football-data.org when the API's form field is empty.
    """
    global _standings_cache, _standings_cache_ts
    if _standings_cache is not None and (time.monotonic() - _standings_cache_ts) < _STANDINGS_TTL:
        return _standings_cache

    url = f"{OPENLIGA_BASE}/getbltable/{LEAGUE_SHORTCUT}/{_current_season()}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, timeout=15)
        resp.raise_for_status()
    table = resp.json()

    result = [
        {
            "position": i + 1,
            "team_id": row["teamInfoId"],
            "team_name": row["teamName"],
            "team_short_name": row.get("shortName", row["teamName"]),
            "team_crest": row.get("teamIconUrl"),
            "played": row["matches"],
            "won": row["won"],
            "draw": row["draw"],
            "lost": row["lost"],
            "goals_for": row["goals"],
            "goals_against": row["opponentGoals"],
            "goal_difference": row["goalDiff"],
            "points": row["points"],
            "form": "",
        }
        for i, row in enumerate(table)
    ]
    _standings_cache = result
    _standings_cache_ts = time.monotonic()
    return result
