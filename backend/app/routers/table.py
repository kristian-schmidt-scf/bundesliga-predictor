import asyncio
from fastapi import APIRouter, HTTPException
from app.services import football_data
from app.services.dixon_coles import get_model
from app.models.schemas import TableEntry, Team

router = APIRouter(prefix="/table", tags=["table"])

SCHEDULED_STATUSES = {"SCHEDULED", "TIMED"}


def _compute_form(team_name: str, fixtures) -> str:
    """Last 5 results for a team as a comma-separated W/D/L string."""
    results = []
    for f in fixtures:
        if f.home_score is None or f.away_score is None:
            continue
        if f.home_team.name == team_name:
            results.append((f.utc_date, "W" if f.home_score > f.away_score else ("D" if f.home_score == f.away_score else "L")))
        elif f.away_team.name == team_name:
            results.append((f.utc_date, "W" if f.away_score > f.home_score else ("D" if f.away_score == f.home_score else "L")))
    results.sort(key=lambda x: x[0])
    return ",".join(r for _, r in results[-5:])


@router.get("", response_model=list[TableEntry])
async def get_league_table():
    """
    Returns current Bundesliga standings augmented with model-implied
    expected points for all remaining scheduled fixtures.
    """
    model = get_model()
    if not model.fitted:
        raise HTTPException(status_code=503, detail="Model not yet fitted.")

    standings, fixtures = await asyncio.gather(
        football_data.get_standings(),
        football_data.get_current_and_upcoming_fixtures(),
    )

    # Build expected-points map: team_name -> expected pts from remaining games
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
        form = row.get("form") or _compute_form(name, fixtures)
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
            form=form,
            expected_pts_remaining=ep,
            projected_total=round(row["points"] + ep, 1),
        ))

    return table
