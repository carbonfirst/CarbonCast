import type { PipelineStage } from '../../hooks/useStatusData'
import { STATUS_COLORS, STATUS_LABELS } from '../../hooks/useStatusData'

export default function StageFlow({
  stages,
  selectedKey,
  onSelect,
}: {
  stages: PipelineStage[]
  selectedKey: string | null
  onSelect: (key: string) => void
}) {
  if (!stages.length) {
    return <div style={{ color: 'var(--muted)', fontSize: 14 }}>Loading pipeline stages…</div>
  }

  return (
    <div style={{ display: 'flex', alignItems: 'stretch', gap: 0, overflowX: 'auto', paddingBottom: 6 }}>
      {stages.map((stage, i) => {
        const color = STATUS_COLORS[stage.status] || '#94A3B8'
        const isSelected = stage.key === selectedKey
        return (
          <div key={stage.key} style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
            <button
              onClick={() => onSelect(stage.key)}
              style={{
                minWidth: 132,
                textAlign: 'left',
                padding: '10px 12px',
                borderRadius: 12,
                cursor: 'pointer',
                border: isSelected ? `1.5px solid ${color}` : '1px solid var(--glassBorder)',
                background: isSelected ? `${color}22` : 'var(--glassBg)',
                color: 'var(--glassText)',
                transition: 'background 120ms, border 120ms',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                <span style={{ width: 9, height: 9, borderRadius: '50%', background: color, flexShrink: 0 }} />
                <span style={{ fontSize: 11, fontWeight: 600, color, letterSpacing: 0.3 }}>
                  {STATUS_LABELS[stage.status] || stage.status}
                </span>
              </div>
              <div style={{ fontSize: 12.5, fontWeight: 500, lineHeight: 1.25 }}>{stage.label}</div>
            </button>
            {i < stages.length - 1 && (
              <svg width="22" height="12" viewBox="0 0 22 12" style={{ flexShrink: 0, margin: '0 2px', color: 'var(--muted)' }}>
                <path d="M0 6h18M14 1l5 5-5 5" stroke="currentColor" strokeWidth="1.5" fill="none" />
              </svg>
            )}
          </div>
        )
      })}
    </div>
  )
}
