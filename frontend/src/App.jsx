import { useEffect, useState } from 'react'
import axios from 'axios'
import FixtureCard from './components/FixtureCard'
import './App.css'

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

function lastFullyFinishedMatchday(groups) {
  const finished = groups.filter(g =>
    g.fixtures.length > 0 && g.fixtures.every(p => p.fixture.status === 'FINISHED')
  )
  return finished.length > 0 ? finished[finished.length - 1].matchday : groups[0]?.matchday
}

export default function App() {
  const [groups, setGroups] = useState([])
  const [selectedMatchday, setSelectedMatchday] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    axios.get('/api/predictions/upcoming')
      .then(res => {
        const g = groupByMatchday(res.data)
        setGroups(g)
        setSelectedMatchday(lastFullyFinishedMatchday(g))
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const current = groups.find(g => g.matchday === selectedMatchday)

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
          <div className="matchday-selector">
            <label htmlFor="matchday-select">Spieltag</label>
            <select
              id="matchday-select"
              value={selectedMatchday ?? ''}
              onChange={e => setSelectedMatchday(Number(e.target.value))}
            >
              {groups.map(g => (
                <option key={g.matchday} value={g.matchday}>
                  Spieltag {g.matchday}
                </option>
              ))}
            </select>
          </div>
        )}

        {current && current.fixtures.map(p => (
          <FixtureCard key={p.fixture.id} prediction={p} />
        ))}
      </main>
    </div>
  )
}
