import './AccuracySummary.css'

function predictedTendency({ home_win, draw, away_win }) {
  if (home_win >= draw && home_win >= away_win) return 'H'
  if (away_win >= draw && away_win >= home_win) return 'A'
  return 'D'
}

function actualTendency(home, away) {
  if (home > away) return 'H'
  if (away > home) return 'A'
  return 'D'
}

function bestEdgePick(edge_home_win, edge_draw, edge_away_win) {
  const edges = [
    { outcome: 'H', edge: edge_home_win ?? -Infinity },
    { outcome: 'D', edge: edge_draw    ?? -Infinity },
    { outcome: 'A', edge: edge_away_win ?? -Infinity },
  ]
  const best = edges.reduce((a, b) => a.edge > b.edge ? a : b)
  return best.edge > 0 ? best.outcome : null
}

function pct(n, d) {
  return d === 0 ? null : Math.round((n / d) * 100)
}

function StatBlock({ label, n, d, note }) {
  const p = pct(n, d)
  const cls = p === null ? '' : p >= 60 ? 'good' : p >= 40 ? 'ok' : 'bad'
  return (
    <div className="stat-block">
      <div className={`stat-fraction ${cls}`}>
        {d === 0 ? '–' : `${n}/${d}`}
      </div>
      {p !== null && <div className={`stat-pct ${cls}`}>{p}%</div>}
      <div className="stat-label">{label}</div>
      {note && <div className="stat-note">{note}</div>}
    </div>
  )
}

export default function AccuracySummary({ predictions }) {
  const finished = predictions.filter(
    p => p.fixture.status === 'FINISHED' &&
         p.fixture.home_score != null &&
         p.fixture.away_score != null
  )

  if (finished.length === 0) return null

  let tendencyCorrect = 0
  let exactCorrect = 0
  let naiveCorrect = 0
  let edgeCorrect = 0
  let edgeTotal = 0

  for (const p of finished) {
    const { home_score, away_score } = p.fixture
    const actual = actualTendency(home_score, away_score)
    const predicted = predictedTendency(p.win_probabilities)

    if (predicted === actual) tendencyCorrect++
    if (actual === 'H') naiveCorrect++

    const [mh, ma] = p.most_likely_score.split('-').map(Number)
    if (mh === home_score && ma === away_score) exactCorrect++

    const pick = bestEdgePick(p.edge_home_win, p.edge_draw, p.edge_away_win)
    if (pick !== null) {
      edgeTotal++
      if (pick === actual) edgeCorrect++
    }
  }

  const n = finished.length

  return (
    <div className="accuracy-summary">
      <span className="accuracy-label">
        Model accuracy{finished.length < predictions.length ? ` (${n}/${predictions.length} played)` : ''}
      </span>
      <div className="accuracy-stats">
        <StatBlock
          label="Tendency"
          n={tendencyCorrect}
          d={n}
          note={`Naive: ${naiveCorrect}/${n}`}
        />
        <div className="stat-divider" />
        <StatBlock label="Exact score" n={exactCorrect} d={n} />
        <div className="stat-divider" />
        <StatBlock
          label="Edge picks"
          n={edgeCorrect}
          d={edgeTotal}
          note={edgeTotal === 0 ? 'No edges' : undefined}
        />
        <div className="stat-divider" />
        <StatBlock label="Naive (home)" n={naiveCorrect} d={n} />
      </div>
    </div>
  )
}
