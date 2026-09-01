// Each zone drives three things at once: which table rows get highlighted
// (from/to/cls), the legend, and one segment of the Monte Carlo ZoneBar
// (simKey reads the matching probability off /api/simulation's response,
// which reuses the same p_cl/p_el/p_ecl/p_playoff/p_relegated field names
// for both competitions — only the label/meaning differs per competition).
export const BL1_ZONES = [
  { from: 1,  to: 4,  label: 'Champions League',   cls: 'zone-cl',      simKey: 'p_cl',       barCls: 'zb-cl' },
  { from: 5,  to: 6,  label: 'Europa League',       cls: 'zone-el',      simKey: 'p_el',       barCls: 'zb-el' },
  { from: 7,  to: 7,  label: 'Conference League',   cls: 'zone-ecl',     simKey: 'p_ecl',      barCls: 'zb-ecl' },
  { from: 16, to: 16, label: 'Relegation playoff',  cls: 'zone-playoff', simKey: 'p_playoff',  barCls: 'zb-playoff' },
  { from: 17, to: 18, label: 'Relegated',            cls: 'zone-rel',    simKey: 'p_relegated', barCls: 'zb-rel' },
]

export const BL2_ZONES = [
  { from: 1,  to: 2,  label: 'Promotion',            cls: 'zone-cl',      simKey: 'p_cl',       barCls: 'zb-cl' },
  { from: 3,  to: 3,  label: 'Promotion playoff',    cls: 'zone-playoff', simKey: 'p_playoff',  barCls: 'zb-playoff' },
  { from: 17, to: 18, label: 'Relegated',            cls: 'zone-rel',    simKey: 'p_relegated', barCls: 'zb-rel' },
]
