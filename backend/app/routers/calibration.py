import math
from collections import defaultdict
from fastapi import APIRouter
from app.services import football_data, prediction_cache
from app.models.schemas import CalibrationResult, CalibrationMatchday, CalibrationBucket

router = APIRouter(prefix="/calibration", tags=["calibration"])

BUCKET_SIZE = 0.1
N_BUCKETS = 10


def _tendency(home_win: float, draw: float, away_win: float) -> str:
    if home_win >= draw and home_win >= away_win:
        return 'H'
    if away_win >= draw:
        return 'A'
    return 'D'


def _actual_tendency(home_score: int, away_score: int) -> str:
    if home_score > away_score:
        return 'H'
    if away_score > home_score:
        return 'A'
    return 'D'


@router.get("", response_model=CalibrationResult)
async def get_calibration():
    """
    Computes calibration metrics for all finished fixtures that have a
    cached pre-kickoff prediction. Metrics are computed against the
    probabilities the model assigned *before* the match started.
    """
    fixtures = await football_data.get_current_and_upcoming_fixtures()
    finished = [
        f for f in fixtures
        if f.status == 'FINISHED'
        and f.home_score is not None
        and f.away_score is not None
    ]

    records = []
    for fixture in finished:
        cached = prediction_cache.get(fixture.id)
        if cached is None:
            continue
        wp = cached.win_probabilities
        actual = _actual_tendency(fixture.home_score, fixture.away_score)
        records.append({
            "matchday": fixture.matchday,
            "p_home": wp.home_win,
            "p_draw": wp.draw,
            "p_away": wp.away_win,
            "actual": actual,
        })

    if not records:
        return CalibrationResult(
            total_fixtures=0,
            brier_score=0.0,
            log_loss=0.0,
            tendency_accuracy=0.0,
            per_matchday=[],
            calibration_curve=[],
        )

    # --- Aggregate metrics ---
    brier_scores, log_losses, correct = [], [], []
    for r in records:
        i_h = 1.0 if r["actual"] == 'H' else 0.0
        i_d = 1.0 if r["actual"] == 'D' else 0.0
        i_a = 1.0 if r["actual"] == 'A' else 0.0

        brier_scores.append(
            (r["p_home"] - i_h) ** 2 +
            (r["p_draw"] - i_d) ** 2 +
            (r["p_away"] - i_a) ** 2
        )

        p_actual = r["p_home"] if r["actual"] == 'H' else (
            r["p_draw"] if r["actual"] == 'D' else r["p_away"]
        )
        log_losses.append(-math.log(max(p_actual, 1e-10)))

        predicted = _tendency(r["p_home"], r["p_draw"], r["p_away"])
        correct.append(1 if predicted == r["actual"] else 0)

    # --- Per-matchday ---
    by_day: dict[int, list] = defaultdict(list)
    for r, bs, ll, c in zip(records, brier_scores, log_losses, correct):
        by_day[r["matchday"]].append((bs, ll, c))

    per_matchday = sorted([
        CalibrationMatchday(
            matchday=day,
            fixtures=len(vals),
            brier_score=round(sum(v[0] for v in vals) / len(vals), 4),
            log_loss=round(sum(v[1] for v in vals) / len(vals), 4),
            tendency_accuracy=round(sum(v[2] for v in vals) / len(vals), 4),
        )
        for day, vals in by_day.items()
    ], key=lambda x: x.matchday)

    # --- Calibration curve ---
    # Each outcome of each fixture contributes a (predicted_prob, is_actual) point
    buckets: dict[int, list] = defaultdict(list)
    for r in records:
        for prob, outcome in [
            (r["p_home"], 'H'),
            (r["p_draw"],  'D'),
            (r["p_away"],  'A'),
        ]:
            bucket = min(int(prob / BUCKET_SIZE), N_BUCKETS - 1)
            buckets[bucket].append((prob, 1 if r["actual"] == outcome else 0))

    calibration_curve = []
    for b in range(N_BUCKETS):
        pts = buckets.get(b, [])
        if not pts:
            continue
        calibration_curve.append(CalibrationBucket(
            bucket_min=round(b * BUCKET_SIZE, 1),
            bucket_max=round((b + 1) * BUCKET_SIZE, 1),
            predicted_mean=round(sum(p for p, _ in pts) / len(pts), 3),
            actual_frequency=round(sum(a for _, a in pts) / len(pts), 3),
            count=len(pts),
        ))

    n = len(records)
    return CalibrationResult(
        total_fixtures=n,
        brier_score=round(sum(brier_scores) / n, 4),
        log_loss=round(sum(log_losses) / n, 4),
        tendency_accuracy=round(sum(correct) / n, 4),
        per_matchday=per_matchday,
        calibration_curve=calibration_curve,
    )
