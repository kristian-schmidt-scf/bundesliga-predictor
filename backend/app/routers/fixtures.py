from fastapi import APIRouter, HTTPException
from app.services import football_data
from app.models.schemas import Fixture
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/fixtures", tags=["fixtures"])


@router.get("/upcoming", response_model=list[Fixture])
async def get_upcoming_fixtures():
    """
    Returns upcoming scheduled Bundesliga fixtures.
    """
    try:
        fixtures = await football_data.get_upcoming_fixtures()
        return fixtures
    except Exception as e:
        logger.exception("Failed to fetch fixtures")
        raise HTTPException(status_code=502, detail=f"Upstream API error: {str(e)}")
