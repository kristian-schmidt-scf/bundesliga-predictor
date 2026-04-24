import ScoreHeatmap from './ScoreHeatmap'
import OddsComparison from './OddsComparison'
import Tipp11Heatmap from './Tipp11Heatmap'
import H2HPanel from './H2HPanel'
import { blendScoreMatrix, blendWinProbs } from '../utils/blendOdds'
import './FixtureCard.css'

function ProbBar({ label, value }) {
  return (
    <div className="prob-bar-row">
      <span className="prob-label">{label}</span>
      <div className="prob-track">
        <div className="prob-fill" style={{ width: `${(value * 100).toFixed(1)}%` }} />
      </div>
      <span className="prob-value">{(value * 100).toFixed(1)}%</span>
    </div>
  )
}

function restLabel(days) {
  if (days == null) return null
  if (days < 4)  return { text: `${days}d ⚡`, cls: 'rest-fatigued' }
  if (days > 14) return { text: `${days}d 🧊`, cls: 'rest-rusty' }
  return { text: `${days}d`, cls: 'rest-normal' }
}

export default function FixtureCard({ prediction, showTipp11, blendOdds, onTeamClick }) {
  const { fixture, win_probabilities, expected_home_goals, expected_away_goals, most_likely_score, score_matrix, odds, edge_home_win, edge_draw, edge_away_win,
    rest_days_home, rest_days_away, travel_km } = prediction

  const canBlend = blendOdds && odds?.implied_home_prob
  const effectiveMatrix = canBlend
    ? { ...score_matrix, matrix: blendScoreMatrix(score_matrix.matrix, win_probabilities, odds) }
    : score_matrix
  const effectiveWinProbs = canBlend
    ? blendWinProbs(win_probabilities, odds)
    : win_probabilities
  const { home_team, away_team, utc_date, status, home_score, away_score } = fixture

  const isFinished = status === 'FINISHED'
  const isLive = ['IN_PLAY', 'PAUSED', 'LIVE'].includes(status)

  const kickoff = new Date(utc_date).toLocaleString('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })

  const actualScore = (isFinished || isLive) && home_score != null && away_score != null
    ? { home: home_score, away: away_score }
    : null

  return (
    <div className={`fixture-card${isFinished ? ' finished' : ''}${isLive ? ' live' : ''}`}>
      <div className="fixture-header">
        <span className="kickoff">{kickoff}</span>
        {isFinished && <span className="status-badge finished">FT</span>}
        {isLive && <span className="status-badge live">LIVE</span>}
      </div>

      <div className="teams-row">
        <div className="team home">
          {home_team.crest_url && <img src={home_team.crest_url} alt="" className="crest" />}
          <button className="team-name-btn" onClick={() => onTeamClick?.(home_team.name)}>{home_team.name}</button>
        </div>
        <div className="vs-block">
          {actualScore ? (
            <span className="actual-score">{actualScore.home} – {actualScore.away}</span>
          ) : (
            <span className="vs">vs</span>
          )}
          <span className="likely-score">
            {actualScore ? `Model: ${most_likely_score}` : most_likely_score}
          </span>
          <span className="xg">xG {expected_home_goals.toFixed(2)} – {expected_away_goals.toFixed(2)}</span>
          {(rest_days_home != null || rest_days_away != null || travel_km > 0) && (
            <span className="fatigue-row">
              {(() => {
                const rh = restLabel(rest_days_home)
                const ra = restLabel(rest_days_away)
                return <>
                  {rh && <span className={`rest-tag ${rh.cls}`}>{rh.text}</span>}
                  {travel_km > 0 && <span className="travel-tag">{Math.round(travel_km)}km</span>}
                  {ra && <span className={`rest-tag ${ra.cls}`}>{ra.text}</span>}
                </>
              })()}
            </span>
          )}
        </div>
        <div className="team away">
          {away_team.crest_url && <img src={away_team.crest_url} alt="" className="crest" />}
          <button className="team-name-btn" onClick={() => onTeamClick?.(away_team.name)}>{away_team.name}</button>
        </div>
      </div>

      <div className="prob-bars">
        <ProbBar label={home_team.short_name} value={effectiveWinProbs.home_win} />
        <ProbBar label="Draw" value={effectiveWinProbs.draw} />
        <ProbBar label={away_team.short_name} value={effectiveWinProbs.away_win} />
      </div>

      <H2HPanel
        homeTeam={home_team.name}
        awayTeam={away_team.name}
        homeShort={home_team.short_name}
        awayShort={away_team.short_name}
      />

      <div className="card-lower">
        <ScoreHeatmap matrix={effectiveMatrix} actualScore={actualScore} />
        {showTipp11 && <Tipp11Heatmap matrix={effectiveMatrix} />}
        {odds && (
          <OddsComparison
            odds={odds}
            winProbabilities={win_probabilities}
            edges={{ home: edge_home_win, draw: edge_draw, away: edge_away_win }}
            homeShort={home_team.short_name}
            awayShort={away_team.short_name}
          />
        )}
      </div>
    </div>
  )
}
