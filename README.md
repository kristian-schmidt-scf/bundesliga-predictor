# Bundesliga Predictor

A full-stack football prediction app powered by the **Dixon-Coles Poisson model**. Predicts Bundesliga match outcomes, compares model probabilities against bookmaker odds, and recommends optimal tips for the **Tipp 11** scoring system.

![Python](https://img.shields.io/badge/Python-3.11-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green) ![React](https://img.shields.io/badge/React-18-61dafb)

---

## Features

**Predictions**
- Dixon-Coles Poisson model fit on 3 seasons of Bundesliga results (~1,100 matches)
- Exponential time decay (90-day half-life) so recent form weighs more
- Head-to-head history adjustment via Bayesian shrinkage
- 9×9 score probability matrix per fixture
- Win / draw / loss probabilities

**Bookmaker comparison**
- Live odds from The Odds API (EU markets)
- Implied probabilities extracted and normalised
- Edge per outcome: model probability minus bookmaker implied probability
- Optional 50/50 blend of model and bookmaker probabilities

**Tipp 11**
- Expected points per possible tip, computed from the score matrix
- Scoring system: Heimtore (+1), Gasttore (+1), Tendenz (+2), Differenz (+2), Basis (max 5, decays with goal error)
- Best tip shown in the sidebar for each fixture, using the blended model

**Frontend**
- Sticky sidebar listing all fixtures for the current selection with team crests, scores, and best Tipp 11 tip
- Score heatmap and Tipp 11 expected-points heatmap per fixture
- Spieltag navigation, live game filter, team filter with favourite
- Toggle between pure Dixon-Coles and bookmaker-blended predictions

---

## Architecture

```
bundesliga-predictor/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI app, model fitted on startup
│   │   ├── config.py             # Settings via pydantic-settings + .env
│   │   ├── models/schemas.py     # Pydantic schemas
│   │   ├── routers/
│   │   │   ├── fixtures.py       # GET /api/fixtures/upcoming
│   │   │   └── predictions.py    # GET /api/predictions/upcoming
│   │   └── services/
│   │       ├── dixon_coles.py    # Model fitting + prediction
│   │       ├── football_data.py  # football-data.org client
│   │       ├── odds.py           # The Odds API client
│   │       └── prediction_cache.py
│   └── requirements.txt
└── frontend/
    └── src/
        ├── App.jsx               # Layout, filters, sidebar
        ├── components/
        │   ├── FixtureCard.jsx
        │   ├── ScoreHeatmap.jsx
        │   ├── Tipp11Heatmap.jsx
        │   └── OddsComparison.jsx
        └── utils/
            ├── tipp11.js         # Scoring logic + expected points
            └── blendOdds.js      # 50/50 model + bookmaker blend
```

---

## Getting started

### Prerequisites

- Python 3.11+
- Node.js 18+
- API keys from:
  - [football-data.org](https://www.football-data.org/) (free tier works)
  - [The Odds API](https://the-odds-api.com/) (free tier works)

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

```
FOOTBALL_DATA_API_KEY=your_key_here
ODDS_API_KEY=your_key_here
```

Start the server:

```bash
python -m uvicorn app.main:app
```

The model fetches 3 seasons of results and fits on startup (~10 seconds). Visit `http://localhost:8000/docs` for the interactive API docs.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The Vite dev server proxies `/api` requests to the backend automatically.

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Model status |
| GET | `/api/predictions/upcoming` | Predictions for current matchday |
| GET | `/api/fixtures/upcoming` | Raw fixture list |
| GET | `/api/predictions/match?home_team=X&away_team=Y` | Ad-hoc prediction |

---

## Model details

The [Dixon-Coles model](https://doi.org/10.1111/1467-9876.00065) estimates attack (α) and defence (δ) strength parameters for each team by maximising the weighted log-likelihood of historical scorelines:

```
λ (home expected goals) = α_home × δ_away × γ
μ (away expected goals) = α_away × δ_home
```

where γ is a global home advantage parameter. A low-score correction factor (ρ) adjusts joint probabilities for 0-0, 1-0, 0-1, and 1-1 scorelines.

**H2H adjustment:** Before producing a prediction, λ and μ are nudged toward the empirical average goals in historical head-to-head matches using Bayesian shrinkage (k=5). Reversed fixtures are normalised by γ before pooling to remove the home advantage signal.

---

## Configuration

All model settings live in `backend/.env` or can be overridden via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `FOOTBALL_DATA_API_KEY` | — | Required |
| `ODDS_API_KEY` | — | Required |
| `seasons_to_fetch` | `3` | Seasons of historical data |
| `time_decay_half_life_days` | `90` | Exponential decay half-life |
