"""
Bundesliga Predictor — FastAPI backend
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.routers import fixtures, predictions, table, calibration
from app.services.dixon_coles import get_model
from app.services.football_data import get_historical_results, get_current_season_results
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    On startup: fetch historical data and fit the Dixon-Coles model.
    This runs once when the server starts, so the first request is instant.
    """
    logger.info("=== Startup: fitting Dixon-Coles model ===")
    try:
        historical = await get_historical_results(settings.seasons_to_fetch)
        current = await get_current_season_results()
        all_results = historical + current

        model = get_model()
        model.fit(all_results)
        logger.info("=== Model ready ===")
    except Exception as e:
        logger.error(f"Model fitting failed on startup: {e}")
        logger.warning("Server is running but predictions will be unavailable until model is fitted.")

    yield  # server runs here


app = FastAPI(
    title="Bundesliga Predictor API",
    description="Dixon-Coles Bayesian predictions for Bundesliga fixtures",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the React dev server (port 5173) to call the API
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


@app.get("/api/health")
async def health():
    model = get_model()
    return {
        "status": "ok",
        "model_fitted": model.fitted,
        "teams_in_model": len(model.teams) if model.fitted else 0,
    }
