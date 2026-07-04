import type { PipelineStage } from '../../hooks/useStatusData'

interface FeedItem {
  stage: string
  when: string | null
  error: string
  traceback_tail?: string | null
}

export default function ErrorsFeed({ stages }: { stages: PipelineStage[] }) {
  const items: FeedItem[] = stages
    .flatMap(stage =>
      (stage.recent_errors || []).map(e => ({ stage: stage.label, ...e })),
    )
    .sort((a, b) => (b.when || '').localeCompare(a.when || ''))
    .slice(0, 20)

  // Region-level errors surfaced inside metrics (EIA/ENTSOE partial runs,
  // failed retraining regions) are worth showing too
  const regionErrors: FeedItem[] = stages.flatMap(stage => [
    ...((stage.metrics?.region_errors as any[]) || []).map((e: any) => ({
      stage: stage.label,
      when: stage.last_run,
      error: `${e.region}: ${e.error}`,
    })),
    ...((stage.metrics?.failed_regions as any[]) || []).map((e: any) => ({
      stage: stage.label,
      when: stage.last_run,
      error: `${e.region}: ${e.error}`,
    })),
  ])

  const all = [...items, ...regionErrors].slice(0, 25)

  if (!all.length) {
    return <div style={{ color: 'var(--muted)', fontSize: 14 }}>No recent errors recorded. 🎉</div>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 320, overflowY: 'auto' }}>
      {all.map((item, i) => (
        <div
          key={i}
          style={{
            padding: '8px 12px',
            borderRadius: 10,
            border: '1px solid rgba(239,68,68,0.3)',
            background: 'rgba(239,68,68,0.07)',
            fontSize: 12.5,
          }}
        >
          <div style={{ display: 'flex', gap: 10, marginBottom: 3 }}>
            <strong>{item.stage}</strong>
            <span style={{ color: 'var(--muted)' }}>
              {item.when ? new Date(item.when).toLocaleString() : ''}
            </span>
          </div>
          <div style={{ wordBreak: 'break-word', color: 'var(--glassText)' }}>{item.error}</div>
          {item.traceback_tail && (
            <details style={{ marginTop: 4 }}>
              <summary style={{ cursor: 'pointer', color: 'var(--muted)', fontSize: 11.5 }}>traceback</summary>
              <pre style={{ fontSize: 11, whiteSpace: 'pre-wrap', margin: '4px 0 0' }}>{item.traceback_tail}</pre>
            </details>
          )}
        </div>
      ))}
    </div>
  )
}
