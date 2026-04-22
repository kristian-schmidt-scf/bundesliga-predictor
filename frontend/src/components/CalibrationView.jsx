import { useEffect, useState } from 'react'
import axios from 'axios'
import './CalibrationView.css'

function StatCard({ label, value, note, explanation, good }) {
  return (
    <div className="cal-stat-card">
      <div className={`cal-stat-value ${good ? 'good' : ''}`}>{value}</div>
      <div className="cal-stat-label">{label}</div>
      {note && <div className="cal-stat-note">{note}</div>}
      {explanation && <div className="cal-stat-explanation">{explanation}</div>}
    </div>
  )
}

function CalibrationBar({ bucket }) {
  const { bucket_min, bucket_max, predicted_mean, actual_frequency, count } = bucket
  const gap = actual_frequency - predicted_mean
  const gapColor = Math.abs(gap) < 0.05 ? '#4caf50' : Math.abs(gap) < 0.12 ? '#f5c518' : '#ef5350'
  return (
    <div className="cal-bar-row">
      <span className="cal-bar-label">{Math.round(bucket_min * 100)}–{Math.round(bucket_max * 100)}%</span>
      <div className="cal-bar-track">
        <div className="cal-bar-predicted" style={{ width: `${predicted_mean * 100}%` }} />
        <div className="cal-bar-actual" style={{ left: `${actual_frequency * 100}%` }} />
      </div>
      <span className="cal-bar-gap" style={{ color: gapColor }}>
        {gap >= 0 ? '+' : ''}{(gap * 100).toFixed(1)}%
      </span>
      <span className="cal-bar-count">n={count}</span>
    </div>
  )
}

function SpieltagChart({ perMatchday, metricKey, yLabel, refLines }) {
  if (perMatchday.length < 2) return null

  const W = 560, H = 180
  const PAD = { top: 16, right: 90, bottom: 28, left: 52 }
  const iW = W - PAD.left - PAD.right
  const iH = H - PAD.top - PAD.bottom

  const spieltage = perMatchday.map(r => r.matchday)
  const values    = perMatchday.map(r => r[metricKey])
  const minSt = Math.min(...spieltage), maxSt = Math.max(...spieltage)

  const allY = [...values, ...refLines.map(r => r.y)]
  const minY = Math.min(...allY), maxY = Math.max(...allY)
  const padY = (maxY - minY) * 0.1 || 0.05

  const xS = st => PAD.left + ((st - minSt) / (maxSt - minSt || 1)) * iW
  const yS = v  => PAD.top  + (1 - (v - (minY - padY)) / (maxY + padY - (minY - padY))) * iH

  const pts = perMatchday.map(r => `${xS(r.matchday)},${yS(r[metricKey])}`).join(' ')
  const yTicks = [minY, (minY + maxY) / 2, maxY]

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="cal-chart">
      {yTicks.map((v, i) => (
        <g key={i}>
          <line x1={PAD.left} y1={yS(v)} x2={W - PAD.right} y2={yS(v)} stroke="#1e1e3a" strokeWidth="1" />
          <text x={PAD.left - 5} y={yS(v) + 4} textAnchor="end" fill="#555" fontSize="9">{v.toFixed(3)}</text>
        </g>
      ))}
      {refLines.map(r => {
        const y = yS(r.y)
        if (y < PAD.top - 4 || y > H - PAD.bottom + 4) return null
        return (
          <g key={r.label}>
            <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y}
              stroke={r.color} strokeWidth="1" strokeDasharray={r.dash || '4 3'} opacity="0.8" />
            <text x={W - PAD.right + 4} y={y + 4} fill={r.color} fontSize="8" opacity="0.9">{r.label}</text>
          </g>
        )
      })}
      <polyline points={pts} fill="none" stroke="#6c63ff" strokeWidth="2" />
      {perMatchday.map(r => (
        <g key={r.matchday}>
          <circle cx={xS(r.matchday)} cy={yS(r[metricKey])} r="3.5" fill="#6c63ff" />
          <text x={xS(r.matchday)} y={H - 6} textAnchor="middle" fill="#555" fontSize="9">{r.matchday}</text>
        </g>
      ))}
      <text x={PAD.left - 36} y={PAD.top + iH / 2} textAnchor="middle" fill="#444" fontSize="9"
        transform={`rotate(-90, ${PAD.left - 36}, ${PAD.top + iH / 2})`}>{yLabel}</text>
      <text x={PAD.left + iW / 2} y={H} textAnchor="middle" fill="#444" fontSize="9">Spieltag</text>
    </svg>
  )
}

