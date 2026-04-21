import { bestTipp11Tip, computePoints } from '../utils/tipp11'
import { blendScoreMatrix } from '../utils/blendOdds'
import './Tipp11Summary.css'

export default function Tipp11Summary({ predictions, useBlend }) {
  if (predictions.length === 0) return null

  const rows = predictions.map(p => {
    const { fixture, score_matrix, win_probabilities, odds } = p
    const { home_team, away_team, home_score, away_score, status } = fixture
    const isFinished = status === 'FINISHED' && home_score != null && away_score != null

    const grid = (useBlend && odds?.implied_home_prob)
      ? blendScoreMatrix(score_matrix.matrix, win_probabilities, odds)
      : score_matrix.matrix

    const { h, a, pts: expectedPts } = bestTipp11Tip(grid)

    const actualPts = isFinished
      ? computePoints(h, a, home_score, away_score)
      : null

    return { home_team, away_team, h, a, expectedPts, actualPts, isFinished, home_score, away_score }
  })

  const totalExpected = rows.reduce((s, r) => s + r.expectedPts, 0)
  const finishedRows = rows.filter(r => r.isFinished)
  const totalActual = finishedRows.length > 0
    ? finishedRows.reduce((s, r) => s + r.actualPts, 0)
    : null

  const showResultCol = finishedRows.length > 0
  const showActualCol = finishedRows.length > 0

  return (
    <div className="t11s-wrapper">
      <div className="t11s-header">
        <span className="t11s-title">Tipp 11 — Round summary</span>
        <span className="t11s-hint">{useBlend ? 'Blended odds' : 'Model only'}</span>
      </div>
      <table className="t11s-table">
        <thead>
          <tr>
            <th>Fixture</th>
            <th>Best tip</th>
            {showResultCol && <th>Result</th>}
            <th>xPts</th>
            {showActualCol && <th>Pts</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td className="t11s-fixture">
                {r.home_team.short_name} – {r.away_team.short_name}
              </td>
              <td className="t11s-tip">{r.h}:{r.a}</td>
              {showResultCol && (
                <td className="t11s-result">
                  {r.isFinished ? `${r.home_score}–${r.away_score}` : '–'}
                </td>
              )}
              <td className="t11s-xpts">{r.expectedPts.toFixed(1)}</td>
              {showActualCol && (
                <td className={r.isFinished ? `pts-${scoreClass(r.actualPts)}` : 't11s-dash'}>
                  {r.isFinished ? r.actualPts : '–'}
                </td>
              )}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="t11s-total">
            <td>Total</td>
            <td />
            {showResultCol && <td />}
            <td className="t11s-xpts">{totalExpected.toFixed(1)}</td>
            {showActualCol && (
              <td className={totalActual !== null ? `pts-${scoreClass(totalActual)}` : 't11s-dash'}>
                {totalActual !== null ? totalActual : '–'}
              </td>
            )}
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

function scoreClass(pts) {
  if (pts === null) return 'none'
  if (pts >= 7) return 'high'
  if (pts >= 3) return 'mid'
  return 'low'
}
