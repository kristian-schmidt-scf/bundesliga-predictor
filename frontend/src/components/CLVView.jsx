import { useEffect, useState, useMemo } from 'react'
import axios from 'axios'
import './CLVView.css'

const OUTCOME_LABEL = { home: 'Home', draw: 'Draw', away: 'Away' }

function pct(v) {
  return v == null ? '–' : `${(v * 100).toFixed(1)}%`
}

function clvClass(v) {
  if (v == null)   return 'clv-none'
  if (v > 0.005)   return 'clv-pos'
  if (v < -0.005)  return 'clv-neg'
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

function Sparkline({ matchdays, effectiveMd, onSelect }) {
  const maxAbs = Math.max(0.03, ...matchdays.map(m => Math.abs(m.avgClv ?? 0)))

  return (
    <div className="clv-spark-wrap">
      <div className="clv-spark-bars">
        <button
          className={`clv-spark-all-btn${effectiveMd == null ? ' active' : ''}`}
          onClick={() => onSelect(null)}
        >
          All
        </button>
        {matchdays.map(m => {
          const isActive = effectiveMd === m.matchday
          const pct = m.avgClv != null ? Math.min(100, Math.abs(m.avgClv) / maxAbs * 100) : 3
          const fillClass = m.avgClv == null ? 'none'
            : m.avgClv > 0.005  ? 'pos'
            : m.avgClv < -0.005 ? 'neg'
            : 'flat'
          return (
            <button
              key={m.matchday}
              className={`clv-spark-btn${isActive ? ' active' : ''}`}
              onClick={() => onSelect(m.matchday)}
              title={`MD${m.matchday}: ${m.avgClv != null ? clvFmt(m.avgClv) : 'no closing odds'} · ${m.withClv}/${m.total} fixtures`}
            >
              <div className="clv-spark-track">
                <div className={`clv-spark-fill ${fillClass}`} style={{ height: `${pct}%` }} />
              </div>
              <span className="clv-spark-md">{m.matchday}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default function CLVView({ modelVariant = 'base' }) {
  const [fetchState, setFetchState] = useState({ variant: null, data: null, error: null })
  const loading = fetchState.variant !== modelVariant
  const data  = fetchState.data
  const error = fetchState.error

  // '__latest__' = default to most recent MD; null = show all; number = specific MD
  const [selectedMd, setSelectedMd] = useState('__latest__')

  useEffect(() => {
    axios.get(`/api/clv?model_variant=${modelVariant}`)
      .then(r => setFetchState({ variant: modelVariant, data: r.data, error: null }))
      .catch(e => setFetchState({ variant: modelVariant, data: null, error: e.message }))
  }, [modelVariant])

  const entries = useMemo(() => data?.entries ?? [], [data])

  // Per-matchday aggregates (for sparkline)
  const matchdays = useMemo(() => {
    const map = {}
    for (const e of entries) {
      if (!map[e.matchday]) map[e.matchday] = { matchday: e.matchday, all: [], withClv: [] }
      map[e.matchday].all.push(e)
      if (e.best_clv != null) map[e.matchday].withClv.push(e)
    }
    return Object.values(map)
      .sort((a, b) => a.matchday - b.matchday)
      .map(({ matchday, all, withClv }) => ({
        matchday,
        total: all.length,
        withClv: withClv.length,
        avgClv: withClv.length > 0
          ? withClv.reduce((s, e) => s + e.best_clv, 0) / withClv.length
          : null,
      }))
  }, [entries])

  const latestMd = matchdays.length > 0 ? matchdays[matchdays.length - 1].matchday : null
  const effectiveMd = selectedMd === '__latest__' ? latestMd : selectedMd

  const filteredEntries = useMemo(
    () => effectiveMd == null ? entries : entries.filter(e => e.matchday === effectiveMd),
    [entries, effectiveMd]
  )

  const filteredStats = useMemo(() => {
    const withClv = filteredEntries.filter(e => e.best_clv != null)
    return {
      avgBestClv: withClv.length > 0
        ? withClv.reduce((s, e) => s + e.best_clv, 0) / withClv.length
        : null,
      fixturesWithClosing: withClv.length,
      fixturesTotal: filteredEntries.length,
    }
  }, [filteredEntries])

  if (loading) return <div className="status">Loading CLV data…</div>
  if (error)   return <div className="status error">Error: {error}</div>
  if (!data)   return null

  const { avgBestClv, fixturesWithClosing, fixturesTotal } = filteredStats
  const noOdds = fixturesWithClosing === 0
  const scopeLabel = effectiveMd != null ? `MD${effectiveMd}` : 'all matchdays'

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
          value={avgBestClv != null ? clvFmt(avgBestClv) : '–'}
          sub={`${fixturesWithClosing} fixture${fixturesWithClosing !== 1 ? 's' : ''} with closing odds · ${scopeLabel}`}
          highlight={avgBestClv != null && avgBestClv > 0}
        />
        <SummaryCard
          label="Fixtures"
          value={fixturesTotal}
          sub={`settled · ${scopeLabel}`}
        />
        <SummaryCard
          label="Coverage"
          value={fixturesTotal > 0 ? `${Math.round(fixturesWithClosing / fixturesTotal * 100)}%` : '–'}
          sub="have closing odds"
        />
      </div>

      {matchdays.length > 1 && (
        <Sparkline
          matchdays={matchdays}
          effectiveMd={effectiveMd}
          onSelect={md => setSelectedMd(md)}
        />
      )}

      {noOdds && (
        <div className="clv-notice">
          No closing odds yet — CLV data builds up over time as the odds poller runs before each kickoff.
          Opening odds are stored on startup; closing odds accumulate with subsequent polls.
        </div>
      )}

      {filteredEntries.length === 0 ? (
        <div className="status">No settled fixtures in prediction cache yet.</div>
      ) : (
        <div className="clv-table-wrap">
          <table className="clv-table">
            <thead>
              <tr>
                {effectiveMd == null && <th>MD</th>}
                <th className="clv-fix-hdr">Fixture</th>
                <th>Result</th>
                <th className="clv-group-hdr" colSpan={3}>Model %</th>
                <th className="clv-group-hdr" colSpan={3}>Closing %</th>
                <th className="clv-group-hdr" colSpan={3}>CLV</th>
                <th>Best pick</th>
              </tr>
              <tr className="clv-sub-hdr">
                {effectiveMd == null && <th />}
                <th /><th />
                <th>H</th><th>D</th><th>A</th>
                <th>H</th><th>D</th><th>A</th>
                <th>H</th><th>D</th><th>A</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filteredEntries.map(e => (
                <tr key={e.fixture_id} className={e.home_score != null ? 'settled' : ''}>
                  {effectiveMd == null && <td className="clv-md">{e.matchday}</td>}
                  <td className="clv-fixture">
                    {e.home_short_name || e.home_team} – {e.away_short_name || e.away_team}
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
