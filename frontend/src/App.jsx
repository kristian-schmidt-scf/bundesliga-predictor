import { useEffect, useState, useMemo } from 'react'
import axios from 'axios'
import FixtureCard from './components/FixtureCard'
import LeagueTable from './components/LeagueTable'
import AccuracySummary from './components/AccuracySummary'
import Tipp11Summary from './components/Tipp11Summary'
import CalibrationView from './components/CalibrationView'
import BacktestView from './components/BacktestView'
import { blendScoreMatrix } from './utils/blendOdds'
import { bestTipp11Tip } from './utils/tipp11'
import './App.css'

function SoccerBallIcon() {
  return (
    <svg className="header-svg" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
      <circle cx="50" cy="50" r="44" stroke="currentColor" strokeWidth="2.5" opacity="0.5" />
      <polygon points="50,28 64,38 59,54 41,54 36,38" stroke="currentColor" strokeWidth="2" opacity="0.7" fill="currentColor" fillOpacity="0.08" />
      <line x1="50" y1="28" x2="50" y2="6"  stroke="currentColor" strokeWidth="1.5" opacity="0.4" />
      <line x1="64" y1="38" x2="84" y2="25" stroke="currentColor" strokeWidth="1.5" opacity="0.4" />
      <line x1="59" y1="54" x2="76" y2="69" stroke="currentColor" strokeWidth="1.5" opacity="0.4" />
      <line x1="41" y1="54" x2="24" y2="69" stroke="currentColor" strokeWidth="1.5" opacity="0.4" />
      <line x1="36" y1="38" x2="16" y2="25" stroke="currentColor" strokeWidth="1.5" opacity="0.4" />
    </svg>
  )
}

function ScatterIcon() {
  return (
    <svg className="header-svg" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
      <line x1="12" y1="88" x2="88" y2="88" stroke="currentColor" strokeWidth="2" opacity="0.3" strokeLinecap="round" />
      <line x1="12" y1="88" x2="12" y2="12" stroke="currentColor" strokeWidth="2" opacity="0.3" strokeLinecap="round" />
      <line x1="18" y1="75" x2="82" y2="18" stroke="#6c63ff" strokeWidth="2" opacity="0.5" strokeLinecap="round" strokeDasharray="4 3" />
      <circle cx="22" cy="72" r="4" fill="#4caf50" opacity="0.85" />
      <circle cx="34" cy="60" r="4" fill="#4caf50" opacity="0.85" />
      <circle cx="44" cy="52" r="4" fill="#4caf50" opacity="0.85" />
      <circle cx="56" cy="40" r="4" fill="#4caf50" opacity="0.85" />
      <circle cx="68" cy="30" r="4" fill="#4caf50" opacity="0.85" />
      <circle cx="30" cy="50" r="3.5" fill="#e8000f" opacity="0.7" />
      <circle cx="52" cy="64" r="3.5" fill="#e8000f" opacity="0.7" />
      <circle cx="74" cy="44" r="3.5" fill="#6c63ff" opacity="0.7" />
    </svg>
  )
}

function AppHeader() {
  return (
    <header className="app-header">
      <div className="header-banner">
        <div className="header-icon"><SoccerBallIcon /></div>
        <div className="header-center">
          <div className="header-flag-stripe" />
          <h1 className="header-title">Bundesliga Predictor</h1>
          <p className="header-subtitle">Dixon-Coles model &nbsp;·&nbsp; Bookmaker edge &nbsp;·&nbsp; Tipp 11</p>
        </div>
        <div className="header-icon"><ScatterIcon /></div>
      </div>
    </header>
  )
}

const LIVE_STATUSES = new Set(['IN_PLAY', 'PAUSED', 'LIVE'])

function groupByMatchday(predictions) {
  const groups = {}
  for (const p of predictions) {
    const day = p.fixture.matchday
    if (!groups[day]) groups[day] = []
    groups[day].push(p)
  }
  return Object.entries(groups)
    .sort(([a], [b]) => Number(a) - Number(b))
    .map(([matchday, fixtures]) => ({ matchday: Number(matchday), fixtures }))
}

const UPCOMING_STATUSES = new Set(['SCHEDULED', 'TIMED'])

function defaultMatchday(groups) {
  const live = groups.find(g => g.fixtures.some(p => LIVE_STATUSES.has(p.fixture.status)))
  if (live) return live.matchday
  const upcoming = groups.find(g => g.fixtures.some(p => UPCOMING_STATUSES.has(p.fixture.status)))
  if (upcoming) return upcoming.matchday
  const finished = groups.filter(g => g.fixtures.every(p => p.fixture.status === 'FINISHED'))
  return finished.length > 0 ? finished[finished.length - 1].matchday : groups[0]?.matchday
}

