"""
Monte Carlo season simulation.

Pre-computes score matrices for all remaining fixtures once, then samples
10 000 outcomes in one vectorised numpy pass. Results are cached for the
lifetime of the server process (re-run after a restart / model refit).
"""

import asyncio
import logging

import numpy as np

from app.services import football_data
from app.services.dixon_coles import get_model

logger = logging.getLogger(__name__)

SCHEDULED_STATUSES = {"SCHEDULED", "TIMED"}
N_SIMULATIONS = 10_000
MAX_GOALS = 9  # score matrix is (MAX_GOALS × MAX_GOALS), goals 0..8

# Bundesliga qualification / relegation zone boundaries (1-indexed positions)
ZONE_CL      = (1, 4)
ZONE_EL      = (5, 6)
ZONE_ECL     = (7, 7)
ZONE_PLAYOFF = (16, 16)
ZONE_REL     = (17, 18)

_cache: dict | None = None


def reset_cache() -> None:
    global _cache
    _cache = None


async def run_simulation() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    model = get_model()
    if not model.fitted:
        return {"status": "unavailable", "n_simulations": 0, "n_remaining": 0, "teams": []}

    standings, fixtures = await asyncio.gather(
        football_data.get_standings(),
        football_data.get_current_and_upcoming_fixtures(),
    )

    remaining = [f for f in fixtures if f.status in SCHEDULED_STATUSES]

    teams_ordered = [row["team_name"] for row in standings]
    n_teams = len(teams_ordered)
    team_idx = {name: i for i, name in enumerate(teams_ordered)}

    base_pts = np.array([row["points"]          for row in standings], dtype=np.float64)
    base_gd  = np.array([row["goal_difference"] for row in standings], dtype=np.float64)
    base_gf  = np.array([row["goals_for"]       for row in standings], dtype=np.float64)

    # Pre-compute flattened probability vectors for each remaining fixture.
    fixture_specs: list[tuple[int, int, np.ndarray]] = []
    for fixture in remaining:
        home = fixture.home_team.name
        away = fixture.away_team.name
        h_idx = team_idx.get(home)
        a_idx = team_idx.get(away)
        if h_idx is None or a_idx is None:
            continue
        try:
            pred = model.predict(home, away, fixture.utc_date.isoformat())
        except Exception:
            continue
        flat = np.array(pred["score_matrix"], dtype=np.float64).flatten()
        flat /= flat.sum()  # guard against floating-point drift
        fixture_specs.append((h_idx, a_idx, flat))

    # Simulation accumulators: shape (N_SIMULATIONS, n_teams)
    sim_pts = np.zeros((N_SIMULATIONS, n_teams), dtype=np.float64)
    sim_gd  = np.zeros((N_SIMULATIONS, n_teams), dtype=np.float64)
    sim_gf  = np.zeros((N_SIMULATIONS, n_teams), dtype=np.float64)

    for h_idx, a_idx, flat in fixture_specs:
        sampled = np.random.choice(MAX_GOALS * MAX_GOALS, size=N_SIMULATIONS, p=flat)
        hg = sampled // MAX_GOALS
        ag = sampled  % MAX_GOALS

        home_wins = hg > ag
        draws     = hg == ag
        away_wins = hg < ag

        sim_pts[:, h_idx] += home_wins * 3 + draws
        sim_pts[:, a_idx] += away_wins * 3 + draws
        sim_gd [:, h_idx] += hg.astype(np.float64) - ag
        sim_gd [:, a_idx] += ag.astype(np.float64) - hg
        sim_gf [:, h_idx] += hg.astype(np.float64)
        sim_gf [:, a_idx] += ag.astype(np.float64)

    total_pts = base_pts[np.newaxis, :] + sim_pts
    total_gd  = base_gd [np.newaxis, :] + sim_gd
    total_gf  = base_gf [np.newaxis, :] + sim_gf

    # Composite sort key encodes Bundesliga tiebreaker order (pts > GD > GF).
    # Ranges: pts ≤ 110, GD ∈ [-120, +120] → shift +150, GF ≤ 200.
    composite = total_pts * 1_000_000 + (total_gd + 150) * 1_000 + total_gf

    # order[n, rank] = team index at that rank in simulation n (0-indexed, rank 0 = 1st)
    order = np.argsort(-composite, axis=1)
    # positions[n, team] = 1-based finishing position of that team in simulation n
    positions = np.argsort(order, axis=1) + 1

    team_results = []
    for i, row in enumerate(standings):
        pos_arr = positions[:, i]
        pts_arr = total_pts[:, i]

        def zone_prob(lo: int, hi: int) -> float:
            return float(((pos_arr >= lo) & (pos_arr <= hi)).mean())

        team_results.append({
            "team_name":    row["team_name"],
            "team_id":      row["team_id"],
            "p_cl":         zone_prob(*ZONE_CL),
            "p_el":         zone_prob(*ZONE_EL),
            "p_ecl":        zone_prob(*ZONE_ECL),
            "p_playoff":    zone_prob(*ZONE_PLAYOFF),
            "p_relegated":  zone_prob(*ZONE_REL),
            "median_points": float(np.median(pts_arr)),
            "p10_points":   float(np.percentile(pts_arr, 10)),
            "p90_points":   float(np.percentile(pts_arr, 90)),
        })

    _cache = {
        "status":        "ready",
        "n_simulations": N_SIMULATIONS,
        "n_remaining":   len(fixture_specs),
        "teams":         team_results,
    }
    logger.info(
        "Season simulation complete: %d fixtures, %d simulations",
        len(fixture_specs), N_SIMULATIONS,
    )
    return _cache
