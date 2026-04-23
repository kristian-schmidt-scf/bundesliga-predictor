import { useEffect, useState } from 'react'
import axios from 'axios'
import './BacktestView.css'

function StatCard({ label, value, note, good }) {
  return (
    <div className="bt-stat-card">
      <div className={`bt-stat-value ${good ? 'good' : ''}`}>{value}</div>
      <div className="bt-stat-label">{label}</div>
      {note && <div className="bt-stat-note">{note}</div>}
    </div>
  )
}

function LineChart({ perMatchday, lines }) {
  if (perMatchday.length < 2) return null

  const W = 560, H = 180
  const PAD = { top: 16, right: 100, bottom: 28, left: 52 }
  const iW = W - PAD.left - PAD.right
  const iH = H - PAD.top - PAD.bottom

  const spieltage = perMatchday.map(r => r.matchday)
  const minSt = Math.min(...spieltage), maxSt = Math.max(...spieltage)

  const allY = lines.flatMap(l => [...perMatchday.map(r => r[l.key]), ...(l.refs || []).map(r => r.y)])
  const minY = Math.min(...allY), maxY = Math.max(...allY)
  const padY = (maxY - minY) * 0.12 || 0.05

  const xS = st => PAD.left + ((st - minSt) / (maxSt - minSt || 1)) * iW
  const yS = v  => PAD.top  + (1 - (v - (minY - padY)) / (maxY + padY - (minY - padY))) * iH

  const yTicks = [minY, (minY + maxY) / 2, maxY]

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="bt-chart">
      {yTicks.map((v, i) => (
        <g key={i}>
          <line x1={PAD.left} y1={yS(v)} x2={W - PAD.right} y2={yS(v)} stroke="var(--border-subtle)" strokeWidth="1" />
          <text x={PAD.left - 5} y={yS(v) + 4} textAnchor="end" fill="var(--text-muted)" fontSize="9">{v.toFixed(lines[0].decimals ?? 3)}</text>
        </g>
      ))}

      {lines.flatMap(l => (l.refs || []).map(r => {
        const y = yS(r.y)
        if (y < PAD.top - 4 || y > H - PAD.bottom + 4) return null
        return (
          <g key={r.label}>
            <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y} stroke={r.color} strokeWidth="1" strokeDasharray={r.dash || '4 3'} opacity="0.75" />
            <text x={W - PAD.right + 4} y={y + 4} fill={r.color} fontSize="8" opacity="0.9">{r.label}</text>
          </g>
        )
      }))}

      {lines.map(l => {
        const pts = perMatchday.map(r => `${xS(r.matchday)},${yS(r[l.key])}`).join(' ')
        return (
          <g key={l.key}>
            <polyline points={pts} fill="none" stroke={l.color} strokeWidth="2" />
            {perMatchday.map(r => (
              <circle key={r.matchday} cx={xS(r.matchday)} cy={yS(r[l.key])} r="3.5" fill={l.color} />
            ))}
          </g>
        )
      })}

      {perMatchday.map(r => (
        <text key={r.matchday} x={xS(r.matchday)} y={H - 6} textAnchor="middle" fill="var(--text-muted)" fontSize="9">{r.matchday}</text>
      ))}

      <text x={PAD.left - 36} y={PAD.top + iH / 2} textAnchor="middle" fill="var(--text-muted)" fontSize="9"
        transform={`rotate(-90, ${PAD.left - 36}, ${PAD.top + iH / 2})`}>{lines.map(l => l.yLabel).join(' / ')}</text>
      <text x={PAD.left + iW / 2} y={H} textAnchor="middle" fill="var(--text-muted)" fontSize="9">Spieltag</text>

      {lines.length > 1 && (
        <g>
          {lines.map((l, i) => (
            <g key={l.key} transform={`translate(${W - PAD.right + 4}, ${PAD.top + i * 14})`}>
              <line x1="0" y1="5" x2="10" y2="5" stroke={l.color} strokeWidth="2" />
              <text x="13" y="9" fill={l.color} fontSize="8">{l.label}</text>
            </g>
          ))}
        </g>
      )}
    </svg>
  )
}

