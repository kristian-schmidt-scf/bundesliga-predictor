from fastapi import APIRouter
from app.services import prediction_cache, prediction_cache_bayes, odds_history
from app.models.schemas import CLVEntry, CLVResponse

router = APIRouter(prefix="/clv", tags=["clv"])


@router.get("", response_model=CLVResponse)
async def get_clv(model_variant: str = "base"):
    """
    Closing line value for all settled fixtures.
    CLV = model implied probability - closing bookmaker implied probability.
    Positive CLV means the model assigned more probability than the market's
    final efficient price — the gold standard for a predictive edge.
    """
    cache = prediction_cache_bayes if model_variant == "bayes" else prediction_cache
    entries: list[CLVEntry] = []

    for fixture_id, pred in cache.get_all().items():
        fixture = pred.fixture
        if fixture.status not in ("FINISHED", "AWARDED"):
            continue

        wp = pred.win_probabilities
        probs = {"home": wp.home_win, "draw": wp.draw, "away": wp.away_win}
        best_outcome = max(probs, key=probs.__getitem__)

        kickoff = fixture.utc_date.isoformat()
        opening = odds_history.get_opening_snapshot(fixture_id)
        closing = odds_history.get_closing_snapshot(fixture_id, kickoff)

        open_h = opening.implied_home_prob if opening else None
        open_d = opening.implied_draw_prob if opening else None
        open_a = opening.implied_away_prob if opening else None

        close_h = closing.implied_home_prob if closing else None
        close_d = closing.implied_draw_prob if closing else None
        close_a = closing.implied_away_prob if closing else None

        clv_home = clv_draw = clv_away = best_clv = None
        if closing and close_h is not None:
            clv_home = round(wp.home_win - close_h, 4)
            clv_draw = round(wp.draw - close_d, 4)
            clv_away = round(wp.away_win - close_a, 4)
            best_clv = {"home": clv_home, "draw": clv_draw, "away": clv_away}[best_outcome]

        entries.append(CLVEntry(
            fixture_id=fixture_id,
            matchday=fixture.matchday,
            home_team=fixture.home_team.name,
            away_team=fixture.away_team.name,
            utc_date=kickoff,
            home_score=fixture.home_score,
            away_score=fixture.away_score,
            model_home_prob=round(wp.home_win, 4),
            model_draw_prob=round(wp.draw, 4),
            model_away_prob=round(wp.away_win, 4),
            opening_home_prob=open_h,
            opening_draw_prob=open_d,
            opening_away_prob=open_a,
            closing_home_prob=close_h,
            closing_draw_prob=close_d,
            closing_away_prob=close_a,
            clv_home=clv_home,
            clv_draw=clv_draw,
            clv_away=clv_away,
            best_outcome=best_outcome,
            best_clv=best_clv,
        ))

    entries.sort(key=lambda e: (e.matchday, e.utc_date))

    with_closing = [e for e in entries if e.best_clv is not None]
    avg_best_clv = (
        round(sum(e.best_clv for e in with_closing) / len(with_closing), 4)
        if with_closing else None
    )

    return CLVResponse(
        entries=entries,
        avg_best_clv=avg_best_clv,
        fixtures_with_closing=len(with_closing),
        fixtures_total=len(entries),
    )
