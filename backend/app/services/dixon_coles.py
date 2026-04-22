"""
Dixon-Coles Poisson model for football score prediction.

Reference: Dixon & Coles (1997) "Modelling Association Football Scores
and Inefficiencies in the Football Betting Market"

Key ideas:
- Each team has an attack (alpha) and defence (delta) strength parameter
- A per-team home advantage (gamma_i) parameter
- Expected goals: lambda_home = alpha_home * delta_away * gamma_home
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
    gammas = np.exp(params[2 * n:3 * n])
    rho = params[3 * n]

    hi = np.array([team_idx[t] for t in data["home_team"]])
    ai = np.array([team_idx[t] for t in data["away_team"]])
    hg = data["home_goals"].values.astype(int)
    ag = data["away_goals"].values.astype(int)

    lam = alphas[hi] * deltas[ai] * gammas[hi]
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

# Shrinkage constant for H2H adjustment: higher = more weight on base model.
# At k=5, a single recent H2H match shifts lambda by ~17%; five matches by ~50%.
H2H_K = 5.0

# Recent form settings.
# FORM_N_GAMES: how many recent matches to consider.
# FORM_KAPPA: dampening exponent — at 0.1 a team with 2× avg PPG gets a ~7% boost.
FORM_N_GAMES = 5
FORM_KAPPA = 0.1


class DixonColesModel:
    def __init__(self):
        self.teams: list[str] = []
        self.alphas: dict[str, float] = {}
        self.deltas: dict[str, float] = {}
        self.gammas: dict[str, float] = {}
        self.rho: float = 0.0
        self.form: dict[str, float] = {}   # team -> form factor (centred around 1.0)
        self.fitted: bool = False
        self._h2h_df: pd.DataFrame | None = None
        self._h2h_weights: np.ndarray | None = None

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

        # Store for H2H lookup at prediction time
        self._h2h_df = df.reset_index(drop=True)
        self._h2h_weights = weights

        # Pre-compute team index lookup once
        team_idx = {t: i for i, t in enumerate(self.teams)}

        # Initial params: all zeros in log-space (=> all strengths = 1, gammas = 1)
        x0 = np.zeros(3 * n + 1)

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
        gammas_raw = np.exp(params[2 * n:3 * n])
        self.rho = float(params[3 * n])

        self.alphas = {t: float(alphas_raw[i]) for i, t in enumerate(self.teams)}
        self.deltas = {t: float(deltas_raw[i]) for i, t in enumerate(self.teams)}
        self.gammas = {t: float(gammas_raw[i]) for i, t in enumerate(self.teams)}
        self.fitted = True

        avg_gamma = float(np.mean(gammas_raw))
        min_t = min(self.gammas, key=self.gammas.get)
        max_t = max(self.gammas, key=self.gammas.get)

        self.form = self._compute_form(df)
        hot   = max(self.form, key=self.form.get)
        cold  = min(self.form, key=self.form.get)

        logger.info(
            f"Model fitted. rho: {self.rho:.4f} | "
            f"avg home advantage: {avg_gamma:.3f} | "
            f"lowest γ: {min_t} ({self.gammas[min_t]:.3f}) | "
            f"highest γ: {max_t} ({self.gammas[max_t]:.3f}) | "
            f"hottest form: {hot} ({self.form[hot]:.3f}) | "
            f"coldest form: {cold} ({self.form[cold]:.3f})"
        )

    def _compute_form(self, df: pd.DataFrame) -> dict[str, float]:
        """
        Compute a form factor for each team based on their last FORM_N_GAMES results.
        Returns a dict of team -> factor centred around 1.0 (above = good form).
        """
        teams = set(df["home_team"]) | set(df["away_team"])
        ppg: dict[str, float] = {}

        for team in teams:
            mask = (df["home_team"] == team) | (df["away_team"] == team)
            recent = df[mask].sort_values("date", ascending=False).head(FORM_N_GAMES)

            pts = []
            for _, row in recent.iterrows():
                hg, ag = int(row["home_goals"]), int(row["away_goals"])
                if row["home_team"] == team:
                    pts.append(3 if hg > ag else 1 if hg == ag else 0)
                else:
                    pts.append(3 if ag > hg else 1 if ag == hg else 0)

            ppg[team] = float(np.mean(pts)) if pts else 1.5

        avg_ppg = float(np.mean(list(ppg.values())))
        # Avoid division by zero; centre factor at 1.0
        return {
            t: (ppg[t] / avg_ppg) ** FORM_KAPPA if avg_ppg > 0 else 1.0
            for t in teams
        }

    def _h2h_adjust(
        self, home_team: str, away_team: str, lam_base: float, mu_base: float
    ) -> tuple[float, float]:
        """
        Bayesian shrinkage of lambda/mu toward H2H empirical goal averages.

        Combines same-order fixtures (home_team at home) and reversed fixtures
        (away_team at home), normalising reversed goals by each team's own gamma
        to remove the home-advantage signal before pooling.
        """
        df = self._h2h_df
        w = self._h2h_weights

        avg_gamma = float(np.mean(list(self.gammas.values())))
        gamma_home = self.gammas.get(home_team, avg_gamma)
        gamma_away = self.gammas.get(away_team, avg_gamma)

        same = (df["home_team"] == home_team) & (df["away_team"] == away_team)
        rev  = (df["home_team"] == away_team) & (df["away_team"] == home_team)

        # Reversed fixtures: scale home_team's away goals up by their home gamma,
        # and away_team's home goals down by their home gamma, before pooling.
        home_goals = np.concatenate([
            df.loc[same, "home_goals"].values.astype(float),
            df.loc[rev,  "away_goals"].values.astype(float) * gamma_home,
        ])
        away_goals = np.concatenate([
            df.loc[same, "away_goals"].values.astype(float),
            df.loc[rev,  "home_goals"].values.astype(float) / gamma_away,
        ])
        weights = np.concatenate([w[same.values], w[rev.values]])

        if len(weights) == 0:
            return lam_base, mu_base

        total_w = weights.sum()
        h2h_lam = float(np.dot(weights, home_goals) / total_w)
        h2h_mu  = float(np.dot(weights, away_goals) / total_w)

        lam_adj = (H2H_K * lam_base + total_w * h2h_lam) / (H2H_K + total_w)
        mu_adj  = (H2H_K * mu_base  + total_w * h2h_mu)  / (H2H_K + total_w)

        logger.debug(
            f"H2H {home_team} vs {away_team}: {int(same.sum())} same, "
            f"{int(rev.sum())} reversed. "
            f"λ {lam_base:.3f}→{lam_adj:.3f}, μ {mu_base:.3f}→{mu_adj:.3f}"
        )
        return lam_adj, mu_adj

    def predict(
        self,
        home_team: str,
        away_team: str,
        use_team_gamma: bool = True,
        use_h2h: bool = True,
        use_form: bool = True,
    ) -> dict:
        """
        Predict score distribution for a fixture.
        Returns score matrix, win probabilities, expected goals, most likely score.
        """
        if not self.fitted:
            raise RuntimeError("Model has not been fitted yet.")

        avg_alpha = float(np.mean(list(self.alphas.values())))
        avg_delta = float(np.mean(list(self.deltas.values())))
        avg_gamma = float(np.mean(list(self.gammas.values())))

        alpha_h = self.alphas.get(home_team, avg_alpha)
        delta_h = self.deltas.get(home_team, avg_delta)
        alpha_a = self.alphas.get(away_team, avg_alpha)
        delta_a = self.deltas.get(away_team, avg_delta)
        gamma_h = self.gammas.get(home_team, avg_gamma) if use_team_gamma else avg_gamma

        avg_form = float(np.mean(list(self.form.values()))) if self.form else 1.0
        form_h = self.form.get(home_team, avg_form) if use_form else 1.0
        form_a = self.form.get(away_team, avg_form) if use_form else 1.0

        lam_base = alpha_h * delta_a * gamma_h
        mu_base  = alpha_a * delta_h

        if use_h2h:
            lam, mu = self._h2h_adjust(home_team, away_team, lam_base, mu_base)
        else:
            lam, mu = lam_base, mu_base

        lam *= form_h
        mu  *= form_a

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
