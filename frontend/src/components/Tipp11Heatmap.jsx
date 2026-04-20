import { computeTipp11Matrix } from '../utils/tipp11'
import './Tipp11Heatmap.css'

function lerp(a, b, t) {
  return a + (b - a) * t
}

function pointsToColor(value, max) {
  const t = max > 0 ? Math.min(value / max, 1) : 0
  const r = Math.round(lerp(240, 30, t))
  const g = Math.round(lerp(240, 160, t))
  const b = Math.round(lerp(240, 50, t))
  return `rgb(${r},${g},${b})`
}

export default function Tipp11Heatmap({ matrix }) {
  const { matrix: grid, max_goals, home_team, away_team } = matrix
  const size = max_goals + 1
  const tipp11 = computeTipp11Matrix(grid)

  const flat = tipp11.flat()
  const maxVal = Math.max(...flat)

  const cols = Array.from({ length: size }, (_, i) => i)
  const rows = Array.from({ length: size }, (_, i) => i)

  const bestScore = Math.max(...flat)
  const bestTips = []
  for (let i = 0; i < size; i++) {
    for (let j = 0; j < size; j++) {
      if (tipp11[i][j] === bestScore) bestTips.push(`${i}:${j}`)
    }
  }

  return (
    <div className="tipp11-wrapper">
      <div className="tipp11-title">
        Tipp 11 — Expected points per tip
        <span className="tipp11-best">Best: {bestTips.join(', ')} ({bestScore.toFixed(2)} pts)</span>
      </div>
      <div className="tipp11-away-label">{away_team} goals →</div>
      <div className="tipp11-body">
        <div className="tipp11-home-label">{home_team} goals ↓</div>
        <div className="tipp11-grid" style={{ gridTemplateColumns: `repeat(${size + 1}, 1fr)` }}>
          <div className="tipp11-cell header corner" />
          {cols.map(j => (
            <div key={j} className="tipp11-cell header">{j}</div>
          ))}
          {rows.map(i => (
            <>
              <div key={`lbl-${i}`} className="tipp11-cell header">{i}</div>
              {cols.map(j => {
                const val = tipp11[i][j]
                const isBest = val === maxVal
                return (
                  <div
                    key={`${i}-${j}`}
                    className={`tipp11-cell data${isBest ? ' best' : ''}`}
                    style={{ backgroundColor: pointsToColor(val, maxVal) }}
                    title={`Tip ${i}:${j} → ${val.toFixed(2)} expected pts`}
                  >
                    {val.toFixed(1)}
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
