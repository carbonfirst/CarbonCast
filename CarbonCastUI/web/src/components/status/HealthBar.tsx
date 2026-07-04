import type { PipelineHealthPayload } from '../../hooks/useStatusData'

const CHECK_LABELS: Record<string, string> = {
  database: 'Database',
  redis_cache: 'Redis',
  celery_worker: 'Celery worker',
  celery_beat: 'Celery beat',
}

export default function HealthBar({
  health,
  error,
}: {
  health: PipelineHealthPayload | null
  error: string | null
}) {
  if (error) {
    return (
      <div style={{ color: '#EF4444', fontSize: 14 }}>
        API unreachable — {error}. Is the Django server running?
      </div>
    )
  }
  if (!health) {
    return <div style={{ color: 'var(--muted)', fontSize: 14 }}>Checking component health…</div>
  }

  return (
    <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
      {Object.entries(health.checks).map(([key, check]) => (
        <div
          key={key}
          title={check.error || (check.ok ? 'healthy' : 'unhealthy')}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '6px 14px',
            borderRadius: 999,
            fontSize: 13,
            border: '1px solid var(--glassBorder)',
            background: check.ok ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)',
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              borderRadius: '50%',
              background: check.ok ? '#22C55E' : '#EF4444',
              boxShadow: check.ok ? '0 0 6px rgba(34,197,94,0.7)' : '0 0 6px rgba(239,68,68,0.7)',
            }}
          />
          {CHECK_LABELS[key] || key}
          {!check.ok && check.error && (
            <span style={{ color: 'var(--muted)', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              — {check.error}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}