export default function BacktestView() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const poll = () => {
      axios.get('/api/backtest').then(res => {
        setData(res.data)
        setLoading(false)
        if (res.data.status === 'computing') {
          setTimeout(poll, 8000)
        }
      }).catch(() => setLoading(false))
    }
    poll()
  }, [])

  if (loading) return <div className="status">Loading…</div>
  if (!data)   return <div className="status error">Failed to load backtest data.</div>

  if (data.status === 'computing') return (
    <div className="bt-wrapper">
      <p className="bt-intro">
        Walk-forward backtest is computing in the background — fitting a fresh model for each of
        Spieltage 18–{data.matchdays_tested > 0 ? data.matchdays_tested + 17 : 30} (~2 minutes total).
        This page will refresh automatically.
      </p>
      <div className="bt-computing">Computing… please wait</div>
    </div>
  )

  if (data.status === 'unavailable' || data.matchdays_tested === 0) return (
    <div className="bt-wrapper">
      <p className="bt-intro">Backtest data is not yet available. Restart the server to trigger computation.</p>
    </div>
  )

  const t11Diff = data.tipp11_actual - data.tipp11_expected
  const t11DiffStr = `${t11Diff >= 0 ? '+' : ''}${t11Diff.toFixed(1)}`

  return (
    <div className="bt-wrapper">
      <p className="bt-intro">
        Walk-forward backtest over <strong>Spieltage 18–{17 + data.matchdays_tested}</strong> of the current
        season. For each matchday, the model was refitted on all data available before that round
        (no lookahead), then scored against the actual results.
      </p>

      <div className="bt-section-title">Aggregate — {data.matchdays_tested} matchdays · {data.matchdays_tested * 9} fixtures</div>
      <div className="bt-stats-row">
        <StatCard label="Brier Score"      value={data.brier_score.toFixed(4)}             note="lower = better" good={data.brier_score < 0.62} />
        <StatCard label="Log-Loss"         value={data.log_loss.toFixed(4)}                note="lower = better" good={data.log_loss < 1.0} />
        <StatCard label="Tendency"         value={`${(data.tendency_accuracy*100).toFixed(1)}%`} note="H/D/A correct" good={data.tendency_accuracy >= 0.5} />
        <StatCard label="Tipp 11 Expected" value={data.tipp11_expected.toFixed(1)}         note="total pts expected" />
        <StatCard label="Tipp 11 Actual"   value={data.tipp11_actual.toFixed(1)}           note={`${t11DiffStr} vs expected`} good={t11Diff >= 0} />
      </div>

      {data.per_matchday.length > 1 && (
        <>
          <div className="bt-section-title bt-section-mt">Brier score by Spieltag</div>
          <LineChart
            perMatchday={data.per_matchday}
            lines={[{ key: 'brier_score', color: 'var(--purple)', yLabel: 'Brier ↓', decimals: 3, label: 'Brier' }]}
          />

          <div className="bt-section-title bt-section-mt">Tipp 11 points by Spieltag</div>
          <p className="bt-description">Expected points (what the model predicted) vs actual points earned with the recommended tip.</p>
          <LineChart
            perMatchday={data.per_matchday}
            lines={[
              { key: 'tipp11_expected', color: 'var(--purple)', yLabel: 'Pts', decimals: 1, label: 'Expected' },
              { key: 'tipp11_actual',   color: 'var(--green)',  yLabel: 'Pts', decimals: 1, label: 'Actual' },
            ]}
          />

          <div className="bt-section-title bt-section-mt">Per matchday</div>
          <table className="bt-table">
            <thead>
              <tr>
                <th>Spieltag</th>
                <th>Fixtures</th>
                <th>Brier ↓</th>
                <th>Log-Loss ↓</th>
                <th>Tendency ↑</th>
                <th>T11 Expected</th>
                <th>T11 Actual</th>
                <th>T11 Δ</th>
              </tr>
            </thead>
            <tbody>
              {data.per_matchday.map(row => {
                const delta = row.tipp11_actual - row.tipp11_expected
                return (
                  <tr key={row.matchday}>
                    <td>{row.matchday}</td>
                    <td>{row.fixtures}</td>
                    <td className={row.brier_score < 0.62 ? 'good' : 'bad'}>{row.brier_score.toFixed(4)}</td>
                    <td className={row.log_loss < 1.0 ? 'good' : 'bad'}>{row.log_loss.toFixed(4)}</td>
                    <td className={row.tendency_accuracy >= 0.5 ? 'good' : 'bad'}>{(row.tendency_accuracy*100).toFixed(1)}%</td>
                    <td className="col-purple">{row.tipp11_expected.toFixed(1)}</td>
                    <td className="col-green">{row.tipp11_actual.toFixed(1)}</td>
                    <td className={delta >= 0 ? 'good' : 'bad'}>{delta >= 0 ? '+' : ''}{delta.toFixed(1)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
