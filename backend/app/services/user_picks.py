"""
SQLite store for user Tipp 11 picks.

One row per fixture (upsert on save). Persists across server restarts.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from app.models.schemas import UserPick
import logging

logger = logging.getLogger(__name__)

_db_path: Path | None = None


def _conn() -> sqlite3.Connection:
    return sqlite3.connect(_db_path, check_same_thread=False)


def init(db_path: str | Path) -> None:
    global _db_path
    _db_path = Path(db_path)
    _db_path.parent.mkdir(parents=True, exist_ok=True)

    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS user_picks (
                fixture_id   INTEGER PRIMARY KEY,
                matchday     INTEGER NOT NULL,
                home_team    TEXT    NOT NULL,
                away_team    TEXT    NOT NULL,
                picked_home  INTEGER NOT NULL,
                picked_away  INTEGER NOT NULL,
                saved_at     TEXT    NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS opponent_picks (
                fixture_id   INTEGER PRIMARY KEY,
                matchday     INTEGER NOT NULL,
                home_team    TEXT    NOT NULL,
                away_team    TEXT    NOT NULL,
                picked_home  INTEGER NOT NULL,
                picked_away  INTEGER NOT NULL,
                saved_at     TEXT    NOT NULL
            )
        """)
    logger.info("User picks DB ready at %s", _db_path)


def save_pick(fixture_id: int, matchday: int, home_team: str, away_team: str,
              picked_home: int, picked_away: int) -> UserPick:
    ts = datetime.now(timezone.utc).isoformat()
    with _conn() as con:
        con.execute("""
            INSERT INTO user_picks
                (fixture_id, matchday, home_team, away_team, picked_home, picked_away, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fixture_id) DO UPDATE SET
                matchday=excluded.matchday,
                home_team=excluded.home_team,
                away_team=excluded.away_team,
                picked_home=excluded.picked_home,
                picked_away=excluded.picked_away,
                saved_at=excluded.saved_at
        """, (fixture_id, matchday, home_team, away_team, picked_home, picked_away, ts))
    return UserPick(fixture_id=fixture_id, matchday=matchday, home_team=home_team,
                    away_team=away_team, picked_home=picked_home, picked_away=picked_away,
                    saved_at=ts)


def delete_pick(fixture_id: int) -> bool:
    with _conn() as con:
        cur = con.execute("DELETE FROM user_picks WHERE fixture_id = ?", (fixture_id,))
    return cur.rowcount > 0


def get_all_picks() -> list[UserPick]:
    with _conn() as con:
        rows = con.execute(
            "SELECT fixture_id, matchday, home_team, away_team, picked_home, picked_away, saved_at "
            "FROM user_picks ORDER BY matchday, fixture_id"
        ).fetchall()
    return [
        UserPick(fixture_id=r[0], matchday=r[1], home_team=r[2], away_team=r[3],
                 picked_home=r[4], picked_away=r[5], saved_at=r[6])
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Opponent picks (same schema, separate table)
# ---------------------------------------------------------------------------

def save_opponent_pick(fixture_id: int, matchday: int, home_team: str, away_team: str,
                       picked_home: int, picked_away: int) -> UserPick:
    ts = datetime.now(timezone.utc).isoformat()
    with _conn() as con:
        con.execute("""
            INSERT INTO opponent_picks
                (fixture_id, matchday, home_team, away_team, picked_home, picked_away, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fixture_id) DO UPDATE SET
                matchday=excluded.matchday,
                home_team=excluded.home_team,
                away_team=excluded.away_team,
                picked_home=excluded.picked_home,
                picked_away=excluded.picked_away,
                saved_at=excluded.saved_at
        """, (fixture_id, matchday, home_team, away_team, picked_home, picked_away, ts))
    return UserPick(fixture_id=fixture_id, matchday=matchday, home_team=home_team,
                    away_team=away_team, picked_home=picked_home, picked_away=picked_away,
                    saved_at=ts)


def delete_opponent_pick(fixture_id: int) -> bool:
    with _conn() as con:
        cur = con.execute("DELETE FROM opponent_picks WHERE fixture_id = ?", (fixture_id,))
    return cur.rowcount > 0


def get_all_opponent_picks() -> list[UserPick]:
    with _conn() as con:
        rows = con.execute(
            "SELECT fixture_id, matchday, home_team, away_team, picked_home, picked_away, saved_at "
            "FROM opponent_picks ORDER BY matchday, fixture_id"
        ).fetchall()
    return [
        UserPick(fixture_id=r[0], matchday=r[1], home_team=r[2], away_team=r[3],
                 picked_home=r[4], picked_away=r[5], saved_at=r[6])
        for r in rows
    ]
