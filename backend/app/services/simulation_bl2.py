"""
Monte Carlo season simulation for 2. Bundesliga.

Fork of simulation.py: same vectorised Monte Carlo core, but sourced from
OpenLigaDB (openliga.py) instead of football-data.org, using get_model_bl2(),
and with 2. Bundesliga's own promotion/relegation zone boundaries (no
European competition zones). Kept as a separate module rather than
parametrizing simulation.py, matching the project's existing convention of
parallel modules per model variant (e.g. prediction_cache.py /
prediction_cache_bayes.py) -- simulation.py's own cache and zone constants
were not designed to be parametrized, and this avoids risking the
well-tested BL1 path for marginal reuse benefit.

Field names in the response reuse TeamSimResult's BL1-shaped fields
(p_cl/p_el/p_ecl/p_playoff/p_relegated) since that schema is shared --
p_el/p_ecl are always 0 here (2. Liga has no European zones), p_cl carries
"auto-promotion" (positions 1-2), and p_playoff carries the promotion/
relegation playoff (position 3). The frontend's BL2_ZONES config (see
LeagueTable.jsx) is what actually relabels these for display.
"""

import asyncio
import logging

import numpy as np

from app.services import openliga
from app.services.dixon_coles import get_model_bl2

logger = logging.getLogger(__name__)

SCHEDULED_STATUSES = {"SCHEDULED", "TIMED"}
N_SIMULATIONS = 10_000
MAX_GOALS = 9  # score matrix is (MAX_GOALS × MAX_GOALS), goals 0..8

# 2. Bundesliga promotion / relegation zone boundaries (1-indexed positions):
# 1-2 auto-promoted, 3 promotion/relegation playoff (vs. Bundesliga's 16th),
# 17-18 relegated to 3. Liga.
ZONE_PROMOTION = (1, 2)
ZONE_PLAYOFF   = (3, 3)
ZONE_REL       = (17, 18)

_cache: dict | None = None


def reset_cache() -> None:
    global _cache
    _cache = None


async def run_simulation() -> dict:
    global _cache
    if _cache is not None:
        return _cache

    model = get_model_bl2()
    if not model.fitted:
        return {"status": "unavailable", "n_simulations": 0, "n_remaining": 0, "teams": []}

    standings, fixtures = await asyncio.gather(
        openliga.get_standings_bl2(),
        openliga.get_current_and_upcoming_fixtures_bl2(),
    )

    remaining = [f for f in fixtures if f.status in SCHEDULED_STATUSES]

    teams_ordered = [row["team_name"] for row in standings]
    n_teams = len(teams_ordered)
    team_idx = {name: i for i, name in enumerate(teams_ordered)}

    base_pts = np.array([row["points"]          for row in standings], dtype=np.float64)
    base_gd  = np.array([row["goal_difference"] for row in standings], dtype=np.float64)
    base_gf  = np.array([row["goals_for"]       for row in standings], dtype=np.float64)

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

    composite = total_pts * 1_000_000 + (total_gd + 150) * 1_000 + total_gf

    order = np.argsort(-composite, axis=1)
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
            "p_cl":         zone_prob(*ZONE_PROMOTION),
            "p_el":         0.0,
            "p_ecl":        0.0,
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
        "BL2 season simulation complete: %d fixtures, %d simulations",
        len(fixture_specs), N_SIMULATIONS,
    )
    return _cache