function MatchupSidebar({ predictions, onSelect, blendOdds }) {
  return (
    <aside className="matchup-sidebar">
      {predictions.map(p => {
        const { fixture, score_matrix, win_probabilities, odds } = p
        const { home_team, away_team, status, home_score, away_score } = fixture
        const isLive = LIVE_STATUSES.has(status)
        const isFinished = status === 'FINISHED'
        const hasScore = home_score != null && away_score != null

        const grid = (blendOdds && odds?.implied_home_prob)
          ? blendScoreMatrix(score_matrix.matrix, win_probabilities, odds)
          : score_matrix.matrix
        const { h, a, pts } = bestTipp11Tip(grid)

        return (
          <button
            key={fixture.id}
            className={`matchup-item${isLive ? ' live' : ''}${isFinished ? ' finished' : ''}`}
            onClick={() => onSelect(fixture.id)}
          >
            <span className="si-team si-home">
              {home_team.crest_url && <img src={home_team.crest_url} className="si-crest" alt="" />}
              <span>{home_team.short_name}</span>
            </span>
            <span className="si-score">
              {isLive && <span className="si-dot" />}
              {hasScore ? `${home_score}–${away_score}` : 'vs'}
            </span>
            <span className="si-team si-away">
              <span>{away_team.short_name}</span>
              {away_team.crest_url && <img src={away_team.crest_url} className="si-crest" alt="" />}
            </span>
            <span className="si-tip">{h}:{a} <span className="si-tip-pts">({pts.toFixed(1)}pt)</span></span>
          </button>
        )
      })}
    </aside>
  )
}

