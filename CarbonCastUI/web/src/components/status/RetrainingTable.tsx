import type { RetrainingRow } from '../../hooks/useStatusData'

const STATUS_COLOR: Record<string, string> = {
  completed: '#22C55E',
  running: '#3B82F6',
  failed: '#EF4444',
}

function fmt(iso: string | null) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export default function RetrainingTable({
  rows,
  loading,
}: {
  rows: RetrainingRow[]
  loading: boolean
}) {
  if (loading && !rows.length) {
    return <div style={{ color: 'var(--muted)', fontSize: 14 }}>Loading retraining runs…</div>
  }
  if (!rows.length) {
    return (
      <div style={{ color: 'var(--muted)', fontSize: 14 }}>
        No retraining runs yet — the weekly retrain task runs Monday 06:00 UTC (or trigger it manually).
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ borderCollapse: 'collapse', width: '100%', fontSize: 12.5 }}>
        <thead>
          <tr style={{ color: 'var(--muted)', textAlign: 'left' }}>
            {['Region', 'Model', 'Status', 'Weather', 'Started', 'Completed', 'Rows', 'Error'].map(h => (
              <th key={h} style={{ padding: '4px 12px 8px 0', fontWeight: 500 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.region} style={{ borderTop: '1px solid var(--glassBorder)' }}>
              <td style={{ padding: '5px 12px 5px 0', fontWeight: 600 }}>{row.region}</td>
              <td style={{ padding: '5px 12px 5px 0' }}>{row.model_name}</td>
              <td style={{ padding: '5px 12px 5px 0', color: STATUS_COLOR[row.status] || 'var(--glassText)', fontWeight: 600 }}>
                {row.status}
              </td>
              <td style={{ padding: '5px 12px 5px 0', color: row.weather_is_fallback ? '#F59E0B' : 'var(--glassText)' }}>
                {row.weather_source}{row.weather_is_fallback ? ' ⚠' : ''}
              </td>
              <td style={{ padding: '5px 12px 5px 0', whiteSpace: 'nowrap' }}>{fmt(row.run_started)}</td>
              <td style={{ padding: '5px 12px 5px 0', whiteSpace: 'nowrap' }}>{fmt(row.run_completed)}</td>
              <td style={{ padding: '5px 12px 5px 0' }}>
                {row.forecast_rows
                  ? Object.entries(row.forecast_rows).map(([k, v]) => `${k}:${v}`).join(' ')
                  : '—'}
              </td>
              <td style={{ padding: '5px 0', color: '#EF4444', maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.error || undefined}>
                {row.error || ''}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
