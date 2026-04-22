from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class Team(BaseModel):
    id: int
    name: str
    short_name: str
    crest_url: Optional[str] = None


class Fixture(BaseModel):
    id: int
    home_team: Team
    away_team: Team
    utc_date: datetime
    matchday: int
    status: str  # SCHEDULED, LIVE, FINISHED, etc.
    home_score: Optional[int] = None
    away_score: Optional[int] = None


# ---------------------------------------------------------------------------
# Odds
# ---------------------------------------------------------------------------

class MatchOdds(BaseModel):
    home_win: Optional[float] = None   # decimal odds (e.g. 1.85)
    draw: Optional[float] = None
    away_win: Optional[float] = None
    # Implied probabilities (1/odds, normalised)
    implied_home_prob: Optional[float] = None
    implied_draw_prob: Optional[float] = None
    implied_away_prob: Optional[float] = None
    bookmaker: Optional[str] = None


# ---------------------------------------------------------------------------
# Predictions
# ---------------------------------------------------------------------------

class ScoreMatrix(BaseModel):
    """
    Probability matrix P(home_goals=i, away_goals=j)
    Rows = home goals (0..max_goals), cols = away goals (0..max_goals)
    """
    matrix: list[list[float]]   # [home_goals][away_goals]
    max_goals: int               # matrix is (max_goals+1) x (max_goals+1)
    home_team: str
    away_team: str


class WinProbabilities(BaseModel):
    home_win: float
    draw: float
    away_win: float


class CalibrationVariant(BaseModel):
    name: str
    description: str
    fixtures: int
    brier_score: float
    log_loss: float
    tendency_accuracy: float


class CalibrationMatchday(BaseModel):
    matchday: int
    fixtures: int
    brier_score: float
    log_loss: float
    tendency_accuracy: float


class CalibrationBucket(BaseModel):
    bucket_min: float
    bucket_max: float
    predicted_mean: float
    actual_frequency: float
    count: int


class CalibrationResult(BaseModel):
    total_fixtures: int
    brier_score: float
    log_loss: float
    tendency_accuracy: float
    variants: list[CalibrationVariant]
    per_matchday: list[CalibrationMatchday]
    calibration_curve: list[CalibrationBucket]


class TableEntry(BaseModel):
    position: int
    team: Team
    played: int
    won: int
    draw: int
    lost: int
    goals_for: int
    goals_against: int
    goal_difference: int
    points: int
    form: Optional[str] = None
    expected_pts_remaining: float = 0.0
    projected_total: float = 0.0


class Prediction(BaseModel):
    fixture: Fixture
    score_matrix: ScoreMatrix
    win_probabilities: WinProbabilities
    expected_home_goals: float
    expected_away_goals: float
    most_likely_score: str          # e.g. "2-1"
    odds: Optional[MatchOdds] = None
    # Edge vs bookmaker (model prob - implied prob); positive = model likes this outcome more
    edge_home_win: Optional[float] = None
    edge_draw: Optional[float] = None
    edge_away_win: Optional[float] = None