export default function App() {
  const [allPredictions, setAllPredictions] = useState([])
  const [groups, setGroups] = useState([])
  const [selectedMatchday, setSelectedMatchday] = useState(null)
  const [liveOnly, setLiveOnly] = useState(false)
  const [selectedTeam, setSelectedTeam] = useState('')
  const [favoriteTeam, setFavoriteTeam] = useState(() => localStorage.getItem('favTeam') ?? '')
  const [showTipp11, setShowTipp11] = useState(false)
  const [blendOdds, setBlendOdds] = useState(false)
  const [showTable, setShowTable] = useState(false)
  const [showCalibration, setShowCalibration] = useState(false)
  const [showBacktest, setShowBacktest] = useState(false)
  const [modelVariant, setModelVariant] = useState('base')
  const [bayesPredictions, setBayesPredictions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    axios.get(`/api/predictions/upcoming?model_variant=${modelVariant}`)
      .then(res => {
        const preds = res.data
        const g = groupByMatchday(preds)
        setAllPredictions(preds)
        setGroups(g)
        setSelectedMatchday(defaultMatchday(g))
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const teams = useMemo(() => {
    const s = new Set()
    for (const p of allPredictions) {
      s.add(p.fixture.home_team.name)
      s.add(p.fixture.away_team.name)
    }
    return [...s].sort()
  }, [allPredictions])

  const liveCount = useMemo(
    () => allPredictions.filter(p => LIVE_STATUSES.has(p.fixture.status)).length,
    [allPredictions]
  )

  const visiblePredictions = useMemo(() => {
    let preds = allPredictions

    if (liveOnly) {
      preds = preds.filter(p => LIVE_STATUSES.has(p.fixture.status))
    } else if (!selectedTeam) {
      const group = groups.find(g => g.matchday === selectedMatchday)
      preds = group ? group.fixtures : []
    }

    if (selectedTeam) {
      preds = preds.filter(p =>
        p.fixture.home_team.name === selectedTeam || p.fixture.away_team.name === selectedTeam
      )
    }

    return preds
  }, [allPredictions, groups, selectedMatchday, liveOnly, selectedTeam])

  useEffect(() => {
    setAllPredictions([])
    setGroups([])
    setSelectedMatchday(null)
    setLoading(true)
    axios.get(`/api/predictions/upcoming?model_variant=${modelVariant}`)
      .then(res => {
        const preds = res.data
        const g = groupByMatchday(preds)
        setAllPredictions(preds)
        setGroups(g)
        setSelectedMatchday(defaultMatchday(g))
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [modelVariant])

  // Fetch Bayes predictions for side-by-side Tipp 11 comparison
  useEffect(() => {
    if (!showTipp11) return
    axios.get('/api/predictions/upcoming?model_variant=bayes')
      .then(res => setBayesPredictions(res.data))
      .catch(() => setBayesPredictions([]))
  }, [showTipp11])

  function toggleFavorite() {
    if (favoriteTeam === selectedTeam) {
      localStorage.removeItem('favTeam')
      setFavoriteTeam('')
    } else {
      localStorage.setItem('favTeam', selectedTeam)
      setFavoriteTeam(selectedTeam)
    }
  }

  function scrollToFixture(id) {
    document.getElementById(`fixture-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="app">
      <AppHeader />

      <div className={`app-body${showTable || showCalibration || showBacktest ? ' no-sidebar' : ''}`}>
        {visiblePredictions.length > 0 && !showTable && !showCalibration && !showBacktest && (
          <MatchupSidebar predictions={visiblePredictions} onSelect={scrollToFixture} blendOdds={blendOdds} />
        )}

        <div className="content-column">
          {loading && <div className="status">Loading predictions…</div>}
          {error && <div className="status error">Error: {error}</div>}

          {groups.length > 0 && (
            <div className="filter-bar">
              {/* Group 1: data selection */}
              <div className="filter-group">
                <label htmlFor="matchday-select">Spieltag</label>
                <select
                  id="matchday-select"
                  value={selectedMatchday ?? ''}
                  onChange={e => { setSelectedMatchday(Number(e.target.value)); setLiveOnly(false) }}
                  disabled={liveOnly || !!selectedTeam}
                >
                  {groups.map(g => (
                    <option key={g.matchday} value={g.matchday}>Spieltag {g.matchday}</option>
                  ))}
                </select>
              </div>

              <button
                className={`filter-btn${liveOnly ? ' active' : ''}${liveCount === 0 ? ' disabled' : ''}`}
                onClick={() => { if (liveCount > 0) setLiveOnly(v => !v) }}
              >
                <span className={`live-dot${liveCount > 0 ? ' pulsing' : ''}`} />
                Live{liveCount > 0 ? ` (${liveCount})` : ''}
              </button>

              <div className="filter-separator" />

              {/* Group 2: analysis overlays */}
              <button
                className={`filter-btn${showTipp11 ? ' active' : ''}`}
                onClick={() => setShowTipp11(v => !v)}
              >
                Tipp 11
              </button>

              <button
                className={`filter-btn${blendOdds ? ' active' : ''}`}
                onClick={() => setBlendOdds(v => !v)}
                title="Blend Dixon-Coles (50%) with bookmaker implied probabilities (50%)"
              >
                Blend odds
              </button>

              <div className="filter-separator" />

              {/* Group 3: view switches */}
              <button
                className={`filter-btn${showTable ? ' view-active' : ''}`}
                onClick={() => setShowTable(v => !v)}
              >
                Table
              </button>

              <button
                className={`filter-btn${showCalibration ? ' view-active' : ''}`}
                onClick={() => setShowCalibration(v => !v)}
              >
                Calibration
              </button>

              <button
                className={`filter-btn${showBacktest ? ' view-active' : ''}`}
                onClick={() => setShowBacktest(v => !v)}
              >
                Backtest
              </button>

              <div className="filter-separator" />

              {/* Group 4: model selector */}
              <button
                className={`filter-btn${modelVariant === 'bayes' ? ' model-active' : ''}`}
                onClick={() => setModelVariant(v => v === 'base' ? 'bayes' : 'base')}
                title="Toggle between base Dixon-Coles and Bayesian prior model"
              >
                {modelVariant === 'bayes' ? 'Bayes Prior' : 'Base Model'}
              </button>

              <div className="filter-group team-filter">
                <label htmlFor="team-select">Team</label>
                <select
                  id="team-select"
                  value={selectedTeam}
                  onChange={e => { setSelectedTeam(e.target.value); setLiveOnly(false) }}
                >
                  <option value="">All teams</option>
                  {teams.map(t => (
                    <option key={t} value={t}>
                      {favoriteTeam === t ? '★ ' : ''}{t}
                    </option>
                  ))}
                </select>
                {selectedTeam && (
                  <button
                    className={`fav-btn${favoriteTeam === selectedTeam ? ' active' : ''}`}
                    onClick={toggleFavorite}
                    title={favoriteTeam === selectedTeam ? 'Remove favourite' : 'Set as favourite'}
                  >
                    ★
                  </button>
                )}
              </div>
            </div>
          )}

          {!showTable && !showCalibration && !showBacktest && <AccuracySummary predictions={visiblePredictions} />}
          {!showTable && !showCalibration && !showBacktest && showTipp11 && (
            <Tipp11Summary
              predictions={visiblePredictions}
              bayesPredictions={bayesPredictions}
              useBlend={blendOdds}
            />
          )}

          {showBacktest ? (
            <BacktestView />
          ) : showCalibration ? (
            <CalibrationView />
          ) : showTable ? (
            <LeagueTable />
          ) : (
            <>
              {visiblePredictions.length === 0 && !loading && (
                <div className="status">
                  {liveOnly ? 'No games currently live.' : 'No fixtures to show.'}
                </div>
              )}
              <div className="fixture-list">
                {visiblePredictions.map(p => (
                  <div key={p.fixture.id} id={`fixture-${p.fixture.id}`}>
                    <FixtureCard prediction={p} showTipp11={showTipp11} blendOdds={blendOdds} />
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
