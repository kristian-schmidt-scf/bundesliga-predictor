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

  return (
    <div className="cal-wrapper">
      <p className="cal-intro">
        Calibration measures how well the model's predicted probabilities match reality.
        A perfectly calibrated model would, for example, win 30% of the time in situations
        where it assigned a 30% chance. Metrics are computed from <strong>{data.total_fixtures} finished
        fixtures</strong> using pre-kickoff predictions stored at the time of the last server start.
      </p>

      <div className="cal-section-title">Season aggregate</div>
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

      {data.calibration_curve.length > 0 && (
        <>
          <div className="cal-section-title cal-section-mt">Calibration curve</div>
          <p className="cal-description">
            Each row groups all predicted outcome probabilities that fell within that percentage band.
            The <span className="cal-legend-inline cal-legend-predicted">purple bar</span> shows the
            average predicted probability; the <span className="cal-legend-inline cal-legend-actual">green marker</span> shows
            how often that outcome actually occurred. When the marker sits on or near the end of the bar,
            the model is well-calibrated in that range. The gap column shows over- (+) or
            under-confidence (−) in percentage points.
          </p>
          <div className="cal-curve">
            {data.calibration_curve.map((b, i) => (
              <CalibrationBar key={i} bucket={b} />
            ))}
          </div>
          <div className="cal-curve-legend">
            <span><span className="leg-predicted" /> Predicted probability</span>
            <span><span className="leg-actual" /> Actual frequency</span>
            <span className="cal-legend-gap-key">
              Gap: <span style={{color:'#4caf50'}}>≤5% well calibrated</span>
              {' · '}<span style={{color:'#f5c518'}}>&lt;12% acceptable</span>
              {' · '}<span style={{color:'#ef5350'}}>≥12% miscalibrated</span>
            </span>
          </div>
        </>
      )}

      {data.per_matchday.length > 0 && (
        <>
          <div className="cal-section-title cal-section-mt">Per matchday</div>
          <p className="cal-description">
            Breakdown by Spieltag. High variance across matchdays is normal given the small sample
            size (9 fixtures each). Focus on the season aggregate above for a reliable signal.
          </p>
          <table className="cal-table">
            <thead>
              <tr>
                <th>Spieltag</th>
                <th>Fixtures</th>
                <th>Brier ↓</th>
                <th>Log-Loss ↓</th>
                <th>Tendency</th>
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
    </div>
  )
}
