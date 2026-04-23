# Bundesliga Predictor

![Python](https://img.shields.io/badge/Python-3.11-3776ab?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61dafb?logo=react&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-5-646cff?logo=vite&logoColor=white)

A personal project that predicts Bundesliga match outcomes using a statistical football model, and compares those predictions against bookmaker odds to find edges. It also serves as a Tipp 11 assistant — working out which scoreline tip maximises your expected points for each fixture.

The app pulls three seasons of historical results on startup, fits a Dixon-Coles Poisson model, and serves predictions for every upcoming fixture. A React frontend displays score probability heatmaps, win/draw/loss bars, bookmaker odds comparisons, and a live league table with model-projected final standings.

---

## Features

- **Match predictions** — 9×9 score probability heatmap, win/draw/loss probabilities, expected goals, most likely scoreline
- **Bookmaker edge** — live EU odds fetched at request time, normalised implied probabilities, edge per outcome highlighted
- **Tipp 11 assistant** — optimal tip per fixture based on expected Tipp 11 points; round summary showing actual vs expected
- **Model blend** — toggle a 50/50 Dixon-Coles + bookmaker blend affecting all outputs
- **League table** — live standings with model-implied projected points for remaining fixtures
- **Calibration** — Brier score, log-loss, per-matchday chart, and an ablation table comparing 8 model variants
- **Back-testing** — walk-forward backtest over Spieltage 18–30: tendency accuracy, Brier, log-loss, Tipp 11 expected vs actual

---

## Model

The foundation is the [Dixon-Coles model](https://doi.org/10.1111/1467-9876.00065), which estimates per-team attack and defence strengths by maximising the time-weighted log-likelihood of historical scorelines. A low-score correction (ρ) adjusts joint probabilities for the 0-0, 1-0, 0-1, and 1-1 scorelines where goal independence breaks down.

On top of the base model, four adjustments are applied at prediction time:

- **Per-team home advantage** — each team gets its own γ fitted from ~17 home games per season rather than a single global factor
- **H2H shrinkage** — Bayesian nudge of expected goals toward historical head-to-head averages (k=5 shrinkage)
- **Form scaling** — multiplies expected goals by a form factor derived from each team's points-per-game over their last 5 matches
- **Fatigue / travel** — rest-day penalty (optimal at 7 days, penalised below 4 or above 14) and a haversine travel distance penalty on the away side

The calibration ablation table measures whether each of these adjustments actually improves predictive accuracy, making it easy to see which ones earn their place.

---

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Free API keys from [football-data.org](https://www.football-data.org/) and [The Odds API](https://the-odds-api.com/)

### Backend

```bash
cd backend
python -m venv .venv

# Windows
.\.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Create `backend/.env`:

```env
FOOTBALL_DATA_API_KEY=your_key_here
ODDS_API_KEY=your_key_here
```

Start the server:

```bash
python -m uvicorn app.main:app
```

On startup the model fetches ~1,100 historical matches and fits in around 10 seconds. Swagger docs are at `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies all `/api` calls to the backend automatically.

---

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/health` | Model status and team count |
| `GET /api/predictions/upcoming` | Predictions for upcoming fixtures (`?model_variant=bayes` for the bookmaker-prior variant) |
| `GET /api/predictions/match` | Ad-hoc prediction (`?home_team=X&away_team=Y`) |
| `GET /api/fixtures/upcoming` | Raw fixture list |
| `GET /api/table` | League table + model-projected standings |
| `GET /api/calibration` | Brier score, log-loss, per-matchday breakdown, ablation variants |
| `GET /api/backtest` | Walk-forward backtest results (computed lazily on first request) |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `FOOTBALL_DATA_API_KEY` | — | Required |
| `ODDS_API_KEY` | — | Required |
| `seasons_to_fetch` | `3` | Seasons of historical data used for model fitting |
| `time_decay_half_life_days` | `90` | Exponential weighting half-life for recent matches |
