import asyncio
from fastapi import APIRouter, HTTPException
from app.services import football_data, odds, prediction_cache
from app.services import prediction_cache_bayes
from app.services.dixon_coles import get_model, get_model_bayes
from app.models.schemas import Prediction, ScoreMatrix, WinProbabilities
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/predictions", tags=["predictions"])

LIVE_STATUSES = {"IN_PLAY", "PAUSED", "LIVE"}
FINISHED_STATUSES = {"FINISHED", "AWARDED"}


def _build_prediction(fixture, pred, match_odds) -> Prediction:
    home = fixture.home_team.name
    away = fixture.away_team.name
    edge_home = edge_draw = edge_away = None
    if match_odds:
        edge_home = round(pred["home_win"] - (match_odds.implied_home_prob or 0), 4)
        edge_draw = round(pred["draw"] - (match_odds.implied_draw_prob or 0), 4)
        edge_away = round(pred["away_win"] - (match_odds.implied_away_prob or 0), 4)
    return Prediction(
        fixture=fixture,
        score_matrix=ScoreMatrix(
            matrix=pred["score_matrix"],
            max_goals=pred["max_goals"],
            home_team=home,
            away_team=away,
        ),
        win_probabilities=WinProbabilities(
            home_win=pred["home_win"],
            draw=pred["draw"],
            away_win=pred["away_win"],
        ),
        expected_home_goals=pred["expected_home_goals"],
        expected_away_goals=pred["expected_away_goals"],
        most_likely_score=pred["most_likely_score"],
        odds=match_odds,
        edge_home_win=edge_home,
        edge_draw=edge_draw,
        edge_away_win=edge_away,
        rest_days_home=pred.get("rest_days_home"),
        rest_days_away=pred.get("rest_days_away"),
        rest_factor_home=pred.get("rest_factor_home"),
        rest_factor_away=pred.get("rest_factor_away"),
        travel_km=pred.get("travel_km"),
        travel_factor=pred.get("travel_factor"),
    )


@router.get("/upcoming", response_model=list[Prediction])
async def get_predictions_for_upcoming_fixtures(model_variant: str = "base"):
    """
    Returns Dixon-Coles predictions for current and upcoming Bundesliga fixtures.
    Use ?model_variant=bayes to serve from the Bayesian prior model.
    Predictions for live/finished games are served from cache (frozen at kickoff).
    """
    use_bayes = model_variant == "bayes"
    model = get_model_bayes() if use_bayes else get_model()
    cache = prediction_cache_bayes if use_bayes else prediction_cache
    if not model.fitted:
        raise HTTPException(
            status_code=503,
            detail="Model not yet fitted. Try again in a moment — fitting runs on startup.",
        )

    fixtures, odds_map = await asyncio.gather(
        football_data.get_current_and_upcoming_fixtures(),
        odds.get_bundesliga_odds(),
    )

    predictions = []
    for fixture in fixtures:
        home = fixture.home_team.name
        away = fixture.away_team.name
        is_settled = fixture.status in LIVE_STATUSES | FINISHED_STATUSES

        # Serve from cache for live/finished games so the prediction is frozen
        # at the last pre-kickoff value. Fall through to compute if cache is cold.
        if is_settled:
            cached = cache.get(fixture.id)
            if cached:
                predictions.append(cached.model_copy(update={"fixture": fixture}))
                continue

        try:
            pred = model.predict(home, away, fixture_date=fixture.utc_date.isoformat())
        except Exception as e:
            logger.warning(f"Prediction failed for {home} vs {away}: {e}")
            continue

        match_odds = odds.find_odds_for_fixture(odds_map, home, away)
        prediction = _build_prediction(fixture, pred, match_odds)

        cache.set(fixture.id, prediction)
        predictions.append(prediction)

    return predictions


@router.get("/match", response_model=Prediction)
async def get_prediction_for_match(home_team: str, away_team: str, fixture_date: str | None = None):
    """
    Get a prediction for a specific match by team names.
    Useful for ad-hoc queries during development.
    """
    model = get_model()
    if not model.fitted:
        raise HTTPException(status_code=503, detail="Model not yet fitted.")

    try:
        pred = model.predict(home_team, away_team, fixture_date=fixture_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    odds_map = await odds.get_bundesliga_odds()
    match_odds = odds.find_odds_for_fixture(odds_map, home_team, away_team)

    edge_home = edge_draw = edge_away = None
    if match_odds:
        edge_home = round(pred["home_win"] - (match_odds.implied_home_prob or 0), 4)
        edge_draw = round(pred["draw"] - (match_odds.implied_draw_prob or 0), 4)
        edge_away = round(pred["away_win"] - (match_odds.implied_away_prob or 0), 4)

    # Minimal fixture shell for ad-hoc queries
    from app.models.schemas import Fixture, Team
    from datetime import datetime, timezone
    dummy_fixture = Fixture(
        id=0,
        home_team=Team(id=0, name=home_team, short_name=home_team),
        away_team=Team(id=0, name=away_team, short_name=away_team),
        utc_date=datetime.now(timezone.utc),
        matchday=0,
        status="UNKNOWN",
    )

    return Prediction(
        fixture=dummy_fixture,
        score_matrix=ScoreMatrix(
            matrix=pred["score_matrix"],
            max_goals=pred["max_goals"],
            home_team=home_team,
            away_team=away_team,
        ),
        win_probabilities=WinProbabilities(
            home_win=pred["home_win"],
            draw=pred["draw"],
            away_win=pred["away_win"],
        ),
        expected_home_goals=pred["expected_home_goals"],
        expected_away_goals=pred["expected_away_goals"],
        most_likely_score=pred["most_likely_score"],
        odds=match_odds,
        edge_home_win=edge_home,
        edge_draw=edge_draw,
        edge_away_win=edge_away,
        rest_days_home=pred.get("rest_days_home"),
        rest_days_away=pred.get("rest_days_away"),
        rest_factor_home=pred.get("rest_factor_home"),
        rest_factor_away=pred.get("rest_factor_away"),
        travel_km=pred.get("travel_km"),
        travel_factor=pred.get("travel_factor"),
    )