export default function CalibrationView() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    axios.get('/api/calibration')
      .then(res => setData(res.data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="status">Loading calibration data…</div>
  if (error)   return <div className="status error">Error: {error}</div>
  if (!data || data.total_fixtures === 0) return (
    <div className="cal-wrapper">
      <p className="cal-intro">
        Calibration data is not yet available. It builds up automatically as matchdays complete
        during the current server session — predictions are captured before kickoff and scored
        against actual results once the match finishes.
      </p>
    </div>
  )

  const BOOKMAKER_KEYS = new Set(['Bookmaker only', '+ Bookmaker blend'])
  const modelVariants = data.variants.filter(v => !BOOKMAKER_KEYS.has(v.name))
  const bestBrier    = Math.min(...modelVariants.map(v => v.brier_score))
  const bestLogLoss  = Math.min(...modelVariants.map(v => v.log_loss))
  const bestTendency = Math.max(...modelVariants.map(v => v.tendency_accuracy))
  const isBest = (v, val, best) => !BOOKMAKER_KEYS.has(v.name) && Math.abs(val - best) < 1e-9

  return (
    <div className="cal-wrapper">
      <p className="cal-intro">
        Calibration measures how well the model's predicted probabilities match reality.
        A perfectly calibrated model would, for example, win 30% of the time in situations
        where it assigned a 30% chance. Metrics are computed from{' '}
        <strong>{data.total_fixtures} finished fixtures</strong> using pre-kickoff predictions
        stored at the time of the last server start (ablation variants are recomputed on-the-fly).
      </p>

      {data.variants.length > 0 && (
        <>
          <div className="cal-section-title">Model variant comparison</div>
          <p className="cal-description">
            Each row shows how a different version of the model performs. Lower Brier score and
            log-loss are better; higher tendency accuracy is better. The best value in each column
            is highlighted green. "Baseline" is plain Dixon-Coles — anything better than it adds value.
            Bookmaker rows require odds to have been cached before kickoff.
          </p>
          <table className="cal-table cal-variants-table">
            <thead>
              <tr>
                <th>Variant</th>
                <th>Description</th>
                <th>n</th>
                <th>Brier ↓</th>
                <th>Log-Loss ↓</th>
                <th>Tendency ↑</th>
              </tr>
            </thead>
            <tbody>
              {data.variants.map(v => (
                <tr key={v.name}>
                  <td className="cal-variant-name">{v.name}</td>
                  <td className="cal-variant-desc">{v.description}</td>
                  <td>{v.fixtures}</td>
                  <td className={isBest(v, v.brier_score, bestBrier) ? 'good' : ''}>{v.brier_score.toFixed(4)}</td>
                  <td className={isBest(v, v.log_loss, bestLogLoss) ? 'good' : ''}>{v.log_loss.toFixed(4)}</td>
                  <td className={isBest(v, v.tendency_accuracy, bestTendency) ? 'good' : ''}>
                    {(v.tendency_accuracy * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <div className="cal-section-title cal-section-mt">Full model — season aggregate</div>
      <div className="cal-stats-row">
        <StatCard
          label="Brier Score"
          value={data.brier_score.toFixed(4)}
          note="lower = better"
          explanation="Mean squared error between predicted probabilities and actual outcomes across all three outcomes (H/D/A). A random model scores ~0.67; a good model for football typically scores 0.55–0.62."
          good={data.brier_score < 0.62}
        />
        <StatCard
          label="Log-Loss"
          value={data.log_loss.toFixed(4)}
          note="lower = better"
          explanation="Mean negative log-likelihood of the actual outcome. Penalises overconfident wrong predictions more heavily than Brier score. Values below 1.0 are generally considered good for football."
          good={data.log_loss < 1.0}
        />
        <StatCard
          label="Tendency Accuracy"
          value={`${(data.tendency_accuracy * 100).toFixed(1)}%`}
          note="H/D/A correct"
          explanation="How often the model's top-probability outcome (home win, draw, or away win) matched the actual result. A naive 'always home win' baseline typically scores around 45%."
          good={data.tendency_accuracy >= 0.5}
        />
      </div>

      {data.per_matchday.length > 0 && (
        <>
          <div className="cal-section-title cal-section-mt">Brier score by Spieltag</div>
          <p className="cal-description">
            Lower is better. High variance is normal with only 9 fixtures per matchday — focus on the trend.
          </p>
          <SpieltagChart
            perMatchday={data.per_matchday}
            metricKey="brier_score"
            yLabel="Brier ↓"
            refLines={[
              { y: 0.67, label: 'Random (0.67)', color: '#ef5350' },
              { y: 0.62, label: 'OK (0.62)',     color: '#f5c518' },
              { y: 0.55, label: 'Good (0.55)',   color: '#4caf50' },
              { y: data.brier_score, label: `Season (${data.brier_score.toFixed(3)})`, color: '#6c63ff', dash: '2 2' },
            ]}
          />

          <div className="cal-section-title cal-section-mt">Log-Loss by Spieltag</div>
          <SpieltagChart
            perMatchday={data.per_matchday}
            metricKey="log_loss"
            yLabel="Log-Loss ↓"
            refLines={[
              { y: 1.1,  label: 'Random (~1.1)', color: '#ef5350' },
              { y: 1.0,  label: 'OK (1.0)',      color: '#f5c518' },
              { y: 0.9,  label: 'Good (0.9)',    color: '#4caf50' },
              { y: data.log_loss, label: `Season (${data.log_loss.toFixed(3)})`, color: '#6c63ff', dash: '2 2' },
            ]}
          />

          <div className="cal-section-title cal-section-mt">Per matchday</div>
          <table className="cal-table">
            <thead>
              <tr>
                <th>Spieltag</th>
                <th>Fixtures</th>
                <th>Brier ↓</th>
                <th>Log-Loss ↓</th>
                <th>Tendency ↑</th>
              </tr>
            </thead>
            <tbody>
              {data.per_matchday.map(row => (
                <tr key={row.matchday}>
                  <td>{row.matchday}</td>
                  <td>{row.fixtures}</td>
                  <td className={row.brier_score < 0.62 ? 'good' : 'bad'}>{row.brier_score.toFixed(4)}</td>
                  <td className={row.log_loss < 1.0 ? 'good' : 'bad'}>{row.log_loss.toFixed(4)}</td>
                  <td className={row.tendency_accuracy >= 0.5 ? 'good' : 'bad'}>
                    {(row.tendency_accuracy * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {data.calibration_curve.length > 0 && (
        <>
          <div className="cal-section-title cal-section-mt">Calibration curve</div>
          <p className="cal-description">
            Each row groups all predicted outcome probabilities that fell within that percentage band.
            The <span className="cal-legend-inline cal-legend-predicted">purple bar</span> shows the
            average predicted probability; the <span className="cal-legend-inline cal-legend-actual">green marker</span> shows
            how often that outcome actually occurred. When the marker sits at the end of the bar,
            the model is well-calibrated. The gap column shows over- (+) or under-confidence (−).
          </p>
          <div className="cal-curve">
            {data.calibration_curve.map((b, i) => <CalibrationBar key={i} bucket={b} />)}
          </div>
          <div className="cal-curve-legend">
            <span><span className="leg-predicted" /> Predicted probability</span>
            <span><span className="leg-actual" /> Actual frequency</span>
            <span className="cal-legend-gap-key">
              Gap: <span style={{color:'#4caf50'}}>≤5%</span>
              {' · '}<span style={{color:'#f5c518'}}>&lt;12%</span>
              {' · '}<span style={{color:'#ef5350'}}>≥12%</span>
            </span>
          </div>
        </>
      )}
    </div>
  )
}
