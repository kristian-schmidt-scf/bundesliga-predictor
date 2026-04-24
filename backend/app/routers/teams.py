from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import numpy as np

from app.services.dixon_coles import get_model, get_model_bayes
from app.services.football_data import get_current_and_upcoming_fixtures
from app.models.schemas import TeamProfileResponse, TeamSeasonResult, TeamUpcomingFixture

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("/{team_name}", response_model=TeamProfileResponse)
async def get_team_profile(team_name: str):
    model = get_model()
    if not model.fitted:
        raise HTTPException(status_code=503, detail="Model not yet fitted.")

    # Case-insensitive team lookup
    resolved = next((t for t in model.teams if t.lower() == team_name.lower()), None)
    if resolved is None:
        raise HTTPException(status_code=404, detail=f"Team '{team_name}' not found in model.")
    team_name = resolved

    avg_alpha = float(np.mean(list(model.alphas.values())))
    avg_delta = float(np.mean(list(model.deltas.values())))
    avg_gamma = float(np.mean(list(model.gammas.values())))
    avg_form  = float(np.mean(list(model.form.values()))) if model.form else 1.0

    bayes = get_model_bayes()
    alpha_bayes = delta_bayes = gamma_bayes = form_bayes = None
    if bayes.fitted and team_name in bayes.alphas:
        alpha_bayes = round(bayes.alphas[team_name], 4)
        delta_bayes = round(bayes.deltas[team_name], 4)
        gamma_bayes = round(bayes.gammas.get(team_name, avg_gamma), 4)
        form_bayes  = round(bayes.form.get(team_name, avg_form), 4)

    # Current season results from training data
    current_year = str(datetime.now(timezone.utc).year)
    season_results: list[TeamSeasonResult] = []
    if model._h2h_df is not None:
        df = model._h2h_df
        mask = (
            ((df["home_team"] == team_name) | (df["away_team"] == team_name)) &
            df["date"].str.startswith(current_year)
        )
        for _, row in df[mask].sort_values("date", ascending=False).iterrows():
            md = int(row["matchday"]) if "matchday" in df.columns and row.get("matchday") else None
            season_results.append(TeamSeasonResult(
                date=str(row["date"])[:10],
                matchday=md,
                home_team=str(row["home_team"]),
                away_team=str(row["away_team"]),
                home_goals=int(row["home_goals"]),
                away_goals=int(row["away_goals"]),
            ))

    # Upcoming fixtures with predictions
    upcoming: list[TeamUpcomingFixture] = []
    for fixture in await get_current_and_upcoming_fixtures():
        if fixture.status not in ("SCHEDULED", "TIMED"):
            continue
        ht, at = fixture.home_team.name, fixture.away_team.name
        if ht != team_name and at != team_name:
            continue
        try:
            pred = model.predict(ht, at, fixture_date=fixture.utc_date.isoformat())
            upcoming.append(TeamUpcomingFixture(
                fixture_id=fixture.id,
                date=fixture.utc_date.isoformat(),
                matchday=fixture.matchday,
                home_team=ht,
                away_team=at,
                home_win_prob=pred["home_win"],
                draw_prob=pred["draw"],
                away_win_prob=pred["away_win"],
                expected_home_goals=pred["expected_home_goals"],
                expected_away_goals=pred["expected_away_goals"],
            ))
        except Exception:
            pass

    return TeamProfileResponse(
        team=team_name,
        alpha=round(model.alphas.get(team_name, avg_alpha), 4),
        delta=round(model.deltas.get(team_name, avg_delta), 4),
        gamma=round(model.gammas.get(team_name, avg_gamma), 4),
        form=round(model.form.get(team_name, avg_form), 4),
        avg_alpha=round(avg_alpha, 4),
        avg_delta=round(avg_delta, 4),
        avg_gamma=round(avg_gamma, 4),
        avg_form=round(avg_form, 4),
        alpha_bayes=alpha_bayes,
        delta_bayes=delta_bayes,
        gamma_bayes=gamma_bayes,
        form_bayes=form_bayes,
        bayes_fitted=bayes.fitted,
        season_results=season_results,
        upcoming=upcoming,
    )
