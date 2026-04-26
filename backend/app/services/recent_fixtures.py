"""
Cross-competition recent fixture cache.

Extends the rest/fatigue computation in dixon_coles.py beyond Bundesliga
by pulling match dates from two free sources:

  1. football-data.org /teams/{id}/matches  — covers UCL, UEL, UECL
  2. OpenLigaDB                             — covers DFB-Pokal

Both are fetched in a background task (not on the hot path).
`get_most_recent_date()` is called synchronously at prediction time.
"""

import asyncio
import httpx
import time
import logging
from datetime import datetime, timezone, timedelta

from app.config import settings

logger = logging.getLogger(__name__)

FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
FOOTBALL_DATA_HEADERS = {"X-Auth-Token": settings.football_data_api_key}
OPENLIGADB_BASE = "https://api.openligadb.de"

# team_name -> sorted list of recent match datetimes (all competitions)
_match_dates: dict[str, list[datetime]] = {}
_cache_ts: float = 0.0


def get_most_recent_date(team_name: str, before: datetime) -> datetime | None:
    """
    Returns the most recent match datetime for a team before the given
    cutoff, across all tracked competitions.  Returns None if no data.
    """
    dates = _match_dates.get(team_name, [])
    prior = [d for d in dates if d < before]
    return max(prior) if prior else None


async def refresh(team_id_map: dict[str, int]) -> None:
    """
    Populate/refresh the cache.  Fetches the last 60 days of matches for
    every team from football-data.org (European comps) and the full
    current DFB-Pokal season from OpenLigaDB.

    Rate-limited to 10 req/min for football-data.org (7 s between calls).
    Safe to call in a background task.
    """
    global _match_dates, _cache_ts

    now = datetime.now(timezone.utc)
    date_from = (now - timedelta(days=60)).strftime("%Y-%m-%d")
    date_to = now.strftime("%Y-%m-%d")

    # Start from whatever is already cached so partial failures don't
    # wipe valid entries.
    new_dates: dict[str, list[datetime]] = {k: list(v) for k, v in _match_dates.items()}

    # ── 1. football-data.org team-level endpoint (European comps) ──────
    async with httpx.AsyncClient() as client:
        for idx, (team_name, team_id) in enumerate(team_id_map.items()):
            if idx > 0:
                await asyncio.sleep(7)  # stay under 10 req/min
            try:
                url = f"{FOOTBALL_DATA_BASE}/teams/{team_id}/matches"
                params = {"dateFrom": date_from, "dateTo": date_to, "status": "FINISHED"}
                resp = await client.get(
                    url, headers=FOOTBALL_DATA_HEADERS, params=params, timeout=10
                )
                if resp.status_code == 429:
                    wait = int(resp.headers.get("Retry-After", 60))
                    logger.warning("Rate limited; waiting %ds before retrying %s", wait, team_name)
                    await asyncio.sleep(wait)
                    resp = await client.get(
                        url, headers=FOOTBALL_DATA_HEADERS, params=params, timeout=10
                    )
                resp.raise_for_status()

                dates = [
                    datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
                    for m in resp.json().get("matches", [])
                ]
                new_dates[team_name] = sorted(set(new_dates.get(team_name, []) + dates))
                logger.debug("football-data.org: %d matches for %s", len(dates), team_name)

            except Exception as e:
                logger.warning("Failed to fetch recent matches for %s: %s", team_name, e)

    # ── 2. OpenLigaDB — DFB-Pokal ──────────────────────────────────────
    try:
        season_year = now.year if now.month >= 7 else now.year - 1
        url = f"{OPENLIGADB_BASE}/getmatchdata/dfb/{season_year}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=15)
            resp.raise_for_status()

        team_names = set(team_id_map.keys())
        for match in resp.json():
            if not match.get("matchIsFinished"):
                continue
            dt_str = match.get("matchDateTime", "")
            if not dt_str:
                continue
            try:
                dt = datetime.fromisoformat(dt_str)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            for raw_name in (match.get("team1", {}).get("teamName", ""),
                             match.get("team2", {}).get("teamName", "")):
                matched = _fuzzy_match(raw_name, team_names)
                if matched:
                    existing = new_dates.get(matched, [])
                    if dt not in existing:
                        existing.append(dt)
                        new_dates[matched] = sorted(existing)

        logger.info("OpenLigaDB DFB-Pokal data merged for season %d", season_year)

    except Exception as e:
        logger.warning("OpenLigaDB DFB-Pokal fetch failed: %s", e)

    _match_dates = new_dates
    _cache_ts = time.monotonic()
    logger.info("Recent fixtures cache refreshed for %d teams", len(new_dates))


def _fuzzy_match(raw: str, known_names: set[str]) -> str | None:
    """Loosely match an OpenLigaDB team name to a known football-data.org name."""
    raw_clean = _strip_prefixes(raw.lower())
    for name in known_names:
        name_clean = _strip_prefixes(name.lower())
        if raw_clean == name_clean:
            return name
        if raw_clean in name_clean or name_clean in raw_clean:
            return name
        if len(raw_clean) >= 4 and raw_clean[:4] == name_clean[:4]:
            return name
    return None


def _strip_prefixes(s: str) -> str:
    for prefix in ["fc ", "bv ", "sv ", "1. ", "vfb ", "vfl ", "tsg ", "sc ", "rb "]:
        s = s.replace(prefix, "")
    return s.strip()
