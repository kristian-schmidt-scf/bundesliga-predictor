"""
Loads pre-scraped Bundesliga historical match data from data/bundesliga_historical.json.
Run backend/scripts/scrape_bundesliga_history.py once to generate the file.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).parent.parent.parent / "data" / "bundesliga_historical.json"


def load_historical_data() -> list[dict]:
    """
    Return pre-scraped historical matches, or an empty list if the file doesn't exist.
    Format matches get_historical_results(): home_team, away_team, home_goals, away_goals, date.
    """
    if not _DATA_PATH.exists():
        logger.info("No historical data file found at %s — using API data only", _DATA_PATH)
        return []

    with open(_DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)

    logger.info("Loaded %d historical matches from %s", len(data), _DATA_PATH.name)
    return data
