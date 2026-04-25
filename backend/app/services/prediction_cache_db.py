"""
SQLite-backed prediction cache.

Predictions for live/finished fixtures are frozen at their first
computation (pre-kickoff) and must survive server restarts so that a
post-match model refit cannot alter the stored tip.

Two singleton instances are created at module level — one per model
variant — and the existing prediction_cache / prediction_cache_bayes
shim modules delegate to them.
"""

import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.models.schemas import Prediction

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
            CREATE TABLE IF NOT EXISTS prediction_cache (
                fixture_id  INTEGER NOT NULL,
                variant     TEXT    NOT NULL,
                prediction  TEXT    NOT NULL,
                frozen_at   TEXT    NOT NULL,
                PRIMARY KEY (fixture_id, variant)
            )
        """)
    logger.info("Prediction cache DB ready at %s", _db_path)

    # Warm every in-memory cache from the persisted rows
    for instance in _instances.values():
        instance._load()


class PredictionCache:
    def __init__(self, variant: str) -> None:
        self._variant = variant
        self._mem: dict[int, Prediction] = {}

    def _load(self) -> None:
        """Load all rows for this variant from SQLite into memory."""
        if _db_path is None:
            return
        with _conn() as con:
            rows = con.execute(
                "SELECT fixture_id, prediction FROM prediction_cache WHERE variant = ?",
                (self._variant,),
            ).fetchall()
        loaded = 0
        for fixture_id, blob in rows:
            try:
                self._mem[fixture_id] = Prediction.model_validate_json(blob)
                loaded += 1
            except Exception as e:
                logger.warning("Skipping corrupt cache row fixture_id=%d: %s", fixture_id, e)
        if loaded:
            logger.info("Loaded %d cached %s predictions from DB", loaded, self._variant)

    def get(self, fixture_id: int) -> Prediction | None:
        return self._mem.get(fixture_id)

    def set(self, fixture_id: int, prediction: Prediction) -> None:
        self._mem[fixture_id] = prediction
        if _db_path is None:
            return
        blob = prediction.model_dump_json()
        frozen_at = datetime.now(timezone.utc).isoformat()
        with _conn() as con:
            con.execute(
                """
                INSERT INTO prediction_cache (fixture_id, variant, prediction, frozen_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(fixture_id, variant) DO NOTHING
                """,
                (fixture_id, self._variant, blob, frozen_at),
            )

    def get_all(self) -> dict[int, Prediction]:
        return dict(self._mem)


# Module-level singletons — imported by the shim modules
_instances: dict[str, PredictionCache] = {}

base  = PredictionCache("base")
bayes = PredictionCache("bayes")

_instances["base"]  = base
_instances["bayes"] = bayes
