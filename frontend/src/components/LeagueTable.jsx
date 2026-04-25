import { useEffect, useState } from 'react'
import axios from 'axios'
import './LeagueTable.css'

const ZONES = [
  { from: 1,  to: 4,  label: 'Champions League',   cls: 'zone-cl' },
  { from: 5,  to: 6,  label: 'Europa League',       cls: 'zone-el' },
  { from: 7,  to: 7,  label: 'Conference League',   cls: 'zone-ecl' },
  { from: 16, to: 16, label: 'Relegation playoff',  cls: 'zone-playoff' },
  { from: 17, to: 18, label: 'Relegated',            cls: 'zone-rel' },
]

function zoneClass(position) {
  const z = ZONES.find(z => position >= z.from && position <= z.to)
  return z ? z.cls : ''
}

function FormPips({ form }) {
  if (!form) return null
  return (
    <span className="form-pips">
      {form.split(',').slice(-5).map((r, i) => (
        <span key={i} className={`pip pip-${r.trim()}`} title={r.trim()} />
      ))}
    </span>
  )
}

function SortHeader({ label, k, sortKey, sortDir, onSort }) {
  const active = sortKey === k
  return (
    <th className={`sortable${active ? ' active' : ''}`} onClick={() => onSort(k)}>
      {label}{active ? (sortDir === 1 ? ' ↑' : ' ↓') : ''}
    </th>
  )
}

function ZoneBar({ sim }) {
  if (!sim) return <span className="zone-bar-placeholder">—</span>

  const { p_cl, p_el, p_ecl, p_playoff, p_relegated } = sim
  const p_safe = Math.max(0, 1 - p_cl - p_el - p_ecl - p_playoff - p_relegated)

  const segments = [
    { key: 'cl',      pct: p_cl,       cls: 'zb-cl' },
    { key: 'el',      pct: p_el,       cls: 'zb-el' },
    { key: 'ecl',     pct: p_ecl,      cls: 'zb-ecl' },
    { key: 'safe',    pct: p_safe,     cls: 'zb-safe' },
    { key: 'playoff', pct: p_playoff,  cls: 'zb-playoff' },
    { key: 'rel',     pct: p_relegated,cls: 'zb-rel' },
  ]

  const fmt = p => p >= 0.005 ? `${(p * 100).toFixed(0)}%` : null

  const tooltip = [
    p_cl       > 0.005 && `CL: ${(p_cl * 100).toFixed(1)}%`,
    p_el       > 0.005 && `EL: ${(p_el * 100).toFixed(1)}%`,
    p_ecl      > 0.005 && `ECL: ${(p_ecl * 100).toFixed(1)}%`,
    p_safe     > 0.005 && `Safe: ${(p_safe * 100).toFixed(1)}%`,
    p_playoff  > 0.005 && `Playoff: ${(p_playoff * 100).toFixed(1)}%`,
    p_relegated> 0.005 && `Rel: ${(p_relegated * 100).toFixed(1)}%`,
  ].filter(Boolean).join(' · ')

  return (
    <div className="zone-bar" title={tooltip}>
      {segments.map(({ key, pct, cls }) =>
        pct > 0.002
          ? <div key={key} className={`zb-seg ${cls}`} style={{ width: `${pct * 100}%` }}>
              {pct >= 0.12 && <span className="zb-label">{fmt(pct)}</span>}
            </div>
          : null
      )}
    </div>
  )
}

export default function LeagueTable({ onTeamClick }) {
  const [table, setTable]     = useState([])
  const [simMap, setSimMap]   = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [sortKey, setSortKey] = useState('position')
  const [sortDir, setSortDir] = useState(1)

  useEffect(() => {
    axios.get('/api/table')
      .then(res => setTable(res.data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  useEffect(() => {
    axios.get('/api/simulation')
      .then(res => {
        const map = {}
        res.data.teams.forEach(t => { map[t.team_name] = t })
        setSimMap(map)
      })
      .catch(() => {})  // simulation is optional — fail silently
  }, [])

  function handleSort(key) {
    if (sortKey === key) setSortDir(d => -d)
    else { setSortKey(key); setSortDir(key === 'position' ? 1 : -1) }
  }

  const sorted = [...table].sort((a, b) => {
    const av = a[sortKey] ?? 0
    const bv = b[sortKey] ?? 0
    return sortDir * (typeof av === 'string' ? av.localeCompare(bv) : av - bv)
  })

  if (loading) return <div className="status">Loading table…</div>
  if (error)   return <div className="status error">Error: {error}</div>

  const simReady = Object.keys(simMap).length > 0

  return (
    <div className="league-table-wrapper">
      <div className="zone-legend">
        {ZONES.map(z => (
          <span key={z.cls} className={`zone-badge ${z.cls}`}>{z.label}</span>
        ))}
      </div>
      <table className="league-table">
        <thead>
          <tr>
            <SortHeader label="#"   k="position" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <th>Team</th>
            <SortHeader label="P"   k="played"   sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader label="W"   k="won"      sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader label="D"   k="draw"     sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader label="L"   k="lost"     sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader label="GD"  k="goal_difference" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader label="Pts" k="points"   sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <th className="col-form">Form</th>
            <SortHeader label="xPts left" k="expected_pts_remaining" sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <SortHeader label="Projected" k="projected_total"        sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
            <th className="col-finish" title="Monte Carlo season finish probabilities (10 000 simulations)">
              Finish zones {simReady ? '' : '…'}
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map(row => (
            <tr key={row.team.id} className={zoneClass(row.position)}>
              <td className="col-pos">{row.position}</td>
              <td className="col-team">
                {row.team.crest_url && <img src={row.team.crest_url} className="table-crest" alt="" />}
                <button className="team-name-btn" onClick={() => onTeamClick?.(row.team.name)}>{row.team.short_name}</button>
              </td>
              <td>{row.played}</td>
              <td>{row.won}</td>
              <td>{row.draw}</td>
              <td>{row.lost}</td>
              <td className={row.goal_difference > 0 ? 'pos' : row.goal_difference < 0 ? 'neg' : ''}>
                {row.goal_difference > 0 ? '+' : ''}{row.goal_difference}
              </td>
              <td className="col-pts">{row.points}</td>
              <td className="col-form"><FormPips form={row.form} /></td>
              <td className="col-xpts">{row.expected_pts_remaining.toFixed(1)}</td>
              <td className="col-proj">{row.projected_total.toFixed(1)}</td>
              <td className="col-finish">
                <ZoneBar sim={simMap[row.team.name]} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
