import { bestTipp11Tip, computePoints } from '../utils/tipp11'
import { blendScoreMatrix } from '../utils/blendOdds'
import './Tipp11Summary.css'

function getBestTip(prediction, useBlend) {
  const { score_matrix, win_probabilities, odds } = prediction
  const grid = (useBlend && odds?.implied_home_prob)
    ? blendScoreMatrix(score_matrix.matrix, win_probabilities, odds)
    : score_matrix.matrix
  return bestTipp11Tip(grid)
}

export default function Tipp11Summary({ predictions, bayesPredictions, useBlend }) {
  if (predictions.length === 0) return null

  // Build a lookup map for Bayes predictions by fixture id
  const bayesMap = Object.fromEntries(
    (bayesPredictions || []).map(p => [p.fixture.id, p])
  )
  const hasBayes = bayesPredictions && bayesPredictions.length > 0

  const rows = predictions.map(p => {
    const { fixture } = p
    const { home_team, away_team, home_score, away_score, status } = fixture
    const isFinished = status === 'FINISHED' && home_score != null && away_score != null

    const base = getBestTip(p, useBlend)
    const bayes = hasBayes && bayesMap[fixture.id] ? getBestTip(bayesMap[fixture.id], useBlend) : null

    const basePts  = isFinished ? computePoints(base.h,  base.a,  home_score, away_score) : null
    const bayesPts = (isFinished && bayes) ? computePoints(bayes.h, bayes.a, home_score, away_score) : null

    return { home_team, away_team, base, bayes, basePts, bayesPts, isFinished, home_score, away_score }
  })

  const totalBaseExp  = rows.reduce((s, r) => s + r.base.pts, 0)
  const totalBayesExp = hasBayes ? rows.reduce((s, r) => s + (r.bayes?.pts ?? 0), 0) : null
  const finishedRows  = rows.filter(r => r.isFinished)
  const totalBaseAct  = finishedRows.length > 0 ? finishedRows.reduce((s, r) => s + (r.basePts ?? 0), 0) : null
  const totalBayesAct = (finishedRows.length > 0 && hasBayes) ? finishedRows.reduce((s, r) => s + (r.bayesPts ?? 0), 0) : null
  const showActual    = finishedRows.length > 0
  const showResult    = showActual

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
            <th className="t11s-tip-hdr">Base tip</th>
            {hasBayes && <th className="t11s-tip-hdr t11s-bayes-hdr">Bayes tip</th>}
            {showResult && <th>Result</th>}
            <th>Base xPts</th>
            {hasBayes && <th>Bayes xPts</th>}
            {showActual && <th>Base pts</th>}
            {showActual && hasBayes && <th>Bayes pts</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              <td className="t11s-fixture">{r.home_team.short_name} – {r.away_team.short_name}</td>
              <td className="t11s-tip">{r.base.h}:{r.base.a}</td>
              {hasBayes && (
                <td className={`t11s-tip t11s-bayes-tip${r.bayes && (r.bayes.h !== r.base.h || r.bayes.a !== r.base.a) ? ' differs' : ''}`}>
                  {r.bayes ? `${r.bayes.h}:${r.bayes.a}` : '–'}
                </td>
              )}
              {showResult && (
                <td className="t11s-result">{r.isFinished ? `${r.home_score}–${r.away_score}` : '–'}</td>
              )}
              <td className="t11s-xpts">{r.base.pts.toFixed(1)}</td>
              {hasBayes && <td className="t11s-xpts t11s-bayes-xpts">{r.bayes ? r.bayes.pts.toFixed(1) : '–'}</td>}
              {showActual && <td className={r.isFinished ? `pts-${scoreClass(r.basePts)}` : 't11s-dash'}>{r.isFinished ? r.basePts : '–'}</td>}
              {showActual && hasBayes && <td className={r.isFinished ? `pts-${scoreClass(r.bayesPts)}` : 't11s-dash'}>{r.isFinished ? r.bayesPts : '–'}</td>}
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="t11s-total">
            <td>Total</td>
            <td />{hasBayes && <td />}
            {showResult && <td />}
            <td className="t11s-xpts">{totalBaseExp.toFixed(1)}</td>
            {hasBayes && <td className="t11s-xpts t11s-bayes-xpts">{totalBayesExp?.toFixed(1) ?? '–'}</td>}
            {showActual && <td className={totalBaseAct !== null ? `pts-${scoreClass(totalBaseAct)}` : ''}>{totalBaseAct ?? '–'}</td>}
            {showActual && hasBayes && <td className={totalBayesAct !== null ? `pts-${scoreClass(totalBayesAct)}` : ''}>{totalBayesAct ?? '–'}</td>}
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

function scoreClass(pts) {
  if (pts === null || pts === undefined) return 'none'
  if (pts >= 7) return 'high'
  if (pts >= 3) return 'mid'
  return 'low'
}
