import { useEffect, useState } from 'react'
import axios from 'axios'
import { BL1_ZONES } from '../utils/leagueZones'
import './LeagueTable.css'

function zoneClass(position, zones) {
  const z = zones.find(z => position >= z.from && position <= z.to)
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

function ZoneBar({ sim, zones }) {
  if (!sim) return <span className="zone-bar-placeholder">—</span>

  const zonePct = zones.map(z => Math.max(0, sim[z.simKey] ?? 0))
  const p_safe = Math.max(0, 1 - zonePct.reduce((a, b) => a + b, 0))

  const segments = [
    ...zones.map((z, i) => ({ key: z.simKey, pct: zonePct[i], cls: z.barCls, label: z.label })),
    { key: 'safe', pct: p_safe, cls: 'zb-safe', label: 'Safe' },
  ]

  const fmt = p => p >= 0.005 ? `${(p * 100).toFixed(0)}%` : null

  const tooltip = segments
    .filter(s => s.pct > 0.005)
    .map(s => `${s.label}: ${(s.pct * 100).toFixed(1)}%`)
    .join(' · ')

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

export default function LeagueTable({ onTeamClick, tableEndpoint = '/api/table', simEndpoint = '/api/simulation', zones = BL1_ZONES }) {
  const [tableState, setTableState] = useState({ endpoint: null, rows: [], error: null })
  const [simMap, setSimMap]   = useState({})
  const [sortKey, setSortKey] = useState('position')
  const [sortDir, setSortDir] = useState(1)

  const table   = tableState.rows
  const loading = tableState.endpoint !== tableEndpoint
  const error   = tableState.error

  useEffect(() => {
    axios.get(tableEndpoint)
      .then(res => setTableState({ endpoint: tableEndpoint, rows: res.data, error: null }))
      .catch(err => setTableState({ endpoint: tableEndpoint, rows: [], error: err.message }))
  }, [tableEndpoint])

  useEffect(() => {
    axios.get(simEndpoint)
      .then(res => {
        const map = {}
        res.data.teams.forEach(t => { map[t.team_name] = t })
        setSimMap(map)
      })
      .catch(() => {})  // simulation is optional — fail silently
  }, [simEndpoint])

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
        {zones.map(z => (
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
            <tr key={row.team.id} className={zoneClass(row.position, zones)}>
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
                <ZoneBar sim={simMap[row.team.name]} zones={zones} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
