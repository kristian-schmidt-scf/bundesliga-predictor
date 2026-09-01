# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend
```bash
cd backend
source .venv/bin/activate          # Linux/macOS
# .\.venv\Scripts\Activate.ps1    # Windows PowerShell
pip install -r requirements.txt
python -m uvicorn app.main:app --reload   # http://localhost:8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 (proxies /api to :8000)
npm run build
npm run lint
npm run preview
```

To expose the dev server on the local network (for PWA testing on mobile):
```bash
npm run dev -- --host
```

No test suite exists in this repo.

## Environment Variables

`backend/.env` (required):
- `FOOTBALL_DATA_API_KEY` — from football-data.org
- `ODDS_API_KEY` — from the-odds-api.com (500 req/month free tier — treat as scarce)
- `seasons_to_fetch` — default 3
- `time_decay_half_life_days` — default 90
- `refit_hour` — hour of day (0–23) for daily model refit, default 6
- `odds_poll_interval_seconds` — interval between odds snapshots, default 43200 (12 h)
- `odds_db_path` — SQLite file for odds history, default `odds_history.db`
- `picks_db_path` — SQLite file for user Tipp 11 picks, default `user_picks.db`
- `prediction_cache_db_path` — SQLite file for frozen predictions, default `prediction_cache.db`

## Architecture

### Overview
Monorepo: `backend/` (FastAPI) + `frontend/` (React + Vite). The frontend dev server proxies `/api/*` to `http://localhost:8000` via Vite config. CORS allows `localhost:5173` and `localhost:3000`.

The app covers two competitions: the top-flight Bundesliga (BL1, sourced from football-data.org + The Odds API) and 2. Bundesliga (BL2, sourced entirely from OpenLigaDB since football-data.org's free tier doesn't include it — no API key, no odds, single model variant). BL2 fixture IDs are offset by `BL2_ID_OFFSET = 1_000_000_000` (see `openliga.py`) so they can never collide with football-data.org's IDs, which lets picks, the prediction cache, and every other int-keyed table treat BL2 fixtures exactly like BL1 ones with no schema changes.

The app is also a PWA: `frontend/public/manifest.json` + `frontend/public/sw.js` allow home-screen installation on iOS/Android. The service worker uses stale-while-revalidate for the app shell and bypasses the cache for all `/api/*` requests.

### Startup Sequence (`app/main.py` lifespan)
On startup, the backend:
1. Initialises three SQLite databases: odds history, user picks, prediction cache
2. Loads 7 seasons of static historical data (`historical_data.py`) + fetches 3 live seasons from football-data.org
3. Fits the base Dixon-Coles model on the merged dataset
4. Fetches current bookmaker odds from The Odds API (module-level cache — no extra call if already cached)
5. Fits the Bayesian-prior model (same model but market-implied goals as priors)
6. Seeds opening odds snapshots from the startup fetch (no extra API call)
7. Fetches 2. Bundesliga data from OpenLigaDB and fits a third model instance (`get_model_bl2()`), isolated in its own try/except so a BL2/OpenLigaDB hiccup never takes down BL1
8. Launches four background tasks: daily refit loop, odds poll loop, pre-kickoff snapshot loop, cross-competition fixture cache refresh loop

### Background Tasks
| Task | Cadence | Purpose |
|------|---------|---------|
| `_daily_refit_loop` | Daily at `refit_hour` | Refetch results, refit base/Bayes models, then refit the BL2 model (each isolated in its own try/except) |
| `_odds_poll_loop` | Every `odds_poll_interval_seconds` (12 h) | Snapshot odds to SQLite |
| `_pre_kickoff_snapshot_loop` | Every 5 min | One-shot snapshot 5–90 min before each kickoff (closing line) |
| `_recent_fixtures_loop` | Daily (immediate on startup) | Refresh cross-competition fixture dates for fatigue computation (BL1 teams only — BL2 predictions use in-league rest days only, no DFB-Pokal/European cross-reference) |

