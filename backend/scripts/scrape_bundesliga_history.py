"""
One-time script: download Bundesliga historical data from football-data.co.uk
and save as backend/data/bundesliga_historical.json.

Usage (from backend/ directory with venv active):
    python scripts/scrape_bundesliga_history.py

Covers seasons 2016/17 through 2022/23 (7 seasons), which predates the
football-data.org free-tier API coverage (last 3 seasons). Combined with the
API data this gives ~10 seasons of training history.
"""

import csv
import io
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

SEASONS = [
    "2223",  # 2022/23
    "2122",  # 2021/22
    "2021",  # 2020/21
    "1920",  # 2019/20
    "1819",  # 2018/19
    "1718",  # 2017/18
    "1617",  # 2016/17
]

BASE_URL = "https://www.football-data.co.uk/mmz4281/{}/D1.csv"

# football-data.co.uk short names → football-data.org canonical names
TEAM_NAME_MAP: dict[str, str] = {
    "Bayern Munich":      "FC Bayern München",
    "Dortmund":           "Borussia Dortmund",
    "Leverkusen":         "Bayer 04 Leverkusen",
    "RB Leipzig":         "RB Leipzig",
    "Ein Frankfurt":      "Eintracht Frankfurt",
    "M'Gladbach":         "Borussia Mönchengladbach",
    "M'gladbach":         "Borussia Mönchengladbach",
    "Wolfsburg":          "VfL Wolfsburg",
    "Freiburg":           "SC Freiburg",
    "Stuttgart":          "VfB Stuttgart",
    "Hoffenheim":         "TSG 1899 Hoffenheim",
    "Augsburg":           "FC Augsburg",
    "Mainz":              "1. FSV Mainz 05",
    "Schalke 04":         "FC Schalke 04",
    "Hertha":             "Hertha BSC",
    "Bochum":             "VfL Bochum 1848",
    "Werder Bremen":      "SV Werder Bremen",
    "Union Berlin":       "1. FC Union Berlin",
    "Heidenheim":         "1. FC Heidenheim 1846",
    "Darmstadt":          "SV Darmstadt 98",
    "Cologne":            "1. FC Köln",
    "FC Koln":            "1. FC Köln",
    "Hamburg":            "Hamburger SV",
    "Paderborn":          "SC Paderborn 07",
    "Fortuna Dusseldorf": "Fortuna Düsseldorf",
    "Hannover":           "Hannover 96",
    "Nurnberg":           "1. FC Nürnberg",
    "Ingolstadt":         "FC Ingolstadt 04",
    "Greuther Furth":     "SpVgg Greuther Fürth",
    "Bielefeld":          "Arminia Bielefeld",
    "St Pauli":           "FC St. Pauli 1910",
    "Holstein Kiel":      "Holstein Kiel",
    "Braunschweig":       "Eintracht Braunschweig",
    "Kaiserslautern":     "1. FC Kaiserslautern",
}


def _parse_date(date_str: str) -> str:
    """Convert football-data.co.uk DD/MM/YY or DD/MM/YYYY to ISO-8601 UTC string."""
    s = date_str.strip()
    fmt = "%d/%m/%Y" if len(s) == 10 else "%d/%m/%y"
    dt = datetime.strptime(s, fmt)
    return dt.replace(hour=12, tzinfo=timezone.utc).isoformat()


def _fetch_season(season_code: str) -> list[dict]:
    url = BASE_URL.format(season_code)
    logger.info(f"Downloading {url}")
    try:
        with urlopen(url, timeout=30) as resp:
            raw = resp.read()
    except URLError as e:
        logger.error(f"  Failed to download: {e}")
        return []

    text = raw.decode("latin-1")
    reader = csv.DictReader(io.StringIO(text))

    results = []
    unmapped: set[str] = set()

    for row in reader:
        home_raw = row.get("HomeTeam", "").strip()
        away_raw = row.get("AwayTeam", "").strip()
        fthg = row.get("FTHG", "").strip()
        ftag = row.get("FTAG", "").strip()
        date_raw = row.get("Date", "").strip()

        if not all([home_raw, away_raw, fthg, ftag, date_raw]):
            continue

        try:
            home_goals = int(float(fthg))
            away_goals = int(float(ftag))
        except ValueError:
            continue

        home = TEAM_NAME_MAP.get(home_raw)
        away = TEAM_NAME_MAP.get(away_raw)

        if home is None:
            unmapped.add(home_raw)
        if away is None:
            unmapped.add(away_raw)
        if home is None or away is None:
            continue

        try:
            date_iso = _parse_date(date_raw)
        except ValueError:
            logger.warning(f"  Skipping unparseable date: {date_raw!r}")
            continue

        results.append({
            "home_team": home,
            "away_team": away,
            "home_goals": home_goals,
            "away_goals": away_goals,
            "date": date_iso,
        })

    if unmapped:
        logger.warning(f"  Unmapped team names (add to TEAM_NAME_MAP): {sorted(unmapped)}")

    logger.info(f"  {len(results)} matches parsed")
    return results


def main() -> None:
    all_results: list[dict] = []

    for i, season_code in enumerate(SEASONS):
        if i > 0:
            time.sleep(1.0)
        results = _fetch_season(season_code)
        all_results.extend(results)

    all_results.sort(key=lambda r: r["date"])

    out_path = Path(__file__).parent.parent / "data" / "bundesliga_historical.json"
    out_path.parent.mkdir(exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(all_results)} matches → {out_path}")


if __name__ == "__main__":
    main()
