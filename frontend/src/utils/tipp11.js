function tendency(home, away) {
  if (home > away) return 'H'
  if (home < away) return 'A'
  return 'D'
}

export function computePoints(hTip, aTip, hActual, aActual) {
  const tendencyCorrect = tendency(hTip, aTip) === tendency(hActual, aActual)
  let pts = 0

  if (hTip === hActual) pts += 1
  if (aTip === aActual) pts += 1

  if (tendencyCorrect) {
    pts += 2
    if (hTip - aTip === hActual - aActual) pts += 2
    const goalError = Math.abs(hTip - hActual) + Math.abs(aTip - aActual)
    pts += Math.max(0, 5 - goalError)
  }

  return pts
}

export function computeTipp11Matrix(grid) {
  const size = grid.length
  return Array.from({ length: size }, (_, hTip) =>
    Array.from({ length: size }, (_, aTip) => {
      let expected = 0
      for (let hActual = 0; hActual < size; hActual++) {
        for (let aActual = 0; aActual < size; aActual++) {
          expected += grid[hActual][aActual] * computePoints(hTip, aTip, hActual, aActual)
        }
      }
      return expected
    })
  )
}

export function bestTipp11Tip(grid) {
  const matrix = computeTipp11Matrix(grid)
  let best = { h: 0, a: 0, pts: -1 }
  matrix.forEach((row, h) =>
    row.forEach((pts, a) => { if (pts > best.pts) best = { h, a, pts } })
  )
  return best
}
