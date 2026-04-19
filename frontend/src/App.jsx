import { useEffect, useState } from 'react'
import axios from 'axios'
import FixtureCard from './components/FixtureCard'
import './App.css'

export default function App() {
  const [predictions, setPredictions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    axios.get('/api/predictions/upcoming')
      .then(res => setPredictions(res.data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="app">
      <header className="app-header">
        <h1>Bundesliga Predictor</h1>
        <p className="subtitle">Dixon-Coles model vs bookmaker odds</p>
      </header>

      <main className="fixture-list">
        {loading && <div className="status">Loading predictions…</div>}
        {error && <div className="status error">Error: {error}</div>}
        {predictions.map(p => (
          <FixtureCard key={p.fixture.id} prediction={p} />
        ))}
      </main>
    </div>
  )
}
