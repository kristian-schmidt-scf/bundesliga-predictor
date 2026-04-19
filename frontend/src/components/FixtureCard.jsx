import ScoreHeatmap from './ScoreHeatmap'
import OddsComparison from './OddsComparison'
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

export default function FixtureCard({ prediction }) {
  const { fixture, win_probabilities, expected_home_goals, expected_away_goals, most_likely_score, score_matrix, odds, edge_home_win, edge_draw, edge_away_win } = prediction
  const { home_team, away_team, utc_date, status, home_score, away_score } = fixture

  const isFinished = status === 'FINISHED'
  const isLive = ['IN_PLAY', 'PAUSED', 'LIVE'].includes(status)

  const kickoff = new Date(utc_date).toLocaleString('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })

  const actualScore = isFinished && home_score != null && away_score != null
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
          <span>{home_team.name}</span>
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
        </div>
        <div className="team away">
          {away_team.crest_url && <img src={away_team.crest_url} alt="" className="crest" />}
          <span>{away_team.name}</span>
        </div>
      </div>

      <div className="prob-bars">
        <ProbBar label={home_team.short_name} value={win_probabilities.home_win} />
        <ProbBar label="Draw" value={win_probabilities.draw} />
        <ProbBar label={away_team.short_name} value={win_probabilities.away_win} />
      </div>

      <div className="card-lower">
        <ScoreHeatmap matrix={score_matrix} actualScore={actualScore} />
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
