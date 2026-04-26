import asyncio
from fastapi import APIRouter
from app.services import backtest as backtest_service
from app.models.schemas import BacktestResult

router = APIRouter(prefix="/backtest", tags=["backtest"])

_task_ref: set = set()


@router.get("", response_model=BacktestResult)
async def get_backtest():
    """
    Returns walk-forward backtest results for all finished Spieltage of the current season.
    Triggers computation on first request; returns status='computing' until ready.
    """
    result = backtest_service.get_result()

    # Lazily kick off computation on first request if not already running/done
    if result["status"] == "unavailable" and not backtest_service._computing and not backtest_service._attempted:
        task = asyncio.create_task(backtest_service.compute_backtest())
        _task_ref.add(task)
        task.add_done_callback(_task_ref.discard)
        return {"status": "computing", "matchdays_tested": 0, "per_matchday": []}

    return result
