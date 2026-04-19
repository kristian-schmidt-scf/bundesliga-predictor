import './OddsComparison.css'

function EdgeBadge({ edge }) {
  if (edge == null) return null
  const pct = (edge * 100).toFixed(1)
  const cls = edge >= 0.03 ? 'positive' : edge <= -0.03 ? 'negative' : 'neutral'
  return <span className={`edge-badge ${cls}`}>{edge >= 0 ? '+' : ''}{pct}%</span>
}

export default function OddsComparison({ odds, winProbabilities, edges, homeShort, awayShort }) {
  const rows = [
    {
      label: homeShort,
      decimal: odds.home_win,
      implied: odds.implied_home_prob,
      model: winProbabilities.home_win,
      edge: edges.home,
    },
    {
      label: 'Draw',
      decimal: odds.draw,
      implied: odds.implied_draw_prob,
      model: winProbabilities.draw,
      edge: edges.draw,
    },
    {
      label: awayShort,
      decimal: odds.away_win,
      implied: odds.implied_away_prob,
      model: winProbabilities.away_win,
      edge: edges.away,
    },
  ]

  return (
    <div className="odds-table">
      <div className="odds-bookmaker">📊 {odds.bookmaker}</div>
      <table>
        <thead>
          <tr>
            <th>Outcome</th>
            <th>Odds</th>
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
