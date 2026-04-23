from fastapi import APIRouter, HTTPException
from app.services.dixon_coles import get_model, get_model_bayes, PRIOR_STRENGTH
from app.services.football_data import get_standings
from app.models.schemas import ModelParamsResponse, TeamParams

router = APIRouter(prefix="/model-params", tags=["model-params"])


@router.get("", response_model=ModelParamsResponse)
async def get_model_params():
    """Returns fitted parameters for teams active in the current Bundesliga season."""
    model = get_model()
    if not model.fitted:
        raise HTTPException(status_code=503, detail="Base model not yet fitted.")

    bayes = get_model_bayes()

    # Use standings — the authoritative list of exactly 18 current Bundesliga teams
    standings = await get_standings()
    current_teams = {row["team_name"] for row in standings}

    teams_out = []
    for team in sorted(t for t in model.teams if t in current_teams):
        entry = TeamParams(
            team=team,
            alpha_base=round(model.alphas.get(team, 0.0), 4),
            delta_base=round(model.deltas.get(team, 0.0), 4),
            gamma_base=round(model.gammas.get(team, 0.0), 4),
            form_base=round(model.form.get(team, 1.0), 4),
        )
        if bayes.fitted:
            entry.alpha_bayes = round(bayes.alphas.get(team, 0.0), 4)
            entry.delta_bayes = round(bayes.deltas.get(team, 0.0), 4)
            entry.gamma_bayes = round(bayes.gammas.get(team, 0.0), 4)
            entry.form_bayes  = round(bayes.form.get(team, 1.0), 4)
        teams_out.append(entry)

    return ModelParamsResponse(
        rho_base=round(model.rho, 4),
        rho_bayes=round(bayes.rho, 4) if bayes.fitted else None,
        prior_strength=PRIOR_STRENGTH,
        bayes_fitted=bayes.fitted,
        teams=teams_out,
    )
