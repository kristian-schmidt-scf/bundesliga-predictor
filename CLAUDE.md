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

No test suite exists in this repo.

## Environment Variables

`backend/.env` (required):
- `FOOTBALL_DATA_API_KEY` — from football-data.org
- `ODDS_API_KEY` — from the-odds-api.com
- `seasons_to_fetch` — default 3
- `time_decay_half_life_days` — default 90

## Architecture

### Overview
Monorepo: `backend/` (FastAPI) + `frontend/` (React + Vite). The frontend dev server proxies `/api/*` to `http://localhost:8000` via Vite config. CORS allows `localhost:5173` and `localhost:3000`.

### Startup Sequence (`app/main.py` lifespan)
On startup, the backend:
1. Fetches 3 seasons of historical Bundesliga matches from football-data.org
2. Fits the base Dixon-Coles model on historical + current season results
3. Fetches current bookmaker odds from The Odds API
4. Fits the Bayesian-prior model (same model but market-implied goals as priors)
5. Pre-fetches data for the lazy backtest

### Core Model (`app/services/dixon_coles.py`)
Dixon-Coles Poisson regression with per-team attack (α), defence (δ), and home advantage (γ) parameters, plus a low-score correction factor (τ/rho). Predictions are adjusted at request time with:
- **H2H shrinkage** — Bayesian blend toward head-to-head historical averages (k=5 prior)
- **Form scaling** — last 5 matches points-per-game
- **Rest penalty** — optimal at 7 days; penalised for <4 or >14 days
- **Travel penalty** — haversine distance, max 3% at 800+ km
- **Time decay** — 90-day half-life weighting during fitting

Two module-level singleton model instances exist: `base` and `bayes` (market-informed priors). The `?model_variant=base|bayes` query param selects which is used.

### Services (`app/services/`)
| File | Purpose |
|------|---------|
| `dixon_coles.py` | Model fitting, prediction, stadium coords, rest/travel factors |
| `football_data.py` | Fixtures/results from football-data.org (async, rate-limited, cached) |
| `odds.py` | Bookmaker odds from The Odds API (500 req/month free tier) |
| `prediction_cache.py` | In-memory cache of base-model predictions for settled matches |
| `prediction_cache_bayes.py` | Same for Bayes model |
| `backtest.py` | Walk-forward backtest for Spieltage 18–30 (lazy: computed on first request) |

### API Routers (`app/routers/`)
| Route | Description |
|-------|-------------|
| `GET /api/predictions/upcoming` | Main endpoint — fixtures + score matrix + win probs + bookmaker edges |
| `GET /api/fixtures/upcoming` | Raw fixture list |
| `GET /api/table` | Standings + model-projected final points |
| `GET /api/calibration` | Brier/log-loss scores + 8-variant ablation table |
| `GET /api/backtest` | Walk-forward results per matchday |
| `GET /api/model_params` | Per-team α/δ/γ parameters |

Settled match predictions are frozen at kickoff via the prediction cache to prevent recalculation.

### Frontend (`frontend/src/`)
- **`App.jsx`** — Main router, matchday grouping, model variant toggle, blend toggle
- **`FixtureCard.jsx`** — Per-fixture card with sidebar + expanded main view
- **`ScoreHeatmap.jsx`** — 9×9 score probability matrix
- **`OddsComparison.jsx`** — Model vs bookmaker edge bars
- **`Tipp11Heatmap.jsx` / `Tipp11Summary.jsx`** — Expected-points matrix + best tip for Tipp 11
- **`LeagueTable.jsx`** — Standings + projected final points
- **`CalibrationView.jsx`** — Calibration metrics + ablation table
- **`BacktestView.jsx`** — Walk-forward backtest results
- **`AccuracySummary.jsx`** — Overall metrics dashboard

Key utilities:
- `utils/tipp11.js` — Score point calculation, expected-points matrix, best-tip selection
- `utils/blendOdds.js` — 50/50 blend of Dixon-Coles + bookmaker probabilities
