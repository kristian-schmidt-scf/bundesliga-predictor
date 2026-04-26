"""
Walk-forward backtest across all finished Spieltage of the current season.

For each finished matchday N:
  - Training data = full historical data + current season Spieltage 1..(N-1)
  - Fit a fresh DixonColesModel (no lookahead)
  - Predict each fixture in Spieltag N
  - Score: Brier, log-loss, tendency accuracy, Tipp 11 expected vs actual

Computed once as a background task on startup; cached in memory.
"""

import math
import logging
from app.services import football_data
from app.services.dixon_coles import DixonColesModel
from app.config import settings

logger = logging.getLogger(__name__)

_cache: dict | None = None
_computing: bool = False
_attempted: bool = False

# Startup data stored here so the lazy trigger makes zero API calls
_prefetched_historical: list[dict] | None = None
_prefetched_current:    list[dict] | None = None


def set_prefetched_data(historical: list[dict], current_all: list[dict]) -> None:
    global _prefetched_historical, _prefetched_current
    _prefetched_historical = historical
    _prefetched_current    = current_all


# ---------------------------------------------------------------------------
# Tipp 11 helpers (mirror of frontend utils/tipp11.js)
# ---------------------------------------------------------------------------

def _tendency(h: int, a: int) -> str:
    if h > a: return 'H'
    if a > h: return 'A'
    return 'D'


def _tipp11_points(h_tip: int, a_tip: int, h_act: int, a_act: int) -> int:
    tip_tend = _tendency(h_tip, a_tip)
    act_tend = _tendency(h_act, a_act)
    pts = 0
    if h_tip == h_act: pts += 1
    if a_tip == a_act: pts += 1
    if tip_tend == act_tend:
        pts += 2
        if h_tip - a_tip == h_act - a_act: pts += 2
        pts += max(0, 5 - abs(h_tip - h_act) - abs(a_tip - a_act))
    return pts


def _best_tipp11_tip(matrix: list[list[float]]) -> tuple[int, int, float]:
    """Find (h_tip, a_tip, expected_pts) maximising expected Tipp 11 points."""
    size = len(matrix)
    best = (0, 0, -1.0)
    for h_tip in range(size):
        for a_tip in range(size):
            exp = sum(
                matrix[h_act][a_act] * _tipp11_points(h_tip, a_tip, h_act, a_act)
                for h_act in range(size)
                for a_act in range(size)
            )
            if exp > best[2]:
                best = (h_tip, a_tip, exp)
    return best


# ---------------------------------------------------------------------------
# Core backtest computation
# ---------------------------------------------------------------------------