### Core Model (`app/services/dixon_coles.py`)
Dixon-Coles Poisson regression with per-team attack (α), defence (δ), and home advantage (γ) parameters, plus a low-score correction factor (τ/rho). Predictions are adjusted at request time with:
- **H2H shrinkage** — Bayesian blend toward head-to-head historical averages (k=5 prior)
- **Form scaling** — last 5 matches points-per-game
- **Rest penalty** — optimal at 7 days; penalised for <4 or >14 days; accounts for European/DFB-Pokal fixtures via `recent_fixtures.py` (BL1 only)
- **Travel penalty** — haversine distance, max 3% at 800+ km
- **Time decay** — 90-day half-life weighting during fitting

α, δ, and γ all get adaptive shrinkage toward the league average during fitting (`SHRINKAGE_K`, coefficient = `K / (effective_n + K)`), and recent-form scaling gets the same treatment (`FORM_SHRINK_K`) — without this, a team with almost no time-weighted match history (a newly promoted club, or one with a winless recent-form window) has nothing stopping its MLE estimate from collapsing to exactly 0, zeroing its predicted goals outright. Negligible effect on well-observed teams, strong effect on data-starved ones.

Three module-level singleton model instances exist: `base` and `bayes` (market-informed priors) for the Bundesliga, and `bl2` for 2. Bundesliga (base fit only — no market-informed variant, since BL2 has no odds data). The `?model_variant=base|bayes` query param selects between the first two on the BL1 endpoints; BL2 is served from separate `/api/bl2/*` routes with no variant param.

### Services (`app/services/`)
| File | Purpose |
|------|---------|
| `dixon_coles.py` | Model fitting, prediction, stadium coords, rest/travel factors |
| `football_data.py` | Fixtures/results from football-data.org (async, rate-limited, 5-min cache on standings) — BL1 only |
| `openliga.py` | Fixtures/results/standings for 2. Bundesliga from OpenLigaDB (no API key, no rate limit); offsets every fixture ID by `BL2_ID_OFFSET` to avoid collision with football-data.org IDs |
| `historical_data.py` | Loads 7 seasons of static JSON scraped from football-data.org (BL1 only — BL2 has no static dataset, OpenLigaDB is queried live for historical seasons) |
| `odds.py` | Bookmaker odds from The Odds API; module-level `_odds_cache` prevents redundant calls — BL1 only |
| `odds_history.py` | SQLite persistence for odds snapshots (used by CLV tracker) — BL1 only |
| `user_picks.py` | SQLite persistence for user and opponent Tipp 11 picks; shared across BL1 and BL2 since fixture IDs never collide |
| `prediction_cache_db.py` | SQLite write-through cache; `ON CONFLICT DO NOTHING` freezes predictions at kickoff permanently; registers `base`, `bayes`, and `base_bl2` variants |
| `prediction_cache.py` | Thin shim: re-exports `get/set/get_all` from `prediction_cache_db.base` |
| `prediction_cache_bayes.py` | Same shim for `prediction_cache_db.bayes` |
| `prediction_cache_bl2.py` | Same shim for `prediction_cache_db.base_bl2` |
| `recent_fixtures.py` | Cross-competition fixture cache (European comps via football-data.org + DFB-Pokal via OpenLigaDB); refreshed daily in background — BL1 teams only |
| `backtest.py` | Walk-forward backtest for Spieltage 18–30 (lazy: computed on first request) — BL1 only |
| `simulation.py` | Monte Carlo season simulation (10 000 runs) for Bundesliga; CL/EL/ECL/playoff/relegation zones |
| `simulation_bl2.py` | Same Monte Carlo core for 2. Bundesliga, sourced from `openliga.py` / `get_model_bl2()`; promotion/playoff/relegation zones instead of European ones |

### Odds API Budget
The Odds API free tier allows 500 requests/month. Calls are tightly controlled:
- **Startup**: 1 call (seeded into module-level cache)
- **Odds poll loop**: 2 calls/day × ~30 days ≈ 60 calls/month
- **Pre-kickoff snapshot**: 1 call per matchday batch (≈ 10/month during the season)
- **Prediction endpoint**: always reads from cache — never triggers a live API call

