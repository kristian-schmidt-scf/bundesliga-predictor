import { useState, useEffect } from 'react'
import './OddsComparison.css'

function EdgeBadge({ edge }) {
  if (edge == null) return null
  const pct = (edge * 100).toFixed(1)
  const cls = edge >= 0.03 ? 'positive' : edge <= -0.03 ? 'negative' : 'neutral'
  return <span className={`edge-badge ${cls}`}>{edge >= 0 ? '+' : ''}{pct}%</span>
}

function MoveBadge({ move }) {
  if (!move) return null
  if (move.direction === 'stable') return <span className="move-badge stable" title="No significant movement">→</span>
  const sign = move.direction === 'shortened' ? '+' : ''
  const title = `${sign}${(move.delta * 100).toFixed(1)}pp since opening`
  if (move.direction === 'shortened') return <span className="move-badge shortened" title={title}>↑</span>
  return <span className="move-badge lengthened" title={title}>↓</span>
}

export default function OddsComparison({ fixtureId, odds, winProbabilities, edges, homeShort, awayShort }) {
  const [movement, setMovement] = useState(null)

  useEffect(() => {
    if (!fixtureId) return
    fetch(`/api/odds/history?fixture_id=${fixtureId}`)
      .then(r => r.json())
      .then(d => {
        if (d.movement_home || d.movement_draw || d.movement_away) setMovement(d)
      })
      .catch(() => {})
  }, [fixtureId])

  const rows = [
    {
      label: homeShort,
      decimal: odds.home_win,
      implied: odds.implied_home_prob,
      model: winProbabilities.home_win,
      edge: edges.home,
      move: movement?.movement_home,
    },
    {
      label: 'Draw',
      decimal: odds.draw,
      implied: odds.implied_draw_prob,
      model: winProbabilities.draw,
      edge: edges.draw,
      move: movement?.movement_draw,
    },
    {
      label: awayShort,
      decimal: odds.away_win,
      implied: odds.implied_away_prob,
      model: winProbabilities.away_win,
      edge: edges.away,
      move: movement?.movement_away,
    },
  ]

  const hasMovement = !!movement

  return (
    <div className="odds-table">
      <div className="odds-bookmaker">📊 {odds.bookmaker}</div>
      <table>
        <thead>
          <tr>
            <th>Outcome</th>
            <th>Odds</th>
            {hasMovement && <th>Move</th>}
            <th>Book %</th>
            <th>Model %</th>
            <th>Edge</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.label} className={row.edge != null && row.edge >= 0.03 ? 'value-row' : ''}>
              <td>{row.label}</td>
              <td>{row.decimal?.toFixed(2) ?? '–'}</td>
              {hasMovement && <td><MoveBadge move={row.move} /></td>}
              <td>{row.implied != null ? (row.implied * 100).toFixed(1) + '%' : '–'}</td>
              <td>{(row.model * 100).toFixed(1)}%</td>
              <td><EdgeBadge edge={row.edge} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
