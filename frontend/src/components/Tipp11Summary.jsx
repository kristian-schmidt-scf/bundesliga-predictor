import { useState, useEffect, useRef } from 'react'
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

function PickInput({ fixtureId, matchday, homeTeam, awayTeam, initialPick, onSave, variant }) {
  const [h, setH] = useState(initialPick?.picked_home ?? '')
  const [a, setA] = useState(initialPick?.picked_away ?? '')
  const saveTimer = useRef(null)

  function tryCommit(nextH, nextA) {
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      const hv = parseInt(nextH, 10)
      const av = parseInt(nextA, 10)
      if (!isNaN(hv) && !isNaN(av) && hv >= 0 && av >= 0) {
        onSave(fixtureId, matchday, homeTeam, awayTeam, hv, av)
      } else if (nextH === '' && nextA === '') {
        onSave(fixtureId, null, homeTeam, awayTeam, null, null) // signal delete
      }
    }, 400)
  }

  const cls = `pick-input${variant ? ` pick-input--${variant}` : ''}`

  return (
    <span className="pick-input-group">
      <input
        className={cls}
        type="number" min="0" max="20"
        value={h}
        onChange={e => { setH(e.target.value); tryCommit(e.target.value, a) }}
        placeholder="–"
      />
      <span className="pick-sep">:</span>
      <input
        className={cls}
        type="number" min="0" max="20"
        value={a}
        onChange={e => { setA(e.target.value); tryCommit(h, e.target.value) }}
        placeholder="–"
      />
    </span>
  )
}

