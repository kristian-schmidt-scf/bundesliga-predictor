from fastapi import APIRouter, HTTPException, Query
from app.services.dixon_coles import get_model
from app.models.schemas import H2HMatch, H2HResponse
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/h2h", tags=["h2h"])


@router.get("/matches", response_model=H2HResponse)
async def get_h2h_matches(
    home_team: str = Query(...),
    away_team: str = Query(...),
    limit: int = Query(6, ge=1, le=20),
):
    model = get_model()
    if not model.fitted:
        raise HTTPException(status_code=503, detail="Model not fitted yet")

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
            if hg > ag:
                result = "HOME_WIN"
            elif hg == ag:
                result = "DRAW"
            else:
                result = "AWAY_WIN"
        else:
            # reversed fixture — home_team was playing away
            if ag > hg:
                result = "HOME_WIN"
            elif ag == hg:
                result = "DRAW"
            else:
                result = "AWAY_WIN"

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
