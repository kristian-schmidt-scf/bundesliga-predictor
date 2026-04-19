import './ScoreHeatmap.css'

function lerp(a, b, t) {
  return a + (b - a) * t
}

function probToColor(value, max) {
  const t = max > 0 ? Math.min(value / max, 1) : 0
  const r = Math.round(lerp(240, 30, t))
  const g = Math.round(lerp(240, 120, t))
  const b = Math.round(lerp(255, 30, t))
  return `rgb(${r},${g},${b})`
}

function probToRedColor(value, max) {
  const t = max > 0 ? Math.min(value / max, 1) : 0
  const r = Math.round(lerp(255, 180, t))
  const g = Math.round(lerp(220, 20, t))
  const b = Math.round(lerp(220, 20, t))
  return `rgb(${r},${g},${b})`
}

export default function ScoreHeatmap({ matrix, actualScore }) {
  const { matrix: grid, max_goals, home_team, away_team } = matrix
  const size = max_goals + 1
  const maxVal = Math.max(...grid.flat())
  const cols = Array.from({ length: size }, (_, i) => i)
  const rows = Array.from({ length: size }, (_, i) => i)

  return (
    <div className="heatmap-wrapper">
      <div className="heatmap-away-label">{away_team} goals →</div>
      <div className="heatmap-body">
        <div className="heatmap-home-label">{home_team} goals ↓</div>
        <div className="heatmap-grid" style={{ gridTemplateColumns: `repeat(${size + 1}, 1fr)` }}>
          <div className="heatmap-cell header corner" />
          {cols.map(j => (
            <div key={j} className="heatmap-cell header">{j}</div>
          ))}
          {rows.map(i => (
            <>
              <div key={`lbl-${i}`} className="heatmap-cell header">{i}</div>
              {cols.map(j => {
                const val = grid[i][j]
                const isActual = actualScore && i === actualScore.home && j === actualScore.away
                return (
                  <div
                    key={`${i}-${j}`}
                    className={`heatmap-cell data${isActual ? ' actual' : ''}`}
                    style={{ backgroundColor: isActual ? probToRedColor(val, maxVal) : probToColor(val, maxVal) }}
                    title={`${i}–${j}: ${(val * 100).toFixed(2)}%${isActual ? ' ← actual' : ''}`}
                  >
                    {(val * 100).toFixed(1)}
                  </div>
                )
              })}
            </>
          ))}
        </div>
      </div>
    </div>
  )
}
