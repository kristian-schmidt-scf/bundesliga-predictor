"""
Dixon-Coles Poisson model for football score prediction.

Reference: Dixon & Coles (1997) "Modelling Association Football Scores
and Inefficiencies in the Football Betting Market"

Key ideas:
- Each team has an attack (alpha) and defence (delta) strength parameter
- A global home advantage (gamma) parameter
- Expected goals: lambda_home = alpha_home * delta_away * gamma
                  mu_away    = alpha_away * delta_home
- Low-score correction factor (tau) adjusts probabilities for 0-0, 1-0, 0-1, 1-1
- Time decay weights recent matches more heavily (exponential decay)
"""

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson
from scipy.special import gammaln
from datetime import datetime, timezone
from app.config import settings
import logging

logger = logging.getLogger(__name__)

MAX_GOALS = 8  # We compute P(i, j) for i,j in 0..MAX_GOALS


# ---------------------------------------------------------------------------
# Time decay
# ---------------------------------------------------------------------------

def _time_weights(dates: list[str], half_life_days: int) -> np.ndarray:
    """
    Exponential decay: w = exp(-lambda * age_in_days)
    where lambda = ln(2) / half_life_days
    """
    now = datetime.now(timezone.utc)
    decay = np.log(2) / half_life_days
    weights = []
    for d in dates:
        dt = datetime.fromisoformat(d.replace("Z", "+00:00"))
        age_days = (now - dt).days
        weights.append(np.exp(-decay * age_days))
    return np.array(weights)


# ---------------------------------------------------------------------------
# Dixon-Coles tau correction
# ---------------------------------------------------------------------------

def _tau(home_goals: int, away_goals: int, lam: float, mu: float, rho: float) -> float:
    """
    Low-score correction factor.
    Adjusts probabilities for (0,0), (1,0), (0,1), (1,1).
    """
    if home_goals == 0 and away_goals == 0:
        return 1 - lam * mu * rho
    elif home_goals == 1 and away_goals == 0:
        return 1 + mu * rho
    elif home_goals == 0 and away_goals == 1:
        return 1 + lam * rho
    elif home_goals == 1 and away_goals == 1:
        return 1 - rho
    else:
        return 1.0


# ---------------------------------------------------------------------------
# Vectorized log-likelihood (fast)
# ---------------------------------------------------------------------------

def _neg_log_likelihood(
    params: np.ndarray,
    data: pd.DataFrame,
    teams: list[str],
    weights: np.ndarray,
    team_idx: dict,
) -> float:
    n = len(teams)
    alphas = np.exp(params[:n])
    deltas = np.exp(params[n:2 * n])
    gamma = np.exp(params[2 * n])
    rho = params[2 * n + 1]

    hi = np.array([team_idx[t] for t in data["home_team"]])
    ai = np.array([team_idx[t] for t in data["away_team"]])
    hg = data["home_goals"].values.astype(int)
    ag = data["away_goals"].values.astype(int)

    lam = alphas[hi] * deltas[ai] * gamma
    mu = alphas[ai] * deltas[hi]

    # Vectorized Poisson log-pmf: k*log(l) - l - log(k!)
    log_p = (
        hg * np.log(lam) - lam - gammaln(hg + 1)
        + ag * np.log(mu) - mu - gammaln(ag + 1)
    )

    # Tau correction for low scores
    tau = np.ones(len(hg))
    mask_00 = (hg == 0) & (ag == 0)
    mask_10 = (hg == 1) & (ag == 0)
    mask_01 = (hg == 0) & (ag == 1)
    mask_11 = (hg == 1) & (ag == 1)

    tau[mask_00] = 1 - lam[mask_00] * mu[mask_00] * rho
    tau[mask_10] = 1 + mu[mask_10] * rho
    tau[mask_01] = 1 + lam[mask_01] * rho
    tau[mask_11] = 1 - rho
    tau = np.clip(tau, 1e-10, None)

    ll = np.sum(weights * (log_p + np.log(tau)))
    return -ll


# ---------------------------------------------------------------------------
# Model fitting
# ---------------------------------------------------------------------------

