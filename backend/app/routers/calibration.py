import math
from collections import defaultdict
from fastapi import APIRouter
from app.services import football_data, prediction_cache
from app.services.dixon_coles import get_model
from app.models.schemas import (
    CalibrationResult, CalibrationMatchday, CalibrationBucket, CalibrationVariant
)

router = APIRouter(prefix="/calibration", tags=["calibration"])

BUCKET_SIZE = 0.1
N_BUCKETS = 10
BLEND_ALPHA = 0.5


def _tendency(p_h, p_d, p_a):
    if p_h >= p_d and p_h >= p_a: return 'H'
    if p_a >= p_d: return 'A'
    return 'D'


def _actual_tendency(home_score, away_score):
    if home_score > away_score: return 'H'
    if away_score > home_score: return 'A'
    return 'D'


def _metrics(records):
    bs_list, ll_list, correct = [], [], []
    for r in records:
        p_h, p_d, p_a, actual = r["p_h"], r["p_d"], r["p_a"], r["actual"]
        i_h = 1.0 if actual == 'H' else 0.0
        i_d = 1.0 if actual == 'D' else 0.0
        i_a = 1.0 if actual == 'A' else 0.0
        bs_list.append((p_h - i_h)**2 + (p_d - i_d)**2 + (p_a - i_a)**2)
        p_act = p_h if actual == 'H' else (p_d if actual == 'D' else p_a)
        ll_list.append(-math.log(max(p_act, 1e-10)))
        correct.append(1 if _tendency(p_h, p_d, p_a) == actual else 0)
    n = len(records)
    return {
        "brier_score": round(sum(bs_list) / n, 4),
        "log_loss":    round(sum(ll_list) / n, 4),
        "tendency_accuracy": round(sum(correct) / n, 4),
    }


VARIANTS = [
    {
        "key": "full",
        "name": "Full model",
        "description": "Per-team γ + H2H adjustment + recent form",
        "use_team_gamma": True, "use_h2h": True, "use_form": True,
    },
    {
        "key": "no_h2h",
        "name": "No H2H",
        "description": "Per-team γ + form, H2H adjustment disabled",
        "use_team_gamma": True, "use_h2h": False, "use_form": True,
    },
    {
        "key": "no_form",
        "name": "No form",
        "description": "Per-team γ + H2H, recent form scaling disabled",
        "use_team_gamma": True, "use_h2h": True, "use_form": False,
    },
    {
        "key": "global_gamma",
        "name": "Global γ",
        "description": "Average home advantage for all teams (no per-team γ), H2H + form kept",
        "use_team_gamma": False, "use_h2h": True, "use_form": True,
    },
    {
        "key": "baseline",
        "name": "Baseline",
        "description": "Global γ, no H2H, no form — plain Dixon-Coles",
        "use_team_gamma": False, "use_h2h": False, "use_form": False,
    },
    {
        "key": "blend",
        "name": "+ Bookmaker blend",
        "description": "Full model blended 50/50 with bookmaker implied probs (requires cached odds)",
        "use_team_gamma": True, "use_h2h": True, "use_form": True,
    },
    {
        "key": "bookmaker",
        "name": "Bookmaker only",
        "description": "Normalised bookmaker implied probabilities — the market alone (requires cached odds)",
        "use_team_gamma": True, "use_h2h": True, "use_form": True,
    },
]


