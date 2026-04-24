from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ---------------------------------------------------------------------------
# Model parameters
# ---------------------------------------------------------------------------

class BacktestMatchday(BaseModel):
    matchday: int
    fixtures: int
    brier_score: float
    log_loss: float
    tendency_accuracy: float
    tipp11_expected: float
    tipp11_actual: float


class BacktestResult(BaseModel):
    status: str                          # "ready" | "computing" | "unavailable"
    matchdays_tested: int = 0
    brier_score: float = 0.0
    log_loss: float = 0.0
    tendency_accuracy: float = 0.0
    tipp11_expected: float = 0.0
    tipp11_actual: float = 0.0
    per_matchday: list[BacktestMatchday] = []


class TeamParams(BaseModel):
    team: str
    alpha_base: float
    delta_base: float
    gamma_base: float
    form_base: float
    alpha_bayes: Optional[float] = None
    delta_bayes: Optional[float] = None
    gamma_bayes: Optional[float] = None
    form_bayes: Optional[float] = None


class ModelParamsResponse(BaseModel):
    rho_base: float
    rho_bayes: Optional[float] = None
    prior_strength: float
    bayes_fitted: bool
    teams: list[TeamParams]


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


class TeamSimResult(BaseModel):
    team_name: str
    team_id: int
    p_cl: float
    p_el: float
    p_ecl: float
    p_playoff: float
    p_relegated: float
    median_points: float
    p10_points: float
    p90_points: float


class SimulationResult(BaseModel):
    status: str
    n_simulations: int
    n_remaining: int
    teams: list[TeamSimResult]


# ---------------------------------------------------------------------------
# Team profile
# ---------------------------------------------------------------------------

class TeamSeasonResult(BaseModel):
    date: str
    matchday: Optional[int]
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int


class TeamUpcomingFixture(BaseModel):
    fixture_id: int
    date: str
    matchday: int
    home_team: str
    away_team: str
    home_win_prob: float
    draw_prob: float
    away_win_prob: float
    expected_home_goals: float
    expected_away_goals: float


class TeamProfileResponse(BaseModel):
    team: str
    alpha: float
    delta: float
    gamma: float
    form: float
    avg_alpha: float
    avg_delta: float
    avg_gamma: float
    avg_form: float
    alpha_bayes: Optional[float] = None
    delta_bayes: Optional[float] = None
    gamma_bayes: Optional[float] = None
    form_bayes: Optional[float] = None
    bayes_fitted: bool
    season_results: list[TeamSeasonResult]
    upcoming: list[TeamUpcomingFixture]


# ---------------------------------------------------------------------------
# Odds movement
# ---------------------------------------------------------------------------

class OddsSnapshot(BaseModel):
    timestamp: str
    home_win: Optional[float] = None
    draw: Optional[float] = None
    away_win: Optional[float] = None
    implied_home_prob: Optional[float] = None
    implied_draw_prob: Optional[float] = None
    implied_away_prob: Optional[float] = None


class OddsMovement(BaseModel):
    direction: str   # "shortened" | "lengthened" | "stable"
    delta: float     # change in implied probability (positive = more likely)


class OddsHistoryResponse(BaseModel):
    fixture_id: int
    snapshots: list[OddsSnapshot]
    opening: Optional[OddsSnapshot] = None
    current: Optional[OddsSnapshot] = None
    movement_home: Optional[OddsMovement] = None
    movement_draw: Optional[OddsMovement] = None
    movement_away: Optional[OddsMovement] = None


# ---------------------------------------------------------------------------
# Head-to-head
# ---------------------------------------------------------------------------

class H2HMatch(BaseModel):
    date: str
    home_team: str
    away_team: str
    home_goals: int
    away_goals: int
    result: str   # HOME_WIN | DRAW | AWAY_WIN — relative to the requested home_team


class H2HResponse(BaseModel):
    home_team: str
    away_team: str
    matches: list[H2HMatch]
    home_wins: int
    draws: int
    away_wins: int


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
    # Fatigue & travel
    rest_days_home: Optional[int] = None
    rest_days_away: Optional[int] = None
    rest_factor_home: Optional[float] = None
    rest_factor_away: Optional[float] = None
    travel_km: Optional[float] = None
    travel_factor: Optional[float] = None