async def compute_backtest(
    historical: list[dict] | None = None,
    current_all: list[dict] | None = None,
) -> None:
    global _attempted
    _attempted = True
    """
    Run walk-forward backtest and store result in module cache.
    Uses only historical + current_all (both available from startup data),
    making zero additional API calls.
    """
    global _cache, _computing
    _computing = True

    try:
        if historical is None:
            historical = _prefetched_historical
        if current_all is None:
            current_all = _prefetched_current
        # Only fall back to API if prefetched data wasn't set (shouldn't happen in normal startup)
        if historical is None:
            historical = await football_data.get_historical_results(settings.seasons_to_fetch)
        if current_all is None:
            current_all = await football_data.get_current_season_results()

        # All matchdays that have at least one finished result, in order
        finished_matchdays = sorted(set(
            r["matchday"] for r in current_all
            if r.get("matchday") is not None
            and r.get("home_goals") is not None
            and r.get("away_goals") is not None
        ))

        logger.info(
            "=== Backtest: walk-forward over %d finished Spieltage (%s–%s) ===",
            len(finished_matchdays),
            finished_matchdays[0] if finished_matchdays else "?",
            finished_matchdays[-1] if finished_matchdays else "?",
        )

        per_matchday = []

        for spieltag in finished_matchdays:
            # Finished fixtures for this spieltag come from current_all
            finished = [
                r for r in current_all
                if r.get("matchday") == spieltag
                and r.get("home_goals") is not None
                and r.get("away_goals") is not None
            ]
            if not finished:
                continue

            # Training data: history + current season games played before this spieltag
            current_train = [r for r in current_all if r.get("matchday", 0) < spieltag]
            train_data = historical + current_train

            model = DixonColesModel()
            try:
                model.fit(train_data)
                logger.info(f"Backtest: Spieltag {spieltag} fitted ({len(train_data)} matches)")
            except Exception as e:
                logger.warning(f"Backtest: Spieltag {spieltag} fit failed: {e}")
                continue

            brier_list, ll_list, correct = [], [], []
            t11_exp_total = t11_act_total = 0.0

            for r in finished:
                home, away = r["home_team"], r["away_team"]
                h_act, a_act = int(r["home_goals"]), int(r["away_goals"])
                actual = _tendency(h_act, a_act)

                try:
                    pred = model.predict(home, away, fixture_date=r["date"])
                except Exception:
                    continue

                p_h, p_d, p_a = pred["home_win"], pred["draw"], pred["away_win"]
                i_h = 1.0 if actual == 'H' else 0.0
                i_d = 1.0 if actual == 'D' else 0.0
                i_a = 1.0 if actual == 'A' else 0.0
                brier_list.append((p_h-i_h)**2 + (p_d-i_d)**2 + (p_a-i_a)**2)
                p_act = p_h if actual == 'H' else (p_d if actual == 'D' else p_a)
                ll_list.append(-math.log(max(p_act, 1e-10)))
                pred_tend = 'H' if p_h >= p_d and p_h >= p_a else ('A' if p_a > p_d else 'D')
                correct.append(1 if pred_tend == actual else 0)

                h_tip, a_tip, exp_pts = _best_tipp11_tip(pred["score_matrix"])
                t11_exp_total += exp_pts
                t11_act_total += _tipp11_points(h_tip, a_tip, h_act, a_act)

            if not brier_list:
                continue

            n = len(brier_list)
            per_matchday.append({
                "matchday":          spieltag,
                "fixtures":          n,
                "brier_score":       round(sum(brier_list) / n, 4),
                "log_loss":          round(sum(ll_list) / n, 4),
                "tendency_accuracy": round(sum(correct) / n, 4),
                "tipp11_expected":   round(t11_exp_total, 2),
                "tipp11_actual":     round(t11_act_total, 2),
            })

        if per_matchday:
            agg_n = len(per_matchday)
            _cache = {
                "status":             "ready",
                "matchdays_tested":   agg_n,
                "brier_score":        round(sum(m["brier_score"]       for m in per_matchday) / agg_n, 4),
                "log_loss":           round(sum(m["log_loss"]          for m in per_matchday) / agg_n, 4),
                "tendency_accuracy":  round(sum(m["tendency_accuracy"] for m in per_matchday) / agg_n, 4),
                "tipp11_expected":    round(sum(m["tipp11_expected"]   for m in per_matchday), 1),
                "tipp11_actual":      round(sum(m["tipp11_actual"]     for m in per_matchday), 1),
                "per_matchday":       per_matchday,
            }
        else:
            _cache = {"status": "unavailable", "matchdays_tested": 0, "per_matchday": []}

        logger.info(f"=== Backtest complete: {len(per_matchday)} matchdays scored ===")

    except Exception as e:
        logger.error(f"Backtest failed: {e}")
        _cache = {"status": "unavailable", "matchdays_tested": 0, "per_matchday": []}
    finally:
        _computing = False


def get_result() -> dict:
    if _computing:
        return {"status": "computing", "matchdays_tested": 0, "per_matchday": []}
    if _cache is None:
        return {"status": "unavailable", "matchdays_tested": 0, "per_matchday": []}
    return _cache