class DixonColesModel:
    def __init__(self):
        self.teams: list[str] = []
        self.alphas: dict[str, float] = {}
        self.deltas: dict[str, float] = {}
        self.gamma: float = 1.0
        self.rho: float = 0.0
        self.fitted: bool = False

    def fit(self, results: list[dict]) -> None:
        """
        Fit the model on historical results.
        results: list of dicts with keys home_team, away_team, home_goals, away_goals, date
        """
        if not results:
            raise ValueError("No results provided to fit the model.")

        df = pd.DataFrame(results)
        self.teams = sorted(
            set(df["home_team"].tolist() + df["away_team"].tolist())
        )
        n = len(self.teams)
        logger.info(f"Fitting Dixon-Coles model on {len(df)} matches, {n} teams")

        weights = _time_weights(
            df["date"].tolist(),
            settings.time_decay_half_life_days,
        )

        # Pre-compute team index lookup once
        team_idx = {t: i for i, t in enumerate(self.teams)}

        # Initial params: all zeros in log-space (=> all strengths = 1)
        x0 = np.zeros(2 * n + 2)

        result = minimize(
            _neg_log_likelihood,
            x0,
            args=(df, self.teams, weights, team_idx),
            method="L-BFGS-B",
            options={"maxiter": 500, "ftol": 1e-9},
        )

        if not result.success:
            logger.warning(f"Optimiser warning: {result.message}")

        params = result.x
        alphas_raw = np.exp(params[:n])
        deltas_raw = np.exp(params[n:2 * n])
        self.gamma = float(np.exp(params[2 * n]))
        self.rho = float(params[2 * n + 1])

        self.alphas = {t: float(alphas_raw[i]) for i, t in enumerate(self.teams)}
        self.deltas = {t: float(deltas_raw[i]) for i, t in enumerate(self.teams)}
        self.fitted = True

        logger.info(
            f"Model fitted. Home advantage (gamma): {self.gamma:.3f}, "
            f"rho: {self.rho:.4f}"
        )

    def predict(self, home_team: str, away_team: str) -> dict:
        """
        Predict score distribution for a fixture.
        Returns score matrix, win probabilities, expected goals, most likely score.
        """
        if not self.fitted:
            raise RuntimeError("Model has not been fitted yet.")

        # Fall back to average strength for unknown teams
        avg_alpha = float(np.mean(list(self.alphas.values())))
        avg_delta = float(np.mean(list(self.deltas.values())))

        alpha_h = self.alphas.get(home_team, avg_alpha)
        delta_h = self.deltas.get(home_team, avg_delta)
        alpha_a = self.alphas.get(away_team, avg_alpha)
        delta_a = self.deltas.get(away_team, avg_delta)

        lam = alpha_h * delta_a * self.gamma
        mu = alpha_a * delta_h

        # Build score probability matrix
        score_matrix = np.zeros((MAX_GOALS + 1, MAX_GOALS + 1))
        for i in range(MAX_GOALS + 1):
            for j in range(MAX_GOALS + 1):
                tau_val = _tau(i, j, lam, mu, self.rho)
                score_matrix[i][j] = (
                    poisson.pmf(i, lam)
                    * poisson.pmf(j, mu)
                    * tau_val
                )

        # Normalise
        score_matrix = score_matrix / score_matrix.sum()

        # Win probabilities
        home_win = float(np.sum(np.tril(score_matrix, -1)))
        away_win = float(np.sum(np.triu(score_matrix, 1)))
        draw = float(np.trace(score_matrix))

        # Most likely score
        idx = np.unravel_index(np.argmax(score_matrix), score_matrix.shape)
        most_likely = f"{idx[0]}-{idx[1]}"

        return {
            "score_matrix": score_matrix.tolist(),
            "max_goals": MAX_GOALS,
            "home_win": round(home_win, 4),
            "draw": round(draw, 4),
            "away_win": round(away_win, 4),
            "expected_home_goals": round(float(lam), 2),
            "expected_away_goals": round(float(mu), 2),
            "most_likely_score": most_likely,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_model_instance: DixonColesModel | None = None


def get_model() -> DixonColesModel:
    global _model_instance
    if _model_instance is None:
        _model_instance = DixonColesModel()
    return _model_instance