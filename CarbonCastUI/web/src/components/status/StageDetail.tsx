import type { PipelineStage } from '../../hooks/useStatusData'
import { STATUS_COLORS, STATUS_LABELS } from '../../hooks/useStatusData'

function fmtTime(iso: string | null) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function MetricValue({ value }: { value: any }) {
  if (value === null || value === undefined) return <span style={{ color: 'var(--muted)' }}>—</span>
  if (typeof value === 'object') {
    return (
      <pre
        style={{
          margin: 0,
          fontSize: 11.5,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          maxHeight: 180,
          overflowY: 'auto',
          color: 'var(--glassText)',
        }}
      >
        {JSON.stringify(value, null, 1)}
      </pre>
    )
  }
  return <span>{String(value)}</span>
}

export default function StageDetail({ stage }: { stage: PipelineStage }) {
  const color = STATUS_COLORS[stage.status] || '#94A3B8'

  return (
    <div
      style={{
        marginTop: 14,
        padding: '14px 16px',
        borderRadius: 12,
        border: `1px solid ${color}55`,
        background: `${color}0d`,
        fontSize: 13,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
        <strong style={{ fontSize: 14 }}>{stage.label}</strong>
        <span style={{ color, fontWeight: 600, fontSize: 12 }}>{STATUS_LABELS[stage.status]}</span>
        <span style={{ color: 'var(--muted)', fontSize: 12 }}>
          last run {fmtTime(stage.last_run)} · last success {fmtTime(stage.last_success)}
        </span>
      </div>

      <p style={{ margin: '0 0 12px', color: 'var(--glassText)' }}>{stage.message}</p>

      {Object.keys(stage.metrics || {}).length > 0 && (
        <table style={{ borderCollapse: 'collapse', width: '100%', marginBottom: 10 }}>
          <tbody>
            {Object.entries(stage.metrics).map(([k, v]) => (
              <tr key={k} style={{ borderTop: '1px solid var(--glassBorder)' }}>
                <td style={{ padding: '5px 12px 5px 0', color: 'var(--muted)', verticalAlign: 'top', whiteSpace: 'nowrap' }}>
                  {k}
                </td>
                <td style={{ padding: '5px 0' }}>
                  <MetricValue value={v} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {stage.history.length > 0 && (
        <div>
          <div style={{ color: 'var(--muted)', fontSize: 12, marginBottom: 4 }}>Recent runs</div>
          {stage.history.map((h, i) => (
            <div key={i} style={{ display: 'flex', gap: 10, fontSize: 12, padding: '3px 0', borderTop: '1px solid var(--glassBorder)' }}>
              <span style={{ whiteSpace: 'nowrap', color: 'var(--muted)' }}>{fmtTime(h.when)}</span>
              <span style={{ fontWeight: 600, color: h.status === 'SUCCESS' ? '#22C55E' : h.status === 'FAILURE' ? '#EF4444' : 'var(--glassText)' }}>
                {h.status}
              </span>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 620, color: 'var(--glassText)' }}>
                {typeof h.result === 'object' ? JSON.stringify(h.result) : String(h.result ?? '')}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
