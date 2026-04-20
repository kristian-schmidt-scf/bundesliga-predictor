import { useEffect, useState, useMemo } from 'react'
import axios from 'axios'
import FixtureCard from './components/FixtureCard'
import './App.css'

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

function defaultMatchday(groups) {
  // 1. Matchday with live games
  const live = groups.find(g => g.fixtures.some(p => LIVE_STATUSES.has(p.fixture.status)))
  if (live) return live.matchday
  // 2. Next upcoming matchday
  const upcoming = groups.find(g => g.fixtures.some(p => p.fixture.status === 'SCHEDULED'))
  if (upcoming) return upcoming.matchday
  // 3. Last fully finished matchday
  const finished = groups.filter(g => g.fixtures.every(p => p.fixture.status === 'FINISHED'))
  return finished.length > 0 ? finished[finished.length - 1].matchday : groups[0]?.matchday
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
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    axios.get('/api/predictions/upcoming')
      .then(res => {
        const preds = res.data
        const g = groupByMatchday(preds)
        setAllPredictions(preds)
        setGroups(g)
        const favTeam = localStorage.getItem('favTeam') ?? ''
        setSelectedTeam(favTeam)
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

  function toggleFavorite() {
    if (favoriteTeam === selectedTeam) {
      localStorage.removeItem('favTeam')
      setFavoriteTeam('')
    } else {
      localStorage.setItem('favTeam', selectedTeam)
      setFavoriteTeam(selectedTeam)
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>Bundesliga Predictor</h1>
        <p className="subtitle">Dixon-Coles model vs bookmaker odds</p>
      </header>

      <main className="fixture-list">
        {loading && <div className="status">Loading predictions…</div>}
        {error && <div className="status error">Error: {error}</div>}

        {groups.length > 0 && (
          <div className="filter-bar">
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
              className={`live-btn${liveOnly ? ' active' : ''}${liveCount === 0 ? ' disabled' : ''}`}
              onClick={() => { if (liveCount > 0) setLiveOnly(v => !v) }}
            >
              <span className={`live-dot${liveCount > 0 ? ' pulsing' : ''}`} />
              Live{liveCount > 0 ? ` (${liveCount})` : ''}
            </button>

            <button
              className={`live-btn${showTipp11 ? ' active' : ''}`}
              onClick={() => setShowTipp11(v => !v)}
            >
              Tipp 11
            </button>

            <button
              className={`live-btn${blendOdds ? ' active' : ''}`}
              onClick={() => setBlendOdds(v => !v)}
              title="Blend Dixon-Coles (50%) with bookmaker implied probabilities (50%)"
            >
              + Bookmaker Odds
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

        {visiblePredictions.length === 0 && !loading && (
          <div className="status">
            {liveOnly ? 'No games currently live.' : 'No fixtures to show.'}
          </div>
        )}

        {visiblePredictions.map(p => (
          <FixtureCard key={p.fixture.id} prediction={p} showTipp11={showTipp11} blendOdds={blendOdds} />
        ))}
      </main>
    </div>
  )
}
