import { useState, useEffect } from 'react'
import './H2HPanel.css'

export default function H2HPanel({ homeTeam, awayTeam, homeShort, awayShort }) {
  const [open, setOpen] = useState(false)
  const [data, setData] = useState(null)
  const [fetchError, setFetchError] = useState(false)

  const loading = open && data === null && !fetchError

  useEffect(() => {
    if (!open || data !== null || fetchError) return
    fetch(`/api/h2h/matches?home_team=${encodeURIComponent(homeTeam)}&away_team=${encodeURIComponent(awayTeam)}`)
      .then(r => r.json())
      .then(d => setData(d))
      .catch(() => setFetchError(true))
  }, [open, homeTeam, awayTeam, data, fetchError])

  return (
    <div className="h2h-panel">
      <button className="h2h-toggle" onClick={() => setOpen(o => !o)}>
        H2H {open ? '▲' : '▼'}
      </button>
      {open && (
        <div className="h2h-content">
          {loading && <span className="h2h-loading">Loading…</span>}
          {data && data.matches.length === 0 && (
            <span className="h2h-empty">No historical meetings found</span>
          )}
          {data && data.matches.length > 0 && (
            <>
              <div className="h2h-summary">
                <span className="h2h-team">{homeShort}</span>
                <span className="h2h-record">
                  <span className="win">{data.home_wins}W</span>
                  {' '}<span className="draw">{data.draws}D</span>
                  {' '}<span className="loss">{data.away_wins}L</span>
                </span>
                <span className="h2h-vs">vs</span>
                <span className="h2h-team">{awayShort}</span>
                <span className="h2h-count">last {data.matches.length}</span>
              </div>
              <div className="h2h-matches">
                {data.matches.map((m, i) => {
                  const cls = m.result === 'HOME_WIN' ? 'win' : m.result === 'DRAW' ? 'draw' : 'loss'
                  const label = m.result === 'HOME_WIN' ? 'W' : m.result === 'DRAW' ? 'D' : 'L'
                  return (
                    <div key={i} className="h2h-row">
                      <span className="h2h-date">{m.date.slice(0, 7)}</span>
                      <span className="h2h-scoreline">
                        {m.home_team} <strong>{m.home_goals}–{m.away_goals}</strong> {m.away_team}
                      </span>
                      <span className={`h2h-result-badge ${cls}`}>{label}</span>
                    </div>
                  )
                })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
