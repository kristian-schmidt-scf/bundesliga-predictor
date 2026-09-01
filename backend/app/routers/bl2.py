"""
2. Bundesliga endpoints.

Mirrors the logic of predictions.py / table.py / h2h.py / simulation.py for
the top-flight Bundesliga, but sourced from OpenLigaDB (openliga.py) via a
dedicated model instance (get_model_bl2()) with no odds/Bayes variant --
see the plan for why this is a separate router rather than parametrizing
the existing BL1 routers.
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.services import openliga, prediction_cache_bl2, simulation_bl2
from app.services.dixon_coles import get_model_bl2
from app.models.schemas import (
    Prediction, ScoreMatrix, WinProbabilities, TableEntry, Team,
    H2HMatch, H2HResponse, SimulationResult,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/bl2", tags=["bl2"])

LIVE_STATUSES = {"IN_PLAY", "PAUSED", "LIVE"}
FINISHED_STATUSES = {"FINISHED", "AWARDED"}
SCHEDULED_STATUSES = {"SCHEDULED", "TIMED"}


def _build_prediction(fixture, pred) -> Prediction:
    return Prediction(
        fixture=fixture,
        score_matrix=ScoreMatrix(
            matrix=pred["score_matrix"],
            max_goals=pred["max_goals"],
            home_team=fixture.home_team.name,
            away_team=fixture.away_team.name,
        ),
        win_probabilities=WinProbabilities(
            home_win=pred["home_win"],
            draw=pred["draw"],
            away_win=pred["away_win"],
        ),
        expected_home_goals=pred["expected_home_goals"],
        expected_away_goals=pred["expected_away_goals"],
        most_likely_score=pred["most_likely_score"],
        odds=None,
        edge_home_win=None,
        edge_draw=None,
        edge_away_win=None,
        rest_days_home=pred.get("rest_days_home"),
        rest_days_away=pred.get("rest_days_away"),
        rest_factor_home=pred.get("rest_factor_home"),
        rest_factor_away=pred.get("rest_factor_away"),
        travel_km=pred.get("travel_km"),
        travel_factor=pred.get("travel_factor"),
    )


@router.get("/fixtures/upcoming", response_model=list[Prediction])
async def get_bl2_predictions_for_upcoming_fixtures():
    """
    Returns Dixon-Coles predictions for current and upcoming 2. Bundesliga
    fixtures. No odds/edge fields (2. Bundesliga has no market data) and no
    model_variant param (only one model). Predictions for live/finished
    games are served from cache (frozen at kickoff), same as BL1.
    """
    model = get_model_bl2()
    if not model.fitted:
        raise HTTPException(
            status_code=503,
            detail="BL2 model not yet fitted. Try again in a moment — fitting runs on startup.",
        )

    fixtures = await openliga.get_current_and_upcoming_fixtures_bl2()

    predictions = []
    for fixture in fixtures:
        home = fixture.home_team.name
        away = fixture.away_team.name
        is_settled = fixture.status in LIVE_STATUSES | FINISHED_STATUSES

        if is_settled:
            cached = prediction_cache_bl2.get(fixture.id)
            if cached:
                predictions.append(cached.model_copy(update={"fixture": fixture}))
                continue

        try:
            pred = model.predict(home, away, fixture_date=fixture.utc_date.isoformat())
        except Exception as e:
            logger.warning(f"BL2 prediction failed for {home} vs {away}: {e}")
            continue

        prediction = _build_prediction(fixture, pred)
        prediction_cache_bl2.set(fixture.id, prediction)
        predictions.append(prediction)

    return predictions


@router.get("/table", response_model=list[TableEntry])
async def get_bl2_table():
    """Current 2. Bundesliga standings augmented with model-implied expected points."""
    model = get_model_bl2()
    if not model.fitted:
        raise HTTPException(status_code=503, detail="BL2 model not yet fitted.")

    standings = await openliga.get_standings_bl2()
    fixtures = await openliga.get_current_and_upcoming_fixtures_bl2()

    remaining = [f for f in fixtures if f.status in SCHEDULED_STATUSES]
    exp_pts: dict[str, float] = {}

    for fixture in remaining:
        home = fixture.home_team.name
        away = fixture.away_team.name
        try:
            pred = model.predict(home, away)
        except Exception:
            continue
        home_ep = pred["home_win"] * 3 + pred["draw"]
        away_ep = pred["away_win"] * 3 + pred["draw"]
        exp_pts[home] = exp_pts.get(home, 0.0) + home_ep
        exp_pts[away] = exp_pts.get(away, 0.0) + away_ep

    table = []
    for row in standings:
        name = row["team_name"]
        ep = round(exp_pts.get(name, 0.0), 1)
        table.append(TableEntry(
            position=row["position"],
            team=Team(
                id=row["team_id"],
                name=name,
                short_name=row["team_short_name"],
                crest_url=row["team_crest"],
            ),
            played=row["played"],
            won=row["won"],
            draw=row["draw"],
            lost=row["lost"],
            goals_for=row["goals_for"],
            goals_against=row["goals_against"],
            goal_difference=row["goal_difference"],
            points=row["points"],
            form=None,
            expected_pts_remaining=ep,
            projected_total=round(row["points"] + ep, 1),
        ))

    return table


@router.get("/h2h/matches", response_model=H2HResponse)
async def get_bl2_h2h_matches(
    home_team: str = Query(...),
    away_team: str = Query(...),
    limit: int = Query(6, ge=1, le=20),
):
    model = get_model_bl2()
    if not model.fitted:
        raise HTTPException(status_code=503, detail="BL2 model not fitted yet")

    df = model._h2h_df
    mask = (
        ((df["home_team"] == home_team) & (df["away_team"] == away_team))
        | ((df["home_team"] == away_team) & (df["away_team"] == home_team))
    )
    h2h = df[mask].sort_values("date", ascending=False).head(limit)

    matches: list[H2HMatch] = []
    home_wins = draws = away_wins = 0

    for _, row in h2h.iterrows():
        hg = int(row["home_goals"])
        ag = int(row["away_goals"])
        ht = row["home_team"]
        at = row["away_team"]

        if ht == home_team:
            result = "HOME_WIN" if hg > ag else "DRAW" if hg == ag else "AWAY_WIN"
        else:
            result = "HOME_WIN" if ag > hg else "DRAW" if ag == hg else "AWAY_WIN"

        if result == "HOME_WIN":
            home_wins += 1
        elif result == "DRAW":
            draws += 1
        else:
            away_wins += 1

        matches.append(H2HMatch(
            date=str(row["date"])[:10],
            home_team=ht,
            away_team=at,
            home_goals=hg,
            away_goals=ag,
            result=result,
        ))

    return H2HResponse(
        home_team=home_team,
        away_team=away_team,
        matches=matches,
        home_wins=home_wins,
        draws=draws,
        away_wins=away_wins,
    )


@router.get("/simulation", response_model=SimulationResult)
async def get_bl2_simulation():
    return await simulation_bl2.run_simulation()
