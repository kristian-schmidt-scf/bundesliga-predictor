import { useEffect, useState } from 'react'
import axios from 'axios'
import './LeagueTable.css'

const ZONES = [
  { from: 1,  to: 4,  label: 'Champions League', cls: 'zone-cl' },
  { from: 5,  to: 6,  label: 'Europa League',    cls: 'zone-el' },
  { from: 7,  to: 7,  label: 'Conference League', cls: 'zone-ecl' },
  { from: 16, to: 16, label: 'Relegation playoff', cls: 'zone-playoff' },
  { from: 17, to: 18, label: 'Relegated',          cls: 'zone-rel' },
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

export default function LeagueTable() {
  const [table, setTable] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [sortKey, setSortKey] = useState('position')
  const [sortDir, setSortDir] = useState(1)

  useEffect(() => {
    axios.get('/api/table')
      .then(res => setTable(res.data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
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

  function SortHeader({ label, k }) {
    const active = sortKey === k
    return (
      <th className={`sortable${active ? ' active' : ''}`} onClick={() => handleSort(k)}>
        {label}{active ? (sortDir === 1 ? ' ↑' : ' ↓') : ''}
      </th>
    )
  }

  if (loading) return <div className="status">Loading table…</div>
  if (error)   return <div className="status error">Error: {error}</div>

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
            <SortHeader label="#"   k="position" />
            <th>Team</th>
            <SortHeader label="P"   k="played" />
            <SortHeader label="W"   k="won" />
            <SortHeader label="D"   k="draw" />
            <SortHeader label="L"   k="lost" />
            <SortHeader label="GD"  k="goal_difference" />
            <SortHeader label="Pts" k="points" />
            <th className="col-form">Form</th>
            <SortHeader label="xPts left" k="expected_pts_remaining" />
            <SortHeader label="Projected"  k="projected_total" />
          </tr>
        </thead>
        <tbody>
          {sorted.map(row => (
            <tr key={row.team.id} className={zoneClass(row.position)}>
              <td className="col-pos">{row.position}</td>
              <td className="col-team">
                {row.team.crest_url && <img src={row.team.crest_url} className="table-crest" alt="" />}
                <span>{row.team.short_name}</span>
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