@router.get("", response_model=CalibrationResult)
async def get_calibration():
    model = get_model()
    fixtures = await football_data.get_current_and_upcoming_fixtures()
    finished = [
        f for f in fixtures
        if f.status == 'FINISHED'
        and f.home_score is not None
        and f.away_score is not None
    ]

    base_records = []
    day_records: dict[int, list] = defaultdict(list)
    variant_records = {v["key"]: [] for v in VARIANTS}

    for fixture in finished:
        home, away = fixture.home_team.name, fixture.away_team.name
        actual = _actual_tendency(fixture.home_score, fixture.away_score)
        cached = prediction_cache.get(fixture.id)

        # Full model — prefer cache (pre-kickoff probs), fall back to recompute
        if cached:
            wp = cached.win_probabilities
            full_rec = {"p_h": wp.home_win, "p_d": wp.draw, "p_a": wp.away_win, "actual": actual}
        else:
            try:
                pred = model.predict(home, away, use_team_gamma=True, use_h2h=True, use_form=True)
                full_rec = {"p_h": pred["home_win"], "p_d": pred["draw"], "p_a": pred["away_win"], "actual": actual}
            except Exception:
                continue

        base_records.append(full_rec)
        day_records[fixture.matchday].append(full_rec)  # built from base_records, not cache-only

        # Ablation variants
        for v in VARIANTS:
            if v["key"] in ("blend", "bookmaker"):
                # These require cached odds — only available if predictions were cached before kickoff
                odds = cached.odds if cached else None
                if odds and odds.implied_home_prob:
                    imp_h, imp_d, imp_a = odds.implied_home_prob, odds.implied_draw_prob, odds.implied_away_prob
                    if v["key"] == "blend":
                        p_h = BLEND_ALPHA * full_rec["p_h"] + (1 - BLEND_ALPHA) * imp_h
                        p_d = BLEND_ALPHA * full_rec["p_d"] + (1 - BLEND_ALPHA) * imp_d
                        p_a = BLEND_ALPHA * full_rec["p_a"] + (1 - BLEND_ALPHA) * imp_a
                    else:
                        p_h, p_d, p_a = imp_h, imp_d, imp_a
                    variant_records[v["key"]].append({"p_h": p_h, "p_d": p_d, "p_a": p_a, "actual": actual})
            elif v["key"] == "full":
                variant_records["full"].append(full_rec)
            else:
                try:
                    pred = model.predict(
                        home, away,
                        use_team_gamma=v["use_team_gamma"],
                        use_h2h=v["use_h2h"],
                        use_form=v["use_form"],
                    )
                    variant_records[v["key"]].append({
                        "p_h": pred["home_win"], "p_d": pred["draw"],
                        "p_a": pred["away_win"], "actual": actual,
                    })
                except Exception:
                    pass

    if not base_records:
        return CalibrationResult(
            total_fixtures=0,
            brier_score=0.0, log_loss=0.0, tendency_accuracy=0.0,
            variants=[], per_matchday=[], calibration_curve=[],
        )

    full_metrics = _metrics(base_records)

    variants_out = []
    for v in VARIANTS:
        recs = variant_records[v["key"]]
        if not recs:
            continue
        m = _metrics(recs)
        variants_out.append(CalibrationVariant(
            name=v["name"],
            description=v["description"],
            fixtures=len(recs),
            brier_score=m["brier_score"],
            log_loss=m["log_loss"],
            tendency_accuracy=m["tendency_accuracy"],
        ))

    per_matchday = sorted([
        CalibrationMatchday(
            matchday=day,
            fixtures=len(recs),
            **_metrics(recs),
        )
        for day, recs in day_records.items()
        if recs
    ], key=lambda x: x.matchday)

    buckets: dict[int, list] = defaultdict(list)
    for rec in base_records:
        for prob, outcome in [(rec["p_h"], 'H'), (rec["p_d"], 'D'), (rec["p_a"], 'A')]:
            b = min(int(prob / BUCKET_SIZE), N_BUCKETS - 1)
            buckets[b].append((prob, 1 if rec["actual"] == outcome else 0))

    calibration_curve = [
        CalibrationBucket(
            bucket_min=round(b * BUCKET_SIZE, 1),
            bucket_max=round((b + 1) * BUCKET_SIZE, 1),
            predicted_mean=round(sum(p for p, _ in pts) / len(pts), 3),
            actual_frequency=round(sum(a for _, a in pts) / len(pts), 3),
            count=len(pts),
        )
        for b in range(N_BUCKETS)
        if (pts := buckets.get(b, []))
    ]

    return CalibrationResult(
        total_fixtures=len(base_records),
        variants=variants_out,
        per_matchday=per_matchday,
        calibration_curve=calibration_curve,
        **full_metrics,
    )
