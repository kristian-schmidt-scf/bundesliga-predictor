"""
Diagnostic: are higher-scoring draws (2:2, 3:3) underestimated by the model?

Compares in-sample predicted frequency vs observed frequency for every score cell
up to 4:4. Shows three columns:
  - Raw Poisson (no tau correction)
  - Model (tau-corrected, normalised — same as what the prediction endpoint outputs)
  - Observed

Usage (from backend/):
    python -m scripts.analyze_draw_calibration
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from scipy.stats import poisson

from app.services.historical_data import load_historical_data
from app.services.dixon_coles import DixonColesModel, _tau, MAX_GOALS


def build_score_matrix(lam: float, mu: float, rho: float, size: int) -> np.ndarray:
    """Normalised tau-corrected Poisson score matrix."""
    m = np.zeros((size, size))
    for i in range(size):
        for j in range(size):
            m[i, j] = poisson.pmf(i, lam) * poisson.pmf(j, mu) * _tau(i, j, lam, mu, rho)
    return m / m.sum()


def build_score_matrix_no_tau(lam: float, mu: float, size: int) -> np.ndarray:
    """Independent Poisson — no tau correction."""
    m = np.zeros((size, size))
    for i in range(size):
        for j in range(size):
            m[i, j] = poisson.pmf(i, lam) * poisson.pmf(j, mu)
    return m / m.sum()


def main():
    data = load_historical_data()
    if not data:
        print("No historical data found. Run scrape_bundesliga_history.py first.")
        return

    print(f"Loaded {len(data)} historical matches")

    model = DixonColesModel()
    model.fit(data)

    print(f"rho = {model.rho:.6f}\n")

    size = 5  # scores 0..4

    pred_tau  = np.zeros((size, size))
    pred_raw  = np.zeros((size, size))
    obs       = np.zeros((size, size), dtype=int)
    total     = 0

    for match in data:
        home = match["home_team"]
        away = match["away_team"]
        hg   = int(match["home_goals"])
        ag   = int(match["away_goals"])

        if home not in model.alphas or away not in model.alphas:
            continue

        lam = model.alphas[home] * model.deltas[away] * model.gammas[home]
        mu  = model.alphas[away] * model.deltas[home]

        pred_tau += build_score_matrix(lam, mu, model.rho, size)
        pred_raw += build_score_matrix_no_tau(lam, mu, size)

        if hg < size and ag < size:
            obs[hg, ag] += 1
        total += 1

    print(f"Matches analysed: {total}\n")

    # ── Draw cells ─────────────────────────────────────────────────────────
    print("=== Draw cells (diagonal) ===")
    header = f"{'Score':<8} {'Raw Poisson':>12} {'Model (tau)':>12} {'Observed':>10} {'Ratio (obs/model)':>18}  Note"
    print(header)
    print("-" * 75)
    for d in range(size):
        raw  = pred_raw[d, d]  / total * 100
        tau  = pred_tau[d, d]  / total * 100
        obs_ = obs[d, d]       / total * 100
        r    = obs_ / tau if tau > 0 else float("inf")
        note = "(tau-corrected)" if d <= 1 else "(no correction)"
        flag = "  <-- OVER" if r < 0.85 else ("  <-- UNDER" if r > 1.15 else "")
        print(f"{d}:{d}     {raw:>11.3f}% {tau:>11.3f}% {obs_:>9.3f}% {r:>12.3f}x       {note}{flag}")

    total_tau = sum(pred_tau[d, d] for d in range(size)) / total * 100
    total_raw = sum(pred_raw[d, d] for d in range(size)) / total * 100
    total_obs = sum(obs[d, d]      for d in range(size)) / total * 100
    print(f"\n{'Total draws':15} {total_raw:>11.2f}% {total_tau:>11.2f}% {total_obs:>9.2f}%")

    # ── Full score grid (model vs observed) ────────────────────────────────
    print("\n=== Score grid: observed% / model% (ratio) ===")
    print("     " + "".join(f"  away={j}" for j in range(size)))
    for i in range(size):
        row = f"h={i}  "
        for j in range(size):
            tau_  = pred_tau[i, j] / total * 100
            obs_  = obs[i, j]      / total * 100
            r     = obs_ / tau_ if tau_ > 0 else 0
            # Mark cells where observed deviates >20% and frequency is >0.5%
            marker = "*" if abs(r - 1) > 0.20 and (tau_ + obs_) > 1.0 else " "
            row += f" {obs_:.1f}/{tau_:.1f}{marker}"
        print(row)

    print("\n  * = |ratio - 1| > 20% in a cell with combined frequency > 1%")
    print("  Format: observed% / predicted%")


if __name__ == "__main__":
    main()
