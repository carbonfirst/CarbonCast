import type { RegionFreshness } from '../../hooks/useStatusData'

type CellState = 'ok' | 'warn' | 'bad' | 'none'

const CELL_COLORS: Record<CellState, string> = {
  ok: '#22C55E',
  warn: '#F59E0B',
  bad: '#EF4444',
  none: 'var(--glassBorder)',
}

function Cell({ state, title }: { state: CellState; title: string }) {
  return (
    <td style={{ padding: 3 }} title={title}>
      <div
        style={{
          width: 16,
          height: 16,
          borderRadius: 4,
          background: CELL_COLORS[state],
          opacity: state === 'none' ? 0.5 : 0.9,
        }}
      />
    </td>
  )
}

export default function RegionMatrix({
  rows,
  loading,
}: {
  rows: RegionFreshness[]
  loading: boolean
}) {
  if (loading && !rows.length) {
    return <div style={{ color: 'var(--muted)', fontSize: 14 }}>Loading region freshness…</div>
  }
  if (!rows.length) {
    return (
      <div style={{ color: 'var(--muted)', fontSize: 14 }}>
        No regions have data yet — seed energy actuals with import_csvs, or wait for the first ingestion cycle.
      </div>
    )
  }

  return (
    <div style={{ overflowX: 'auto' }}>
      <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--muted)', marginBottom: 10, flexWrap: 'wrap' }}>
        <span><span style={{ color: CELL_COLORS.ok }}>■</span> fresh</span>
        <span><span style={{ color: CELL_COLORS.warn }}>■</span> fallback / stale</span>
        <span><span style={{ color: CELL_COLORS.bad }}>■</span> missing</span>
        <span>Columns: Actuals · Weather · Forecast</span>
      </div>
      <table style={{ borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr style={{ color: 'var(--muted)', textAlign: 'left' }}>
            <th style={{ padding: '2px 10px 6px 0', fontWeight: 500 }}>Region</th>
            <th style={{ padding: '2px 6px 6px', fontWeight: 500 }}>A</th>
            <th style={{ padding: '2px 6px 6px', fontWeight: 500 }}>W</th>
            <th style={{ padding: '2px 6px 6px', fontWeight: 500 }}>F</th>
            <th style={{ padding: '2px 6px 6px 12px', fontWeight: 500 }}>Weather source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => {
            const actuals: CellState = row.latest_actual_ts
              ? row.actuals_stale ? 'warn' : 'ok'
              : 'bad'
            const weather: CellState = row.latest_weather_created
              ? row.weather_is_fallback ? 'warn' : row.weather_stale ? 'warn' : 'ok'
              : 'bad'
            const forecast: CellState = row.latest_forecast_ts
              ? row.forecast_missing_or_short ? 'warn' : 'ok'
              : 'bad'
            return (
              <tr key={row.region} style={{ borderTop: '1px solid var(--glassBorder)' }}>
                <td style={{ padding: '3px 10px 3px 0', fontWeight: 600 }}>{row.region}</td>
                <Cell state={actuals} title={`Actuals: ${row.latest_actual_ts || 'none'}${row.actuals_stale ? ' (stale >2d)' : ''}`} />
                <Cell state={weather} title={`Weather: ${row.latest_weather_created || 'none'}${row.weather_is_fallback ? ' (historical fallback)' : ''}${row.weather_stale ? ' (stale >6h)' : ''}`} />
                <Cell state={forecast} title={`Forecast: ${row.latest_forecast_ts || 'none'}${row.forecast_missing_or_short ? ' (short horizon)' : ''}`} />
                <td style={{ padding: '3px 6px 3px 12px', color: row.weather_is_fallback ? '#F59E0B' : 'var(--muted)' }}>
                  {row.weather_source || '—'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
