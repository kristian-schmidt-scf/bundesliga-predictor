from fastapi import APIRouter, Query
from app.services import odds_history
from app.models.schemas import OddsHistoryResponse, OddsMovement, OddsSnapshot

router = APIRouter(prefix="/odds", tags=["odds"])

_STABLE_THRESHOLD = 0.005  # < 0.5pp change = stable


def _movement(opening: OddsSnapshot | None, current: OddsSnapshot | None, field: str) -> OddsMovement | None:
    if opening is None or current is None:
        return None
    o = getattr(opening, field)
    c = getattr(current, field)
    if o is None or c is None:
        return None
    delta = round(c - o, 4)
    if abs(delta) < _STABLE_THRESHOLD:
        direction = "stable"
    elif delta > 0:
        direction = "shortened"
    else:
        direction = "lengthened"
    return OddsMovement(direction=direction, delta=delta)


@router.get("/history", response_model=OddsHistoryResponse)
async def get_odds_history(fixture_id: int = Query(...)):
    history = odds_history.get_history(fixture_id)
    opening = history[0] if history else None
    current = history[-1] if len(history) >= 2 else None

    return OddsHistoryResponse(
        fixture_id=fixture_id,
        snapshots=history,
        opening=opening,
        current=current,
        movement_home=_movement(opening, current, "implied_home_prob"),
        movement_draw=_movement(opening, current, "implied_draw_prob"),
        movement_away=_movement(opening, current, "implied_away_prob"),
    )
