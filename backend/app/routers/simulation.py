from fastapi import APIRouter
from app.services.simulation import run_simulation
from app.models.schemas import SimulationResult

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.get("", response_model=SimulationResult)
async def get_simulation():
    return await run_simulation()
