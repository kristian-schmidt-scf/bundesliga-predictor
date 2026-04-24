"""
Bundesliga Predictor — FastAPI backend
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.routers import fixtures, predictions, table, calibration, model_params, backtest as backtest_router, simulation as simulation_router, teams as teams_router
from app.services import backtest as backtest_service
import asyncio
from app.services.dixon_coles import get_model, get_model_bayes
from app.services.football_data import (
    get_historical_results, get_current_season_results, get_current_and_upcoming_fixtures
)
from app.services.historical_data import load_historical_data
from app.services.odds import get_bundesliga_odds, find_odds_for_fixture
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Keep strong references to background tasks so they aren't garbage-collected
_bg_tasks: set = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    On startup: fetch historical data and fit both the base and Bayesian-prior models.
    The Bayesian model uses current bookmaker odds as priors on attack/defence parameters.
    """
    logger.info("=== Startup: fitting Dixon-Coles models ===")
    try:
        static     = load_historical_data()
        historical = await get_historical_results(settings.seasons_to_fetch)
        current    = await get_current_season_results()

        # Merge static + API data; deduplicate by (date, home, away) so that
        # increasing seasons_to_fetch never causes duplicates with the static file.
        seen: set[tuple] = set()
        all_results: list[dict] = []
        for match in historical + current + static:
            key = (match["date"][:10], match["home_team"], match["away_team"])
            if key not in seen:
                seen.add(key)
                all_results.append(match)

        logger.info(
            "Training data: %d API matches + %d static historical = %d total (after dedup)",
            len(historical) + len(current), len(static), len(all_results),
        )

        # 1. Base model — no bookmaker prior
        model = get_model()
        model.fit(all_results)
        logger.info("=== Base model ready ===")

        # Store data for backtest lazy trigger — no extra API calls needed
        backtest_service.set_prefetched_data(historical, current)

        # 2. Bayesian model — use current bookmaker odds as MAP prior
        logger.info("=== Startup: fitting Bayesian prior model ===")
        try:
            upcoming_fixtures = await get_current_and_upcoming_fixtures()
            odds_map = await get_bundesliga_odds()

            odds_list = []
            for fixture in upcoming_fixtures:
                home = fixture.home_team.name
                away = fixture.away_team.name
                match_odds = find_odds_for_fixture(odds_map, home, away)
                if match_odds and match_odds.implied_home_prob:
                    odds_list.append({
                        "home_team": home,
                        "away_team": away,
                        "implied_home_prob": match_odds.implied_home_prob,
                        "implied_draw_prob": match_odds.implied_draw_prob,
                        "implied_away_prob": match_odds.implied_away_prob,
                    })

            model_bayes = get_model_bayes()
            model_bayes.fit_with_prior(all_results, odds_list)
            logger.info("=== Bayesian prior model ready ===")
        except Exception as e:
            logger.warning(f"Bayesian model fitting failed: {e} — Bayes predictions unavailable.")

        # Backtest is triggered lazily on first GET /api/backtest request

    except Exception as e:
        logger.error(f"Model fitting failed on startup: {e}")
        logger.warning("Server is running but predictions may be unavailable.")

    yield  # server runs here


app = FastAPI(
    title="Bundesliga Predictor API",
    description="Dixon-Coles Bayesian predictions for Bundesliga fixtures",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(fixtures.router, prefix="/api")
app.include_router(predictions.router, prefix="/api")
app.include_router(table.router, prefix="/api")
app.include_router(calibration.router, prefix="/api")
app.include_router(model_params.router, prefix="/api")
app.include_router(backtest_router.router, prefix="/api")
app.include_router(simulation_router.router, prefix="/api")
app.include_router(teams_router.router, prefix="/api")


@app.get("/api/health")
async def health():
    model = get_model()
    model_bayes = get_model_bayes()
    return {
        "status": "ok",
        "model_fitted": model.fitted,
        "model_bayes_fitted": model_bayes.fitted,
        "teams_in_model": len(model.teams) if model.fitted else 0,
    }
