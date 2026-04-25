import { useEffect, useState } from 'react'
import axios from 'axios'
import './CLVView.css'

const OUTCOME_LABEL = { home: 'Home', draw: 'Draw', away: 'Away' }

function pct(v) {
  return v == null ? '–' : `${(v * 100).toFixed(1)}%`
}

function clvClass(v) {
  if (v == null) return 'clv-none'
  if (v > 0.01)  return 'clv-pos'
  if (v < -0.01) return 'clv-neg'
  return 'clv-flat'
}

function clvFmt(v) {
  if (v == null) return '–'
  return `${v > 0 ? '+' : ''}${(v * 100).toFixed(1)}pp`
}

function SummaryCard({ label, value, sub, highlight }) {
  return (
    <div className={`clv-card${highlight ? ' highlight' : ''}`}>
      <div className="clv-card-value">{value}</div>
      <div className="clv-card-label">{label}</div>
      {sub && <div className="clv-card-sub">{sub}</div>}
    </div>
  )
}

export default function CLVView({ modelVariant = 'base' }) {
  const [fetchState, setFetchState] = useState({ variant: null, data: null, error: null })
  const loading = fetchState.variant !== modelVariant
  const data  = fetchState.data
  const error = fetchState.error

  useEffect(() => {
    axios.get(`/api/clv?model_variant=${modelVariant}`)
      .then(r => setFetchState({ variant: modelVariant, data: r.data, error: null }))
      .catch(e => setFetchState({ variant: modelVariant, data: null, error: e.message }))
  }, [modelVariant])

  if (loading) return <div className="status">Loading CLV data…</div>
  if (error)   return <div className="status error">Error: {error}</div>
  if (!data)   return null

  const { entries, avg_best_clv, fixtures_with_closing, fixtures_total } = data
  const noOdds = fixtures_with_closing === 0

  return (
    <div className="clv-wrapper">
      <div className="clv-header">
        <div>
          <h2 className="clv-title">Closing Line Value</h2>
          <p className="clv-desc">
            CLV = model probability − closing implied probability.
            Positive means the model assigned more probability than the market's final efficient price.
          </p>
        </div>
      </div>

      <div className="clv-cards">
        <SummaryCard
          label="Avg CLV (best pick)"
          value={avg_best_clv != null ? clvFmt(avg_best_clv) : '–'}
          sub={`${fixtures_with_closing} fixture${fixtures_with_closing !== 1 ? 's' : ''} with closing odds`}
          highlight={avg_best_clv != null && avg_best_clv > 0}
        />
        <SummaryCard
          label="Fixtures in cache"
          value={fixtures_total}
          sub="settled fixtures with frozen predictions"
        />
        <SummaryCard
          label="Coverage"
          value={fixtures_total > 0 ? `${Math.round(fixtures_with_closing / fixtures_total * 100)}%` : '–'}
          sub="have closing odds"
        />
      </div>

      {noOdds && (
        <div className="clv-notice">
          No closing odds yet — CLV data builds up over time as the odds poller runs before each kickoff.
          Opening odds are stored on startup; closing odds accumulate with subsequent polls.
        </div>
      )}

      {entries.length === 0 ? (
        <div className="status">No settled fixtures in prediction cache yet.</div>
      ) : (
        <div className="clv-table-wrap">
          <table className="clv-table">
            <thead>
              <tr>
                <th>MD</th>
                <th className="clv-fix-hdr">Fixture</th>
                <th>Result</th>
                <th className="clv-group-hdr" colSpan={3}>Model %</th>
                <th className="clv-group-hdr" colSpan={3}>Closing %</th>
                <th className="clv-group-hdr" colSpan={3}>CLV</th>
                <th>Best pick</th>
              </tr>
              <tr className="clv-sub-hdr">
                <th /><th /><th />
                <th>H</th><th>D</th><th>A</th>
                <th>H</th><th>D</th><th>A</th>
                <th>H</th><th>D</th><th>A</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {entries.map(e => (
                <tr key={e.fixture_id} className={e.home_score != null ? 'settled' : ''}>
                  <td className="clv-md">{e.matchday}</td>
                  <td className="clv-fixture">
                    {e.home_team.split(' ').pop()} – {e.away_team.split(' ').pop()}
                  </td>
                  <td className="clv-result">
                    {e.home_score != null ? `${e.home_score}–${e.away_score}` : '–'}
                  </td>
                  <td className="clv-prob">{pct(e.model_home_prob)}</td>
                  <td className="clv-prob">{pct(e.model_draw_prob)}</td>
                  <td className="clv-prob">{pct(e.model_away_prob)}</td>
                  <td className="clv-prob muted">{pct(e.closing_home_prob)}</td>
                  <td className="clv-prob muted">{pct(e.closing_draw_prob)}</td>
                  <td className="clv-prob muted">{pct(e.closing_away_prob)}</td>
                  <td className={clvClass(e.clv_home)}>{clvFmt(e.clv_home)}</td>
                  <td className={clvClass(e.clv_draw)}>{clvFmt(e.clv_draw)}</td>
                  <td className={clvClass(e.clv_away)}>{clvFmt(e.clv_away)}</td>
                  <td className={`clv-best clv-best-${e.best_outcome}`}>
                    {OUTCOME_LABEL[e.best_outcome]}
                    {e.best_clv != null && (
                      <span className={`clv-best-val ${clvClass(e.best_clv)}`}> {clvFmt(e.best_clv)}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
