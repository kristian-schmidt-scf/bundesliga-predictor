import { useEffect, useState } from 'react'
import axios from 'axios'
import './TeamProfile.css'

function RatingBar({ label, value, avg, higherIsBetter = true }) {
  const pct = Math.min(value / (avg * 2), 1) * 100
  const avgPct = 50
  const better = higherIsBetter ? value > avg : value < avg
  const diff = ((value - avg) / avg * 100).toFixed(1)
  const sign = diff > 0 ? '+' : ''

  return (
    <div className="rating-row">
      <span className="rating-label">{label}</span>
      <div className="rating-track">
        <div
          className={`rating-fill ${better ? 'above-avg' : 'below-avg'}`}
          style={{ width: `${pct}%` }}
        />
        <div className="rating-avg-mark" style={{ left: `${avgPct}%` }} title="League avg" />
      </div>
      <span className={`rating-value ${better ? 'pos' : 'neg'}`}>
        {value.toFixed(3)} <span className="rating-diff">({sign}{diff}%)</span>
      </span>
    </div>
  )
}

function ResultBadge({ homeTeam, homeGoals, awayGoals, team }) {
  const isHome = homeTeam === team
  const scored = isHome ? homeGoals : awayGoals
  const conceded = isHome ? awayGoals : homeGoals
  const result = scored > conceded ? 'W' : scored < conceded ? 'L' : 'D'
  return <span className={`result-badge result-${result}`}>{result}</span>
}

export default function TeamProfile({ teamName, onClose }) {
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!teamName) return
    let cancelled = false
    axios.get(`/api/teams/${encodeURIComponent(teamName)}`)
      .then(res => { if (!cancelled) { setProfile(res.data); setError(null); setLoading(false) } })
      .catch(err => { if (!cancelled) { setError(err.response?.data?.detail ?? err.message); setLoading(false) } })
    return () => { cancelled = true }
  }, [teamName])

  useEffect(() => {
    function handleKey(e) { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <div className="tp-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="tp-modal" role="dialog" aria-modal="true" aria-label={`Team profile: ${teamName}`}>
        <div className="tp-header">
          <h2 className="tp-title">{teamName}</h2>
          <button className="tp-close" onClick={onClose} aria-label="Close">✕</button>
        </div>

        {loading && <div className="tp-status">Loading…</div>}
        {error   && <div className="tp-status tp-error">{error}</div>}

        {profile && (
          <>
            <section className="tp-section">
              <h3 className="tp-section-title">Model ratings</h3>
              <RatingBar label="Attack (α)" value={profile.alpha} avg={profile.avg_alpha} higherIsBetter={true} />
              <RatingBar label="Defence (δ)" value={profile.delta} avg={profile.avg_delta} higherIsBetter={false} />
              <RatingBar label="Home adv (γ)" value={profile.gamma} avg={profile.avg_gamma} higherIsBetter={true} />
              <RatingBar label="Form" value={profile.form} avg={profile.avg_form} higherIsBetter={true} />
              {profile.bayes_fitted && profile.alpha_bayes != null && (
                <div className="tp-bayes-note">
                  Bayes α: {profile.alpha_bayes.toFixed(3)} · δ: {profile.delta_bayes.toFixed(3)}
                </div>
              )}
            </section>

            {profile.upcoming.length > 0 && (
              <section className="tp-section">
                <h3 className="tp-section-title">Upcoming fixtures</h3>
                <table className="tp-table">
                  <thead>
                    <tr>
                      <th>MD</th>
                      <th>Date</th>
                      <th>Opponent</th>
                      <th>H/A</th>
                      <th>Win%</th>
                      <th>Draw%</th>
                      <th>xG</th>
                    </tr>
                  </thead>
                  <tbody>
                    {profile.upcoming.map(f => {
                      const isHome = f.home_team === profile.team
                      const opponent = isHome ? f.away_team : f.home_team
                      const winProb = isHome ? f.home_win_prob : f.away_win_prob
                      const xgFor = isHome ? f.expected_home_goals : f.expected_away_goals
                      const xgAgainst = isHome ? f.expected_away_goals : f.expected_home_goals
                      const date = new Date(f.date).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })
                      return (
                        <tr key={f.fixture_id}>
                          <td>{f.matchday}</td>
                          <td className="tp-date">{date}</td>
                          <td className="tp-opponent">{opponent}</td>
                          <td className={`tp-ha ${isHome ? 'home' : 'away'}`}>{isHome ? 'H' : 'A'}</td>
                          <td className="tp-prob">{(winProb * 100).toFixed(0)}%</td>
                          <td className="tp-prob">{(f.draw_prob * 100).toFixed(0)}%</td>
                          <td className="tp-xg">{xgFor.toFixed(2)}–{xgAgainst.toFixed(2)}</td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </section>
            )}

            {profile.season_results.length > 0 && (
              <section className="tp-section">
                <h3 className="tp-section-title">This season</h3>
                <table className="tp-table">
                  <thead>
                    <tr>
                      <th>MD</th>
                      <th>Date</th>
                      <th>Home</th>
                      <th></th>
                      <th>Away</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {profile.season_results.map((r, i) => (
                      <tr key={i}>
                        <td>{r.matchday ?? '—'}</td>
                        <td className="tp-date">{r.date}</td>
                        <td className={`tp-team-cell ${r.home_team === profile.team ? 'is-this-team' : ''}`}>{r.home_team}</td>
                        <td className="tp-score">{r.home_goals}–{r.away_goals}</td>
                        <td className={`tp-team-cell ${r.away_team === profile.team ? 'is-this-team' : ''}`}>{r.away_team}</td>
                        <td>
                          <ResultBadge
                            homeTeam={r.home_team}
                            homeGoals={r.home_goals} awayGoals={r.away_goals}
                            team={profile.team}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  )
}