### API Routers (`app/routers/`)
| Route | Description |
|-------|-------------|
| `GET /api/predictions/upcoming` | Main endpoint — fixtures + score matrix + win probs + bookmaker edges |
| `GET /api/fixtures/upcoming` | Raw fixture list |
| `GET /api/table` | Standings + model-projected final points |
| `GET /api/calibration` | Brier/log-loss scores + 8-variant ablation table |
| `GET /api/backtest` | Walk-forward results per matchday |
| `GET /api/model_params` | Per-team α/δ/γ parameters |
| `GET /api/simulation` | Monte Carlo season simulation result |
| `GET /api/teams/{team_name}` | Team profile (form, fixtures, model params) |
| `GET /api/h2h/matches` | Head-to-head history for a fixture |
| `GET /api/odds/history` | Odds movement history for a fixture |
| `GET /api/clv` | Closing line value report for settled picks |
| `GET /api/picks` | User's Tipp 11 picks |
| `PUT /api/picks/{fixture_id}` | Save / update a pick |
| `DELETE /api/picks/{fixture_id}` | Remove a pick |
| `GET /api/picks/opponent` | Opponent's picks |
| `PUT /api/picks/opponent/{fixture_id}` | Save / update opponent pick |
| `DELETE /api/picks/opponent/{fixture_id}` | Remove opponent pick |
| `GET /api/bl2/fixtures/upcoming` | 2. Bundesliga predictions — same `Prediction` shape as `/api/predictions/upcoming`, `odds`/`edge_*` always `null`, no `model_variant` param |
| `GET /api/bl2/table` | 2. Bundesliga standings + model-projected final points |
| `GET /api/bl2/h2h/matches` | Head-to-head history between two 2. Bundesliga teams |
| `GET /api/bl2/simulation` | 2. Bundesliga Monte Carlo season simulation |

Settled match predictions are frozen at kickoff via the SQLite prediction cache and survive server restarts. `/api/picks/*` and the prediction cache are shared across both competitions — see the `BL2_ID_OFFSET` note in the Overview above.

### Frontend (`frontend/src/`)
- **`App.jsx`** — Main router, `activeTab` navigation across both competitions (`fixtures`/`table` for BL1, `fixtures-bl2`/`table-bl2` for BL2), model variant toggle (BL1 only), blend toggle. Fixture-fetching/filtering/live-polling state is extracted into a `useFixtures` hook and instantiated once per competition, so BL1 and BL2 matchday selection, team filter, and favourite team never share state
- **`FixtureCard.jsx`** — Per-fixture card with sidebar + expanded main view; live score polling every 20 s (via the parent's `useFixtures` poll, not a per-card fetch); odds panel auto-omits when `odds` is `null` (always the case for BL2), no BL2-specific code needed
- **`ScoreHeatmap.jsx`** — 9×9 score probability matrix
- **`OddsComparison.jsx`** — Model vs bookmaker edge bars (averaged across all bookmakers) — BL1 only, never rendered for BL2
- **`Tipp11Heatmap.jsx` / `Tipp11Summary.jsx`** — Expected-points matrix + best tip for Tipp 11; live scores with provisional points shown during in-play games; work unmodified for BL2 (keyed by fixture ID, which never collides across competitions)
- **`LeagueTable.jsx`** — Standings + projected final points; takes `tableEndpoint`/`simEndpoint`/`zones` props (defaulting to BL1's) so the same component serves both competitions' table tabs
- **`CalibrationView.jsx`** — Calibration metrics + ablation table — BL1 only
- **`BacktestView.jsx`** — Walk-forward backtest results — BL1 only
- **`AccuracySummary.jsx`** — Overall metrics dashboard
- **`TeamProfile.jsx`** — Team detail page (form, upcoming fixtures, model parameters) — BL1 only
- **`H2HPanel.jsx`** — Head-to-head history panel inside FixtureCard; takes an `endpoint` prop (defaults to `/api/h2h/matches`, BL2 fixtures pass `/api/bl2/h2h/matches`)
- **`CLVView.jsx`** — Closing line value tracker; shows edge captured vs closing market — BL1 only (BL2 has no odds)

Key utilities:
- `utils/tipp11.js` — Score point calculation, expected-points matrix, best-tip selection
- `utils/blendOdds.js` — 50/50 blend of Dixon-Coles + bookmaker probabilities
- `utils/leagueZones.js` — `BL1_ZONES` (CL/EL/ECL/playoff/relegation) and `BL2_ZONES` (promotion/playoff/relegation) configs consumed by `LeagueTable.jsx`

The app is mobile-responsive: CSS media queries at ≤768px (tablet) and ≤480px (phone). Wide tables use `overflow-x: auto` with a `min-width` to stay scrollable rather than wrapping.
