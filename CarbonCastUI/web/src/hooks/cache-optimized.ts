import { useState, useEffect, useRef } from 'react'
import { PerformanceLogger } from './performance-logger'

export interface TimelineState {
  mode: 'past' | 'now' | 'future'
  date: string
  hour: number
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Single cache for hour-specific data
const hourCache = new Map<string, { data: any; timestamp: number; ttl: number }>()
const HOUR_CACHE_TTL = 5 * 60 * 1000 // 5 minutes for hour-specific data

// Optimized cache key generation
const getHourCacheKey = (date: string, hour: number, mode: string): string => {
  return `${mode}_${date}_h${hour}`
}

// Fast hour-specific fetch
const fetchSingleHour = async (
  date: string, 
  hour: number, 
  mode: string
): Promise<any> => {
  const cacheKey = getHourCacheKey(date, hour, mode)
  
  // Check cache first
  const cached = hourCache.get(cacheKey)
  if (cached && Date.now() - cached.timestamp < cached.ttl) {
    PerformanceLogger.increment('cache_hits')
    return cached.data
  }
  
  // Use optimized endpoint
  const endpoint = mode === 'past' 
    ? '/v1/CarbonIntensityHistoryOptimized' 
    : '/v1/CarbonIntensityForecastsHistoryOptimized'
  
  const url = `${API_BASE}${endpoint}?region_code=all&date=${date}&hour=${hour}`
  
  PerformanceLogger.startTimer(`fetch_hour_${date}_${hour}`)
  PerformanceLogger.logNetworkRequest(url)
  
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`)
  }
  
  const result = await response.json()
  PerformanceLogger.endTimer(`fetch_hour_${date}_${hour}`)
  PerformanceLogger.logDataSize(`hour_${date}_${hour}`, result)
  
  // Cache the result
  hourCache.set(cacheKey, {
    data: result,
    timestamp: Date.now(),
    ttl: HOUR_CACHE_TTL
  })
  
  PerformanceLogger.increment('api_calls')
  return result
}

// OPTIMIZED Carbon Intensity Hook
export const useOptimizedCarbonIntensityData = (timelineState: TimelineState) => {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [backgroundLoading, setBackgroundLoading] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  useEffect(() => {
    // Cancel any ongoing requests
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()

    const fetchData = async () => {
      if (timelineState.mode === 'now') {
        // Handle 'now' mode separately (existing logic)
        return
      }

      try {
        PerformanceLogger.startTimer(`total_load_${timelineState.date}_${timelineState.hour}`)
        setLoading(true)
        setError(null)

        // OPTIMIZATION: Fetch only the current hour immediately
        const hourData = await fetchSingleHour(
          timelineState.date, 
          timelineState.hour, 
          timelineState.mode
        )

        // Update UI immediately with current hour data
        setData(hourData)
        setLoading(false) // ✅ Stop loading indicator immediately
        PerformanceLogger.endTimer(`total_load_${timelineState.date}_${timelineState.hour}`)

        // BACKGROUND: Prefetch adjacent hours (optional, low priority)
        setBackgroundLoading(true)
        const adjacentHours = [
          timelineState.hour - 1, 
          timelineState.hour + 1
        ].filter(h => h >= 0 && h < 24)

        Promise.all(
          adjacentHours.map(h =>
            fetchSingleHour(timelineState.date, h, timelineState.mode)
              .catch(() => {}) // Silent prefetch failure
          )
        ).finally(() => {
          setBackgroundLoading(false)
        })

      } catch (err: any) {
        if (err.name === 'AbortError') return
        setError(err.message)
        setLoading(false)
        setBackgroundLoading(false)
      }
    }

    fetchData()

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [timelineState.mode, timelineState.date, timelineState.hour]) // React to ALL changes

  return { data, loading, error, backgroundLoading }
}

// Efficient cache management
export const clearOptimizedCache = () => {
  hourCache.clear()
  PerformanceLogger.reset()
}

// Cache statistics
export const getOptimizedCacheStats = () => {
  const perfStats = PerformanceLogger.getStats()
  return {
    hourCacheSize: hourCache.size,
    cacheHitRatio: perfStats.cache_hits / (perfStats.cache_hits + perfStats.api_calls) || 0,
    ...perfStats
  }
}