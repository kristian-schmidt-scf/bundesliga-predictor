from fastapi import APIRouter
from app.services.backtest import get_result
from app.models.schemas import BacktestResult

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.get("", response_model=BacktestResult)
async def get_backtest():
    """
    Returns walk-forward backtest results for Spieltage 18–30.
    Computed once as a background task on startup; returns status='computing'
    until ready (~2 minutes after first server start).
    """
    return get_result()
