"""
Odds snapshot store with SQLite persistence.

The in-memory dict is the read path (fast, no DB round-trips on every
/api/odds/history request). SQLite is the write path and the source of
truth on restart — the in-memory dict is rebuilt from the DB in init().

Schema
------
odds_snapshots(fixture_id INTEGER, timestamp TEXT, home_win REAL,
               draw REAL, away_win REAL, implied_home_prob REAL,
               implied_draw_prob REAL, implied_away_prob REAL)
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from app.models.schemas import MatchOdds, OddsSnapshot
import logging

logger = logging.getLogger(__name__)

_snapshots: dict[int, list[OddsSnapshot]] = {}
_db_path: Path | None = None


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(_db_path, check_same_thread=False)


def init(db_path: str | Path) -> None:
    """Create the DB + table if needed, then load existing snapshots into memory."""
    global _db_path
    _db_path = Path(db_path)
    _db_path.parent.mkdir(parents=True, exist_ok=True)

    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS odds_snapshots (
                fixture_id      INTEGER NOT NULL,
                timestamp       TEXT    NOT NULL,
                home_win        REAL,
                draw            REAL,
                away_win        REAL,
                implied_home_prob REAL,
                implied_draw_prob REAL,
                implied_away_prob REAL
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_fixture ON odds_snapshots(fixture_id)")

    _load_from_db()
    logger.info("Odds history DB ready at %s (%d fixtures loaded)", _db_path, len(_snapshots))


def _load_from_db() -> None:
    _snapshots.clear()
    with _conn() as con:
        rows = con.execute(
            "SELECT fixture_id, timestamp, home_win, draw, away_win, "
            "implied_home_prob, implied_draw_prob, implied_away_prob "
            "FROM odds_snapshots ORDER BY timestamp ASC"
        ).fetchall()
    for row in rows:
        fid = int(row[0])
        snap = OddsSnapshot(
            timestamp=row[1],
            home_win=row[2],
            draw=row[3],
            away_win=row[4],
            implied_home_prob=row[5],
            implied_draw_prob=row[6],
            implied_away_prob=row[7],
        )
        _snapshots.setdefault(fid, []).append(snap)


def record_snapshot(fixture_id: int, odds: MatchOdds) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    snap = OddsSnapshot(
        timestamp=ts,
        home_win=odds.home_win,
        draw=odds.draw,
        away_win=odds.away_win,
        implied_home_prob=odds.implied_home_prob,
        implied_draw_prob=odds.implied_draw_prob,
        implied_away_prob=odds.implied_away_prob,
    )
    _snapshots.setdefault(fixture_id, []).append(snap)

    if _db_path is not None:
        with _conn() as con:
            con.execute(
                "INSERT INTO odds_snapshots VALUES (?,?,?,?,?,?,?,?)",
                (fixture_id, ts, odds.home_win, odds.draw, odds.away_win,
                 odds.implied_home_prob, odds.implied_draw_prob, odds.implied_away_prob),
            )


def get_history(fixture_id: int) -> list[OddsSnapshot]:
    return _snapshots.get(fixture_id, [])


def prune(fixture_ids: set[int]) -> None:
    """Remove snapshot history for settled fixtures from memory and DB."""
    removed = 0
    for fid in fixture_ids:
        if fid in _snapshots:
            del _snapshots[fid]
            removed += 1

    if removed and _db_path is not None:
        with _conn() as con:
            con.execute(
                f"DELETE FROM odds_snapshots WHERE fixture_id IN ({','.join('?' * len(fixture_ids))})",
                list(fixture_ids),
            )
        logger.info("Pruned odds history for %d settled fixtures", removed)
