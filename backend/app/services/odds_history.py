"""
In-memory store for odds snapshots.

Snapshots are keyed by fixture_id. The first snapshot becomes the "opening"
odds; subsequent snapshots track movement. Records are pruned automatically
when the corresponding fixture is settled (no point tracking finished games).
"""

from datetime import datetime, timezone
from app.models.schemas import MatchOdds, OddsSnapshot
import logging

logger = logging.getLogger(__name__)

_snapshots: dict[int, list[OddsSnapshot]] = {}


def record_snapshot(fixture_id: int, odds: MatchOdds) -> None:
    snap = OddsSnapshot(
        timestamp=datetime.now(timezone.utc).isoformat(),
        home_win=odds.home_win,
        draw=odds.draw,
        away_win=odds.away_win,
        implied_home_prob=odds.implied_home_prob,
        implied_draw_prob=odds.implied_draw_prob,
        implied_away_prob=odds.implied_away_prob,
    )
    _snapshots.setdefault(fixture_id, []).append(snap)


def get_history(fixture_id: int) -> list[OddsSnapshot]:
    return _snapshots.get(fixture_id, [])


def prune(fixture_ids: set[int]) -> None:
    """Remove snapshot history for settled fixtures."""
    removed = 0
    for fid in fixture_ids:
        if fid in _snapshots:
            del _snapshots[fid]
            removed += 1
    if removed:
        logger.info("Pruned odds history for %d settled fixtures", removed)
