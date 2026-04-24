from fastapi import APIRouter, HTTPException
from app.services import user_picks
from app.models.schemas import UserPick, UserPickRequest

router = APIRouter(prefix="/picks", tags=["picks"])


@router.get("", response_model=list[UserPick])
async def get_picks():
    return user_picks.get_all_picks()


@router.put("/{fixture_id}", response_model=UserPick)
async def save_pick(fixture_id: int, body: UserPickRequest):
    if body.picked_home < 0 or body.picked_away < 0:
        raise HTTPException(status_code=422, detail="Goals cannot be negative")
    return user_picks.save_pick(
        fixture_id=fixture_id,
        matchday=body.matchday,
        home_team=body.home_team,
        away_team=body.away_team,
        picked_home=body.picked_home,
        picked_away=body.picked_away,
    )


@router.delete("/{fixture_id}", status_code=204)
async def delete_pick(fixture_id: int):
    user_picks.delete_pick(fixture_id)
