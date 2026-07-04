import { useState } from 'react'
import AppSidebar from '../AppSidebar'
import {
  usePipelineStatus,
  usePipelineHealth,
  useDataFreshness,
  useRetrainingStatus,
} from '../../hooks/useStatusData'
import HealthBar from './HealthBar'
import StageFlow from './StageFlow'
import StageDetail from './StageDetail'
import RegionMatrix from './RegionMatrix'
import RetrainingTable from './RetrainingTable'
import ErrorsFeed from './ErrorsFeed'

const cardStyle: React.CSSProperties = {
  background: 'var(--panelBg, var(--glassBg))',
  border: '1px solid var(--glassBorder)',
  borderRadius: 16,
  padding: '16px 20px',
  backdropFilter: 'blur(24px) saturate(160%)',
  WebkitBackdropFilter: 'blur(24px) saturate(160%)',
}

export default function StatusPage() {
  const status = usePipelineStatus()
  const health = usePipelineHealth()
  const freshness = useDataFreshness()
  const retraining = useRetrainingStatus()
  const [selectedStage, setSelectedStage] = useState<string | null>(null)

  const stages = status.data?.stages ?? []
  const selected = stages.find(s => s.key === selectedStage) || null

  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--appBg, transparent)' }}>
      <AppSidebar />
      <main
        style={{
          flex: 1,
          marginLeft: 63,
          padding: '24px 32px 64px',
          display: 'flex',
          flexDirection: 'column',
          gap: 20,
          maxWidth: 1400,
          color: 'var(--glassText)',
        }}
      >
        <header style={{ display: 'flex', alignItems: 'baseline', gap: 16, flexWrap: 'wrap' }}>
          <h1 style={{ fontSize: 24, fontWeight: 600, margin: 0 }}>Pipeline Status</h1>
          <span style={{ color: 'var(--muted)', fontSize: 13 }}>
            {status.data
              ? `Updated ${new Date(status.data.generated_at).toLocaleTimeString()}`
              : status.error
                ? `Cannot reach API: ${status.error}`
                : 'Loading…'}
          </span>
          <button
            onClick={() => { status.refresh(); health.refresh(); freshness.refresh(); retraining.refresh() }}
            style={{
              marginLeft: 'auto',
              padding: '6px 14px',
              borderRadius: 10,
              border: '1px solid var(--glassBorder)',
              background: 'var(--glassBg)',
              color: 'var(--glassText)',
              cursor: 'pointer',
              fontSize: 13,
            }}
          >
            Refresh
          </button>
        </header>

        <section style={cardStyle}>
          <HealthBar health={health.data} error={health.error} />
        </section>

        <section style={cardStyle}>
          <h2 style={{ fontSize: 15, fontWeight: 600, margin: '0 0 14px' }}>End-to-end stages</h2>
          <StageFlow
            stages={stages}
            selectedKey={selectedStage}
            onSelect={key => setSelectedStage(key === selectedStage ? null : key)}
          />
          {selected && <StageDetail stage={selected} />}
        </section>

        <section style={cardStyle}>
          <h2 style={{ fontSize: 15, fontWeight: 600, margin: '0 0 14px' }}>Recent errors</h2>
          <ErrorsFeed stages={stages} />
        </section>

        <section style={cardStyle}>
          <h2 style={{ fontSize: 15, fontWeight: 600, margin: '0 0 14px' }}>
            Region data freshness
          </h2>
          <RegionMatrix rows={freshness.data?.status ?? []} loading={freshness.loading} />
        </section>

        <section style={cardStyle}>
          <h2 style={{ fontSize: 15, fontWeight: 600, margin: '0 0 14px' }}>Model retraining</h2>
          <RetrainingTable rows={retraining.data?.retraining_status ?? []} loading={retraining.loading} />
        </section>
      </main>
    </div>
  )
}
