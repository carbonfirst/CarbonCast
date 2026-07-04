import { useState, useEffect, useCallback } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export type StageStatus =
  | 'ok'
  | 'degraded'
  | 'failed'
  | 'stale'
  | 'waiting_on_credential'
  | 'waiting_on_config'
  | 'never_ran'

export interface StageError {
  when: string | null
  error: string
  traceback_tail?: string | null
}

export interface PipelineStage {
  key: string
  label: string
  status: StageStatus
  message: string
  last_run: string | null
  last_success: string | null
  metrics: Record<string, any>
  recent_errors: StageError[]
  history: { when: string | null; status: string; result: any }[]
}

export interface PipelineStatusPayload {
  generated_at: string
  overall: StageStatus
  stages: PipelineStage[]
}

export interface HealthCheck {
  ok: boolean
  error?: string
  last_heartbeat?: string
  last_dispatch?: string
}

export interface PipelineHealthPayload {
  ok: boolean
  generated_at: string
  checks: Record<string, HealthCheck>
}

export interface RegionFreshness {
  region: string
  latest_actual_ts: string | null
  latest_weather_created: string | null
  latest_forecast_ts: string | null
  weather_source: string | null
  weather_is_fallback: boolean
  actuals_stale: boolean
  weather_stale: boolean
  forecast_missing_or_short: boolean
}

export interface RetrainingRow {
  region: string
  model_name: string
  status: string
  weather_source: string
  weather_is_fallback: boolean
  run_started: string | null
  run_completed: string | null
  forecast_horizon: number | null
  batch_id: string | null
  forecast_rows: Record<string, number> | null
  error: string | null
}

interface PollState<T> {
  data: T | null
  loading: boolean
  error: string | null
  refresh: () => void
}

function usePolledEndpoint<T>(path: string, intervalMs: number): PollState<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tick, setTick] = useState(0)

  const refresh = useCallback(() => setTick(t => t + 1), [])

  useEffect(() => {
    let cancelled = false
    const controller = new AbortController()

    const fetchOnce = async () => {
      try {
        const res = await fetch(`${API_BASE}${path}`, { signal: controller.signal })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json = await res.json()
        if (!cancelled) {
          setData(json)
          setError(null)
        }
      } catch (e: any) {
        if (!cancelled && e.name !== 'AbortError') {
          setError(e.message || 'fetch failed')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    fetchOnce()
    const id = setInterval(fetchOnce, intervalMs)
    return () => {
      cancelled = true
      controller.abort()
      clearInterval(id)
    }
  }, [path, intervalMs, tick])

  return { data, loading, error, refresh }
}

export function usePipelineStatus(intervalMs = 30000) {
  return usePolledEndpoint<PipelineStatusPayload>('/v1/PipelineStatus', intervalMs)
}

export function usePipelineHealth(intervalMs = 30000) {
  return usePolledEndpoint<PipelineHealthPayload>('/v1/PipelineHealth', intervalMs)
}

export function useDataFreshness(intervalMs = 60000) {
  return usePolledEndpoint<{ status: RegionFreshness[] }>('/v1/DataFreshness', intervalMs)
}

export function useRetrainingStatus(intervalMs = 60000) {
  return usePolledEndpoint<{ retraining_status: RetrainingRow[] }>('/v1/RetrainingStatus', intervalMs)
}

export const STATUS_COLORS: Record<StageStatus, string> = {
  ok: '#22C55E',
  degraded: '#F59E0B',
  failed: '#EF4444',
  stale: '#F97316',
  waiting_on_credential: '#8B5CF6',
  waiting_on_config: '#6B7280',
  never_ran: '#94A3B8',
}

export const STATUS_LABELS: Record<StageStatus, string> = {
  ok: 'OK',
  degraded: 'Degraded',
  failed: 'Failed',
  stale: 'Stale',
  waiting_on_credential: 'Needs credential',
  waiting_on_config: 'Needs config',
  never_ran: 'Never ran',
}
