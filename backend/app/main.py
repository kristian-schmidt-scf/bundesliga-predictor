"""
Bundesliga Predictor — FastAPI backend
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging

from app.routers import fixtures, predictions, table, calibration, model_params, backtest as backtest_router, simulation as simulation_router, teams as teams_router, h2h as h2h_router, odds as odds_router, picks as picks_router, clv as clv_router
from app.services import backtest as backtest_service
from app.services import odds_history, user_picks, prediction_cache_db
from app.services.dixon_coles import get_model, get_model_bayes
from app.services.football_data import (
    get_historical_results, get_current_season_results, get_current_and_upcoming_fixtures
)
from app.services.historical_data import load_historical_data
from app.services.odds import get_bundesliga_odds, find_odds_for_fixture
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_bg_tasks: set = set()


def _merge_results(historical: list[dict], current: list[dict], static: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    all_results: list[dict] = []
    for match in historical + current + static:
        key = (match["date"][:10], match["home_team"], match["away_team"])
        if key not in seen:
            seen.add(key)
            all_results.append(match)
    return all_results


async def _run_full_refit() -> list[dict]:
    """Fetch latest data and refit both the base and Bayesian models."""
    static     = load_historical_data()
    historical = await get_historical_results(settings.seasons_to_fetch)
    current    = await get_current_season_results()
    all_results = _merge_results(historical, current, static)

    logger.info("Refitting on %d matches", len(all_results))
    model = get_model()
    model.fit(all_results)
    logger.info("Base model refit complete")

    try:
        upcoming_fixtures = await get_current_and_upcoming_fixtures()
        odds_map = await get_bundesliga_odds(force_refresh=True)
        odds_list = _build_odds_list(upcoming_fixtures, odds_map)
        get_model_bayes().fit_with_prior(all_results, odds_list)
        logger.info("Bayesian prior model refit complete")
    except Exception as e:
        logger.warning("Bayesian model refit failed: %s", e)

    return all_results


def _build_odds_list(fixtures, odds_map) -> list[dict]:
    odds_list = []
    for fixture in fixtures:
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
    return odds_list


async def _snapshot_current_odds(fixtures, odds_map) -> None:
    """Record a snapshot for every upcoming fixture using an already-fetched odds_map."""
    count = 0
    for fixture in fixtures:
        if fixture.status in ("FINISHED", "AWARDED"):
            continue
        match_odds = find_odds_for_fixture(odds_map, fixture.home_team.name, fixture.away_team.name)
        if match_odds:
            odds_history.record_snapshot(fixture.id, match_odds)
            count += 1
    logger.info("Odds snapshots recorded for %d fixtures", count)


async def _poll_odds_and_snapshot() -> None:
    """Fetch fresh odds and record snapshots (called by the background poll loop)."""
    try:
        fixtures = await get_current_and_upcoming_fixtures()
        odds_map = await get_bundesliga_odds(force_refresh=True)
        await _snapshot_current_odds(fixtures, odds_map)
    except Exception as e:
        logger.warning("Odds snapshot poll failed: %s", e)


async def _daily_refit_loop() -> None:
    """Background task: refit models daily at the configured hour (default 06:00 local)."""
    while True:
        now = datetime.now()
        target = now.replace(hour=settings.refit_hour, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        delay = (target - now).total_seconds()
        logger.info("Next scheduled refit in %.1fh (at %02d:00)", delay / 3600, settings.refit_hour)
        await asyncio.sleep(delay)
        logger.info("=== Starting scheduled daily refit ===")
        try:
            await _run_full_refit()
        except Exception as e:
            logger.error("Scheduled refit failed: %s", e)


async def _odds_poll_loop() -> None:
    """Background task: snapshot odds every N seconds (default 2h)."""
    while True:
        await asyncio.sleep(settings.odds_poll_interval_seconds)
        logger.info("=== Polling odds snapshot ===")
        await _poll_odds_and_snapshot()


async def _pre_kickoff_snapshot_loop() -> None:
    """
    Capture the true closing line by snapshotting odds once per fixture in the
    90-minute window before kickoff.  Costs one Odds API call per batch of
    simultaneous kickoffs regardless of how many games start at once.
    """
    snapshotted: set[int] = set()
    while True:
        await asyncio.sleep(300)  # check every 5 minutes
        try:
            now = datetime.now(timezone.utc)
            fixtures = await get_current_and_upcoming_fixtures()
            due = [
                f for f in fixtures
                if f.id not in snapshotted
                and f.status == "SCHEDULED"
                and 5 <= (f.utc_date - now).total_seconds() / 60 <= 90
            ]
            if due:
                logger.info(
                    "Pre-kickoff snapshot: %d fixture(s) kick off within 90 min", len(due)
                )
                odds_map = await get_bundesliga_odds(force_refresh=True)
                await _snapshot_current_odds(fixtures, odds_map)
                for f in due:
                    snapshotted.add(f.id)
        except Exception as e:
            logger.warning("Pre-kickoff snapshot failed: %s", e)


def _start_background(coro) -> None:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from pathlib import Path
    odds_history.init(Path(__file__).parent.parent / settings.odds_db_path)
    user_picks.init(Path(__file__).parent.parent / settings.picks_db_path)
    prediction_cache_db.init(Path(__file__).parent.parent / settings.prediction_cache_db_path)

    logger.info("=== Startup: fitting Dixon-Coles models ===")
    try:
        static     = load_historical_data()
        historical = await get_historical_results(settings.seasons_to_fetch)
        current    = await get_current_season_results()
        all_results = _merge_results(historical, current, static)

        logger.info(
            "Training data: %d API matches + %d static historical = %d total (after dedup)",
            len(historical) + len(current), len(static), len(all_results),
        )

        model = get_model()
        model.fit(all_results)
        logger.info("=== Base model ready ===")

        backtest_service.set_prefetched_data(historical, current)

        logger.info("=== Startup: fitting Bayesian prior model ===")
        try:
            upcoming_fixtures = await get_current_and_upcoming_fixtures()
            odds_map = await get_bundesliga_odds()

            odds_list = _build_odds_list(upcoming_fixtures, odds_map)
            get_model_bayes().fit_with_prior(all_results, odds_list)
            logger.info("=== Bayesian prior model ready ===")

            # Seed the opening odds snapshots from this startup fetch (no extra API call)
            await _snapshot_current_odds(upcoming_fixtures, odds_map)
        except Exception as e:
            logger.warning("Bayesian model fitting failed: %s — Bayes predictions unavailable.", e)

    except Exception as e:
        logger.error("Model fitting failed on startup: %s", e)
        logger.warning("Server is running but predictions may be unavailable.")

    _start_background(_daily_refit_loop())
    _start_background(_odds_poll_loop())
    _start_background(_pre_kickoff_snapshot_loop())

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
app.include_router(h2h_router.router, prefix="/api")
app.include_router(odds_router.router, prefix="/api")
app.include_router(picks_router.router, prefix="/api")
app.include_router(clv_router.router, prefix="/api")


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
