const ALPHA = 0.5  // weight on Dixon-Coles model (1 - ALPHA goes to bookmaker)

export function blendScoreMatrix(grid, winProbs, impliedProbs) {
  const { home_win, draw, away_win } = winProbs
  const { implied_home_prob, implied_draw_prob, implied_away_prob } = impliedProbs

  if (!implied_home_prob || !implied_draw_prob || !implied_away_prob) return grid

  const bHome = ALPHA * home_win + (1 - ALPHA) * implied_home_prob
  const bDraw  = ALPHA * draw    + (1 - ALPHA) * implied_draw_prob
  const bAway  = ALPHA * away_win + (1 - ALPHA) * implied_away_prob

  const sHome = home_win > 0 ? bHome / home_win : 1
  const sDraw  = draw    > 0 ? bDraw  / draw    : 1
  const sAway  = away_win > 0 ? bAway  / away_win : 1

  return grid.map((row, i) =>
    row.map((val, j) => {
      if (i > j) return val * sHome
      if (i === j) return val * sDraw
      return val * sAway
    })
  )
}

export function blendWinProbs(winProbs, impliedProbs) {
  const { home_win, draw, away_win } = winProbs
  const { implied_home_prob, implied_draw_prob, implied_away_prob } = impliedProbs

  if (!implied_home_prob || !implied_draw_prob || !implied_away_prob) return winProbs

  return {
    home_win: ALPHA * home_win + (1 - ALPHA) * implied_home_prob,
    draw:     ALPHA * draw     + (1 - ALPHA) * implied_draw_prob,
    away_win: ALPHA * away_win + (1 - ALPHA) * implied_away_prob,
  }
}