export default function Tipp11Summary({ predictions, bayesPredictions, useBlend }) {
  const [picks, setPicks] = useState({})           // keyed by fixture_id
  const [oppPicks, setOppPicks] = useState({})     // keyed by fixture_id

  useEffect(() => {
    fetch('/api/picks')
      .then(r => r.json())
      .then(data => {
        const map = {}
        for (const p of data) map[p.fixture_id] = p
        setPicks(map)
      })
      .catch(() => {})
    fetch('/api/picks/opponent')
      .then(r => r.json())
      .then(data => {
        const map = {}
        for (const p of data) map[p.fixture_id] = p
        setOppPicks(map)
      })
      .catch(() => {})
  }, [])

  async function handleSave(fixtureId, matchday, homeTeam, awayTeam, pickedHome, pickedAway) {
    if (pickedHome === null) {
      await fetch(`/api/picks/${fixtureId}`, { method: 'DELETE' }).catch(() => {})
      setPicks(prev => { const next = { ...prev }; delete next[fixtureId]; return next })
    } else {
      const res = await fetch(`/api/picks/${fixtureId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ matchday, home_team: homeTeam, away_team: awayTeam, picked_home: pickedHome, picked_away: pickedAway }),
      }).catch(() => null)
      if (res?.ok) {
        const saved = await res.json()
        setPicks(prev => ({ ...prev, [fixtureId]: saved }))
      }
    }
  }

  async function handleOppSave(fixtureId, matchday, homeTeam, awayTeam, pickedHome, pickedAway) {
    if (pickedHome === null) {
      await fetch(`/api/picks/opponent/${fixtureId}`, { method: 'DELETE' }).catch(() => {})
      setOppPicks(prev => { const next = { ...prev }; delete next[fixtureId]; return next })
    } else {
      const res = await fetch(`/api/picks/opponent/${fixtureId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ matchday, home_team: homeTeam, away_team: awayTeam, picked_home: pickedHome, picked_away: pickedAway }),
      }).catch(() => null)
      if (res?.ok) {
        const saved = await res.json()
        setOppPicks(prev => ({ ...prev, [fixtureId]: saved }))
      }
    }
  }

  if (predictions.length === 0) return null

  const bayesMap = Object.fromEntries(
    (bayesPredictions || []).map(p => [p.fixture.id, p])
  )
  const hasBayes = bayesPredictions && bayesPredictions.length > 0

  const rows = predictions.map(p => {
    const { fixture } = p
    const { home_team, away_team, home_score, away_score, status, matchday } = fixture
    const isFinished = status === 'FINISHED' && home_score != null && away_score != null

    const base  = getBestTip(p, useBlend)
    const bayes = hasBayes && bayesMap[fixture.id] ? getBestTip(bayesMap[fixture.id], useBlend) : null

    const basePts  = isFinished ? computePoints(base.h,  base.a,  home_score, away_score) : null
    const bayesPts = (isFinished && bayes) ? computePoints(bayes.h, bayes.a, home_score, away_score) : null

    const pick    = picks[fixture.id] ?? null
    const myPts   = (isFinished && pick) ? computePoints(pick.picked_home, pick.picked_away, home_score, away_score) : null

    const oppPick = oppPicks[fixture.id] ?? null
    const oppPts  = (isFinished && oppPick) ? computePoints(oppPick.picked_home, oppPick.picked_away, home_score, away_score) : null

    return { fixture, home_team, away_team, matchday, base, bayes, basePts, bayesPts, isFinished, home_score, away_score, pick, myPts, oppPick, oppPts }
  })

  const totalBaseExp  = rows.reduce((s, r) => s + r.base.pts, 0)
  const totalBayesExp = hasBayes ? rows.reduce((s, r) => s + (r.bayes?.pts ?? 0), 0) : null
  const finishedRows  = rows.filter(r => r.isFinished)
  const totalBaseAct  = finishedRows.length > 0 ? finishedRows.reduce((s, r) => s + (r.basePts ?? 0), 0) : null
  const totalBayesAct = (finishedRows.length > 0 && hasBayes) ? finishedRows.reduce((s, r) => s + (r.bayesPts ?? 0), 0) : null
  const pickedFinished = finishedRows.filter(r => r.myPts !== null)
  const totalMyAct    = pickedFinished.length > 0 ? pickedFinished.reduce((s, r) => s + r.myPts, 0) : null

  const oppPickedFinished = finishedRows.filter(r => r.oppPts !== null)
  const totalOppAct       = oppPickedFinished.length > 0 ? oppPickedFinished.reduce((s, r) => s + r.oppPts, 0) : null

  const showActual = finishedRows.length > 0
  const showResult = showActual

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
            <th className="t11s-my-pick-hdr">Your pick</th>
            {showActual && <th>Your pts</th>}
            <th className="t11s-opp-pick-hdr">Opp pick</th>
            {showActual && <th>Opp pts</th>}
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
              <td className="t11s-my-pick-cell">
                <PickInput
                  key={r.pick?.saved_at ?? 'empty'}
                  fixtureId={r.fixture.id}
                  matchday={r.matchday}
                  homeTeam={r.home_team.name}
                  awayTeam={r.away_team.name}
                  initialPick={r.pick}
                  onSave={handleSave}
                />
              </td>
              {showActual && (
                <td className={r.myPts !== null ? `pts-${scoreClass(r.myPts)}` : 't11s-dash'}>
                  {r.myPts !== null ? r.myPts : '–'}
                </td>
              )}
              <td className="t11s-my-pick-cell">
                <PickInput
                  key={r.oppPick?.saved_at ?? 'opp-empty'}
                  fixtureId={r.fixture.id}
                  matchday={r.matchday}
                  homeTeam={r.home_team.name}
                  awayTeam={r.away_team.name}
                  initialPick={r.oppPick}
                  onSave={handleOppSave}
                  variant="opp"
                />
              </td>
              {showActual && (
                <td className={r.oppPts !== null ? `pts-${scoreClass(r.oppPts)}` : 't11s-dash'}>
                  {r.oppPts !== null ? r.oppPts : '–'}
                </td>
              )}
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
            <td />
            {showActual && <td className={totalMyAct !== null ? `pts-${scoreClass(totalMyAct)}` : ''}>{totalMyAct ?? '–'}</td>}
            <td />
            {showActual && <td className={totalOppAct !== null ? `pts-${scoreClass(totalOppAct)}` : ''}>{totalOppAct ?? '–'}</td>}
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
