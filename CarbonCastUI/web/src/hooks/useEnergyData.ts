import { useState, useEffect, useRef } from 'react'
import type { TimelineState } from './cache'
import { convertToApiRegionCode } from '../utils/regionMapping'
import { getCurrentUtcDate, getCurrentUtcHour } from '../utils/dateUtils'

// Use environment variable for API URL, fallback to localhost for development
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Reduced cache TTL for real-time updates - only cache for 30 seconds
const memoryCache = new Map<string, { data: any; metadata?: any; timestamp: number }>()
const CACHE_TTL = 30 * 1000 // 30 seconds cache for smoother updates

// Helper to generate cache key
const getCacheKey = (endpoint: string, params: Record<string, any>): string => {
  const sortedParams = Object.keys(params).sort().map(key => `${key}=${params[key]}`).join('&')
  return `${endpoint}?${sortedParams}`
}

// Helper to get from cache
const getFromCache = (key: string): any => {
  const cached = memoryCache.get(key)
  if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
    // IMPORTANT: Return new object references to trigger React re-renders
    return {
      data: cached.data ? { ...cached.data } : cached.data,
      metadata: cached.metadata ? { ...cached.metadata } : cached.metadata
    }
  }
  return null
}

// Helper to set cache - stores the full API response
const setCache = (key: string, result: any): void => {
  // Store the full result structure - don't extract data separately
  // This ensures consistency when reading back
  memoryCache.set(key, {
    data: result,  // Store full result (including result.data if present)
    metadata: result.metadata || result.fallback_metadata,
    timestamp: Date.now()
  })
}

// Helper to clear cache for a specific region
const clearRegionCache = (regionCode?: string): void => {
  if (!regionCode) return
  const keysToDelete: string[] = []
  memoryCache.forEach((_, key) => {
    if (key.includes(regionCode)) {
      keysToDelete.push(key)
    }
  })
  keysToDelete.forEach(key => memoryCache.delete(key))
}

// Track if this is the initial load
let isInitialLoad = true

// Helper to get priority hour for progressive loading.
// Hours sent to the API must be UTC: the backend filters ts__hour in UTC,
// so a local-clock hour paired with a UTC date fetches the wrong rows.
const getPriorityHour = (timelineState?: TimelineState): number => {
  if (isInitialLoad) {
    // On initial load, use the current UTC hour
    isInitialLoad = false
    return getCurrentUtcHour()
  } else if (timelineState) {
    // On date change, use current slider position
    return timelineState.hour
  }
  return getCurrentUtcHour()
}

export interface EnergySource {
  name: string
  value: number
  percentage: number
  color: string
}

export interface CarbonIntensityData {
  time: string
  value: number
}

// Color mapping for energy sources
const sourceColors: Record<string, string> = {
  coal: '#6B7280',
  'nat_gas': '#EF4444',
  'natural gas': '#EF4444',
  nuclear: '#10B981',
  oil: '#F59E0B',
  hydro: '#3B82F6',
  wind: '#06B6D4',
  solar: '#FCD34D',
  other: '#8B5CF6',
  biomass: '#84CC16',
  geothermal: '#FB923C',
  storage: '#EC4899'
}

// All standard energy sources that should always be displayed
const ALL_ENERGY_SOURCES = [
  'coal',
  'natural gas',
  'nuclear',
  'oil',
  'hydro',
  'solar',
  'wind',
  'other'
] as const

// Display names for energy sources
const sourceDisplayNames: Record<string, string> = {
  coal: 'Coal',
  'nat_gas': 'Natural gas',
  'natural gas': 'Natural gas',
  nuclear: 'Nuclear',
  oil: 'Oil',
  hydro: 'Hydro',
  wind: 'Wind',
  solar: 'Solar',
  other: 'Other',
  biomass: 'Biomass',
  geothermal: 'Geothermal',
  storage: 'Storage'
}

// Use the centralized convertToApiRegionCode function from regionMapping

export function useEnergyMix(regionCode: string | undefined, timelineState?: TimelineState) {
  const [data, setData] = useState<EnergySource[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fallbackInfo, setFallbackInfo] = useState<{ used: boolean; message?: string } | null>(null)
  const previousRegionRef = useRef<string | undefined>(undefined)
  const previousDateRef = useRef<string | undefined>(undefined)
  const backgroundLoadingRef = useRef<boolean>(false)

  useEffect(() => {
    if (!regionCode) {
      setData([])
      setTotal(0)
      return
    }

    // Don't clear cache when region changes - keep it for quick switching
    previousRegionRef.current = regionCode

    // Detect if date changed for progressive loading
    const dateChanged = previousDateRef.current && previousDateRef.current !== timelineState?.date
    previousDateRef.current = timelineState?.date

    // Create AbortController for this request
    const abortController = new AbortController()

    const processEnergyData = (energyData: Record<string, unknown>) => {
      // Create a map of all sources with their values (including zeros)
      const sourceMap = new Map<string, number>()
      
      // Initialize all standard sources with 0
      ALL_ENERGY_SOURCES.forEach(source => {
        sourceMap.set(source, 0)
      })
      
      let totalValue = 0
      
      Object.entries(energyData).forEach(([key, value]) => {
        // Handle both number and string number values (API sometimes returns strings)
        const isNumericValue = (typeof value === 'number') ||
                               (typeof value === 'string' && !isNaN(parseFloat(value)))
        
        if (isNumericValue &&
            key !== 'UTC time' &&
            key !== 'creation_time' &&
            key !== 'creation_time (UTC)' &&
            key !== 'version' &&
            key !== 'region_code' &&
            key !== 'timestamp' &&
            key !== 'id') {
          
          // Parse the value as a number
          const numericValue = typeof value === 'number' ? value : parseFloat(value as string)
          
          // Skip if value is NaN
          if (isNaN(numericValue)) {
            return
          }
          
          // Normalize the source name
          const sourceName = key.toLowerCase()
            .replace(/(.*)(coal|nat_gas|nuclear|oil|hydro|wind|solar|other|biomass|geothermal|storage)(.*)/g, '$2')
            .replace(/_/g, ' ')
            .replace(/nat gas/, 'natural gas')
          
          // Update the source value in our map
          const currentValue = sourceMap.get(sourceName) || 0
          sourceMap.set(sourceName, currentValue + numericValue)
          
          totalValue += numericValue
        }
      })
      
      // Convert map to array of EnergySource objects - include ALL sources
      const sources: EnergySource[] = []
      
      ALL_ENERGY_SOURCES.forEach(sourceName => {
        const value = sourceMap.get(sourceName) || 0
        const displayName = sourceDisplayNames[sourceName] || sourceName.charAt(0).toUpperCase() + sourceName.slice(1)
        
        sources.push({
          name: displayName,
          value: value,
          percentage: totalValue > 0 ? (value / totalValue) * 100 : 0,
          color: sourceColors[sourceName] || '#9CA3AF'
        })
      })
      
      // Sort by value (highest first), but keep zeros at the end
      sources.sort((a, b) => {
        // Both have values or both are zero - sort by value descending
        if ((a.value > 0 && b.value > 0) || (a.value === 0 && b.value === 0)) {
          return b.value - a.value
        }
        // Sources with value come before sources with zero
        return a.value === 0 ? 1 : -1
      })
      
      // If total is 0, we still return all sources with 0 values
      // The UI will handle this appropriately
      
      return { sources, totalValue }
    }

    const fetchEnergyMix = async () => {
      try {
        const apiRegionCode = convertToApiRegionCode(regionCode)
        
        // Progressive loading: determine priority hour
        const priorityHour = dateChanged || isInitialLoad ? getPriorityHour(timelineState) : timelineState?.hour ?? getCurrentUtcHour()
        
        // Build cache key for current hour
        let endpoint: string
        let params: Record<string, string | number>
        
        if (!timelineState || timelineState.mode === 'now') {
          endpoint = '/v1/EnergySources'
          params = { region_code: apiRegionCode }
        } else if (timelineState.mode === 'past') {
          endpoint = '/v1/EnergySourcesHistory'
          params = { region_code: apiRegionCode, date: timelineState.date, hour: priorityHour }
        } else {
          endpoint = '/v1/EnergySourcesForecastsHistory'
          params = { regionCode: apiRegionCode, date: timelineState.date, hour: priorityHour }
        }
        
        const cacheKey = getCacheKey(endpoint, params)
        
        // Check cache first for priority hour
        const cachedResult = getFromCache(cacheKey)
        if (cachedResult) {
          // cachedResult.data can be either:
          // 1. The full API response { data: [...], metadata: {...} }
          // 2. Just the data array [...]
          const cachedData = cachedResult.data
          const metadata = cachedResult.metadata
          
          // Check for fallback metadata
          if (metadata?.overall_fallback) {
            const actualDate = metadata.direct_actual_date || metadata.lifecycle_actual_date
            setFallbackInfo({
              used: true,
              message: `Data from ${actualDate} (requested ${metadata.requested_date})`
            })
          } else {
            setFallbackInfo(null)
          }
          
          // Determine if cachedData is the array or has .data property
          const dataArray = cachedData?.data || cachedData
          
          if (Array.isArray(dataArray) && dataArray.length > 0) {
            // Process cached data - ensure new array reference
            const processedData = processEnergyData(dataArray[0])
            // Check if we got valid data with non-zero total
            if (processedData.totalValue > 0) {
              setData([...processedData.sources])  // Force new array reference
              setTotal(processedData.totalValue)
              setError(null)
              // Return early - we have valid cached data
              return
            } else {
              // If cached data has zero total, it might be stale - fetch fresh
              memoryCache.delete(cacheKey)
            }
          } else if (typeof cachedData === 'object' && cachedData !== null && !Array.isArray(cachedData)) {
            // Handle case where cachedData is a single object (not array)
            const processedData = processEnergyData(cachedData)
            if (processedData.totalValue > 0) {
              setData([...processedData.sources])  // Force new array reference
              setTotal(processedData.totalValue)
              setError(null)
              return
            } else {
              memoryCache.delete(cacheKey)
            }
          }
          // If we get here, cached data was invalid - continue to fetch fresh
        }
        
        // Not in cache, need to fetch priority hour first
        setLoading(true)
        setError(null)
        
        // First, fetch priority hour data for immediate UI update
        let priorityUrl: string
        if (!timelineState || timelineState.mode === 'now') {
          priorityUrl = `${API_BASE}/v1/EnergySources?region_code=${apiRegionCode}`
        } else if (timelineState.mode === 'past') {
          priorityUrl = `${API_BASE}/v1/EnergySourcesHistory?region_code=${apiRegionCode}&date=${timelineState.date}&hour=${priorityHour}`
        } else {
          priorityUrl = `${API_BASE}/v1/EnergySourcesForecastsHistory?regionCode=${apiRegionCode}&date=${timelineState.date}&hour=${priorityHour}`
        }
        
        const priorityResponse = await fetch(priorityUrl, { signal: abortController.signal })
        
        if (!priorityResponse.ok) {
          // Special handling for forecast API failures
          if (priorityResponse.status === 500 && timelineState?.mode === 'future') {
            // Try fallback to past data for the same date/hour
            const fallbackUrl = `${API_BASE}/v1/EnergySourcesHistory?region_code=${apiRegionCode}&date=${timelineState.date}&hour=${priorityHour}`
            
            try {
              const fallbackResponse = await fetch(fallbackUrl, { signal: abortController.signal })
              if (fallbackResponse.ok) {
                const fallbackResult = await fallbackResponse.json()
                
                // Process the fallback data
                if (fallbackResult.data && fallbackResult.data.length > 0) {
                  const { sources, totalValue } = processEnergyData(fallbackResult.data[0])
                  setData([...sources])
                  setTotal(totalValue)
                  setLoading(false)
                  setFallbackInfo({
                    used: true,
                    message: 'Forecast unavailable, showing historical data'
                  })
                  setError(null)
                  
                  // Cache the successful fallback
                  setCache(cacheKey, fallbackResult)
                  return
                } else if (fallbackResult && !fallbackResult.data) {
                  const processedData = processEnergyData(fallbackResult)
                  setData([...processedData.sources])
                  setTotal(processedData.totalValue)
                  setLoading(false)
                  setFallbackInfo({
                    used: true,
                    message: 'Forecast unavailable, showing historical data'
                  })
                  setError(null)
                  setCache(cacheKey, fallbackResult)
                  return
                }
              }
            } catch {
              // Fallback also failed, continue to show error
            }
          }
          
          // Set error state but don't throw - show graceful error in UI
          setError(`Unable to load energy data (${priorityResponse.status})`)
          setLoading(false)
          setData([{
            name: 'Data unavailable',
            value: 0,
            percentage: 100,
            color: '#9CA3AF'
          }])
          setTotal(0)
          return
        }
        
        const priorityResult = await priorityResponse.json()
        
        // Cache the priority result
        setCache(cacheKey, priorityResult)
        
        // Process and display priority hour data immediately
        if (priorityResult.data && priorityResult.data.length > 0) {
          const { sources, totalValue } = processEnergyData(priorityResult.data[0])
          setData([...sources])  // Force new array reference
          setTotal(totalValue)
          setLoading(false) // Stop loading indicator after first data
          
          // Check for fallback metadata
          // Backend returns: overall_fallback, lifecycle_actual_date, direct_actual_date, requested_date
          if (priorityResult.metadata?.overall_fallback) {
            const actualDate = priorityResult.metadata.direct_actual_date || priorityResult.metadata.lifecycle_actual_date
            setFallbackInfo({
              used: true,
              message: `Data from ${actualDate} (requested ${priorityResult.metadata.requested_date})`
            })
          } else {
            setFallbackInfo(null)
          }
        } else if (priorityResult && !priorityResult.data) {
          // Handle case where result is the data directly (not wrapped)
          const processedData = processEnergyData(priorityResult)
          setData([...processedData.sources])  // Force new array reference
          setTotal(processedData.totalValue)
          setLoading(false)
          setFallbackInfo(null)
        } else {
          // Set empty data but don't cache it
          setData([{
            name: 'No data available',
            value: 0,
            percentage: 100,
            color: '#9CA3AF'
          }])
          setTotal(0)
          setError(null)
          setLoading(false)
        }
        
        // If current hour is different from priority hour, fetch it too
        if (timelineState && timelineState.hour !== priorityHour && !backgroundLoadingRef.current) {
          backgroundLoadingRef.current = true
          
          // Build URL for current hour
          let currentUrl: string
          if (timelineState.mode === 'past') {
            currentUrl = `${API_BASE}/v1/EnergySourcesHistory?region_code=${apiRegionCode}&date=${timelineState.date}&hour=${timelineState.hour}`
          } else if (timelineState.mode === 'future') {
            currentUrl = `${API_BASE}/v1/EnergySourcesForecastsHistory?regionCode=${apiRegionCode}&date=${timelineState.date}&hour=${timelineState.hour}`
          } else {
            backgroundLoadingRef.current = false
            return
          }
          
          // Fetch current hour in background
          fetch(currentUrl)
            .then(response => response.json())
            .then(result => {
              const currentParams = { ...params, hour: timelineState.hour }
              const currentCacheKey = getCacheKey(endpoint, currentParams)
              setCache(currentCacheKey, result)
              
              // Update UI with current hour data
              const dataArray = result.data || result
              if (Array.isArray(dataArray) && dataArray.length > 0) {
                const processedData = processEnergyData(dataArray[0])
                // Only update if we have valid data with non-zero total
                if (processedData.totalValue > 0) {
                  setData([...processedData.sources])  // Force new array reference
                  setTotal(processedData.totalValue)
                }
              } else if (typeof dataArray === 'object' && dataArray !== null && !Array.isArray(dataArray)) {
                // Handle single object format
                const processedData = processEnergyData(dataArray)
                if (processedData.totalValue > 0) {
                  setData([...processedData.sources])  // Force new array reference
                  setTotal(processedData.totalValue)
                }
              }
            })
            .catch(() => {}) // Silent background fetch error
            .finally(() => {
              backgroundLoadingRef.current = false
            })
        }
        
      } catch (err) {
        // Ignore abort errors
        if (err instanceof Error && err.name === 'AbortError') {
          return
        }
        setError(err instanceof Error ? err.message : 'Failed to fetch energy data')
        setLoading(false)
      }
    }

    fetchEnergyMix()

    // Cleanup: cancel the request if component unmounts or dependencies change
    return () => {
      abortController.abort()
    }
  }, [regionCode, timelineState?.mode, timelineState?.date, timelineState?.hour])

  return { data, total, loading, error, fallbackInfo }
}

export function useCarbonIntensityHistory(regionCode: string | undefined, timelineState?: TimelineState) {
  const [actual, setActual] = useState<CarbonIntensityData[]>([])
  const [forecast, setForecast] = useState<CarbonIntensityData[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fallbackInfo, setFallbackInfo] = useState<{ used: boolean; message?: string } | null>(null)
  const previousRegionRef = useRef<string | undefined>(undefined)
  const previousDateRef = useRef<string | undefined>(undefined)
  const lastDataRef = useRef<{ actual: CarbonIntensityData[], forecast: CarbonIntensityData[] }>({ actual: [], forecast: [] })

  useEffect(() => {
    if (!regionCode) {
      setActual([])
      setForecast([])
      return
    }

    // Clear cache when region changes
    if (previousRegionRef.current && previousRegionRef.current !== regionCode) {
      clearRegionCache(previousRegionRef.current)
    }
    previousRegionRef.current = regionCode

    // Detect if date changed for progressive loading
    const dateChanged = previousDateRef.current && previousDateRef.current !== timelineState?.date
    previousDateRef.current = timelineState?.date

    // Create AbortController for this request
    const abortController = new AbortController()

    const fetchCarbonHistory = async () => {
      setLoading(true)
      setError(null)
      
      try {
        const apiRegionCode = convertToApiRegionCode(regionCode)
        
        // Progressive loading: determine priority hour
        const priorityHour = dateChanged || isInitialLoad ? getPriorityHour(timelineState) : timelineState?.hour ?? getCurrentUtcHour()
        
        // First, fetch data for priority hour for immediate display
        let priorityActualUrl: string
        let priorityForecastUrl: string
        
        if (!timelineState || timelineState.mode === 'now') {
          // For 'now' mode, fetch current data
          priorityActualUrl = `${API_BASE}/v1/CarbonIntensity?region_code=${apiRegionCode}`
          priorityForecastUrl = `${API_BASE}/v1/CarbonIntensityForecasts?regionCode=${apiRegionCode}&forecastPeriod=1h`
        } else {
          // For historical/future modes, fetch specific hour first
          priorityActualUrl = `${API_BASE}/v1/CarbonIntensityHistory?region_code=${apiRegionCode}&date=${timelineState.date}&hour=${priorityHour}`
          priorityForecastUrl = `${API_BASE}/v1/CarbonIntensityForecastsHistory?region_code=${apiRegionCode}&date=${timelineState.date}&hour=${priorityHour}`
        }
        
        // Fetch priority hour data
        const [actualResponse, forecastResponse] = await Promise.all([
          fetch(priorityActualUrl, { signal: abortController.signal }),
          fetch(priorityForecastUrl, { signal: abortController.signal })
        ])
        
        // Process priority hour actual data
        if (actualResponse.ok) {
          const actualResult = await actualResponse.json()
          
          // Check for fallback metadata
          // Backend returns: overall_fallback, lifecycle_actual_date, direct_actual_date, requested_date
          if (actualResult.metadata?.overall_fallback) {
            const actualDate = actualResult.metadata.direct_actual_date || actualResult.metadata.lifecycle_actual_date
            setFallbackInfo({
              used: true,
              message: `Data from ${actualDate} (requested ${actualResult.metadata.requested_date})`
            })
          } else {
            setFallbackInfo(null)
          }
          
          if (actualResult.data && actualResult.data.length > 0) {
            // Initialize array with empty data for all 24 hours
            const actualData: CarbonIntensityData[] = Array.from({ length: 24 }, (_, i) => ({
              time: `${i}:00`,
              value: 0
            }))
            
            // Set priority hour data
            const hourData = actualResult.data[0]
            actualData[priorityHour] = {
              time: `${priorityHour}:00`,
              value: hourData.carbon_intensity_avg_direct || hourData.carbon_intensity_avg_lifecycle || 0
            }
            
            // Force new array reference for React to detect change
            if (JSON.stringify(actualData) !== JSON.stringify(lastDataRef.current.actual)) {
              setActual([...actualData])
              lastDataRef.current.actual = actualData
            }
            setLoading(false) // Stop loading after first data
          }
        }
        
        // Process priority hour forecast data
        if (forecastResponse.ok) {
          const forecastResult = await forecastResponse.json()
          
          if (forecastResult.data && forecastResult.data.length > 0) {
            // Initialize array with empty data for all 24 hours
            const forecastData: CarbonIntensityData[] = Array.from({ length: 24 }, (_, i) => ({
              time: `${i}:00`,
              value: 0
            }))
            
            // Set priority hour data
            const hourData = forecastResult.data[0]
            forecastData[priorityHour] = {
              time: `${priorityHour}:00`,
              value: hourData.forecasted_avg_carbon_intensity_direct || hourData.carbon_intensity_avg_direct || 0
            }
            
            // Force new array reference for React to detect change
            if (JSON.stringify(forecastData) !== JSON.stringify(lastDataRef.current.forecast)) {
              setForecast([...forecastData])
              lastDataRef.current.forecast = forecastData
            }
          }
        }
        
        // Now fetch remaining hours in background
        if (timelineState && timelineState.mode !== 'now') {
          // Fetch all 24 hours for the chart
          const fullActualUrl = `${API_BASE}/v1/CarbonIntensityHistory?region_code=${apiRegionCode}&date=${timelineState.date}`
          const fullForecastUrl = `${API_BASE}/v1/CarbonIntensityForecastsHistory?region_code=${apiRegionCode}&date=${timelineState.date}`
          
          Promise.all([
            fetch(fullActualUrl),
            fetch(fullForecastUrl)
          ]).then(async ([actualRes, forecastRes]) => {
            if (actualRes.ok) {
              const actualResult = await actualRes.json()
              if (actualResult.data && actualResult.data.length > 0) {
                const actualData: CarbonIntensityData[] = []
                for (let i = 0; i < Math.min(24, actualResult.data.length); i++) {
                  const hourData = actualResult.data[i]
                  actualData.push({
                    time: `${i}:00`,
                    value: hourData.carbon_intensity_avg_direct || hourData.carbon_intensity_avg_lifecycle || 0
                  })
                }
                // Force new array reference for React to detect change
                if (JSON.stringify(actualData) !== JSON.stringify(lastDataRef.current.actual)) {
                  setActual([...actualData])
                  lastDataRef.current.actual = actualData
                }
              }
            }
            
            if (forecastRes.ok) {
              const forecastResult = await forecastRes.json()
              if (forecastResult.data && forecastResult.data.length > 0) {
                const forecastData: CarbonIntensityData[] = forecastResult.data.slice(0, 24).map((item: Record<string, unknown>, index: number) => ({
                  time: `${index}:00`,
                  value: item.forecasted_avg_carbon_intensity_direct || item.carbon_intensity_avg_direct || 0
                }))
                // Force new array reference for React to detect change
                if (JSON.stringify(forecastData) !== JSON.stringify(lastDataRef.current.forecast)) {
                  setForecast([...forecastData])
                  lastDataRef.current.forecast = forecastData
                }
              }
            }
          }).catch(() => {}) // Silent background fetch error
        } else {
          // For 'now' mode, fetch full 24h forecast
          fetch(`${API_BASE}/v1/CarbonIntensityForecasts?regionCode=${apiRegionCode}&forecastPeriod=24h`)
            .then(async (res) => {
              if (res.ok) {
                const result = await res.json()
                if (result.data && result.data.length > 0) {
                  const forecastData: CarbonIntensityData[] = result.data.slice(0, 24).map((item: Record<string, unknown>, index: number) => ({
                    time: `${index}:00`,
                    value: item.forecasted_avg_carbon_intensity_direct || item.carbon_intensity_avg_direct || 0
                  }))
                  // Force new array reference for React to detect change
                  if (JSON.stringify(forecastData) !== JSON.stringify(lastDataRef.current.forecast)) {
                    setForecast([...forecastData])
                    lastDataRef.current.forecast = forecastData
                  }
                }
              }
            })
            .catch(() => {}) // Silent background fetch error
        }
        
      } catch (err) {
        // Ignore abort errors
        if (err instanceof Error && err.name === 'AbortError') {
          return
        }
        setError(err instanceof Error ? err.message : 'Failed to fetch carbon intensity data')
        setLoading(false)
      }
    }

    fetchCarbonHistory()

    // Cleanup: cancel the request if component unmounts or dependencies change
    return () => {
      abortController.abort()
    }
  }, [regionCode, timelineState?.mode, timelineState?.date, timelineState?.hour])

  return { actual, forecast, loading, error, fallbackInfo }
}

export function useCurrentCarbonIntensity(regionCode: string | undefined, timelineState?: TimelineState) {
  const [value, setValue] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fallbackInfo, setFallbackInfo] = useState<{ used: boolean; message?: string } | null>(null)
  const previousRegionRef = useRef<string | undefined>(undefined)
  const lastFetchRef = useRef<{ region: string; mode: string; date: string; hour: number } | null>(null)
  const lastValueRef = useRef<number | null>(null)

  useEffect(() => {
    if (!regionCode) {
      setValue(null)
      return
    }

    // Clear cache when region changes
    if (previousRegionRef.current && previousRegionRef.current !== regionCode) {
      clearRegionCache(previousRegionRef.current)
    }
    previousRegionRef.current = regionCode

    // Check if we need to fetch (params changed)
    const currentFetch = {
      region: regionCode,
      mode: timelineState?.mode || 'now',
      date: timelineState?.date || getCurrentUtcDate(),
      hour: timelineState?.hour ?? getCurrentUtcHour()
    }
    
    const shouldSkipFetch = lastFetchRef.current &&
      lastFetchRef.current.region === currentFetch.region &&
      lastFetchRef.current.mode === currentFetch.mode &&
      lastFetchRef.current.date === currentFetch.date &&
      lastFetchRef.current.hour === currentFetch.hour
    
    if (shouldSkipFetch) {
      return
    }
    
    lastFetchRef.current = currentFetch

    // Create AbortController for this request
    const abortController = new AbortController()

    const fetchCurrent = async () => {
      try {
        const apiRegionCode = convertToApiRegionCode(regionCode)
        
        // Build cache key
        let endpoint: string
        let params: Record<string, string | number>
        
        if (!timelineState || timelineState.mode === 'now') {
          endpoint = '/v1/CarbonIntensity'
          params = { region_code: apiRegionCode }
        } else if (timelineState.mode === 'past') {
          endpoint = '/v1/CarbonIntensityHistory'
          params = { region_code: apiRegionCode, date: timelineState.date, hour: timelineState.hour }
        } else {
          endpoint = '/v1/CarbonIntensityForecastsHistory'
          params = { region_code: apiRegionCode, date: timelineState.date, hour: timelineState.hour }
        }
        
        const cacheKey = getCacheKey(endpoint, params)
        
        // Check cache first
        const cachedResult = getFromCache(cacheKey)
        if (cachedResult) {
          const result = cachedResult.data || cachedResult
          const metadata = cachedResult.metadata
          
          // Check for fallback metadata
          // Backend returns: overall_fallback, lifecycle_actual_date, direct_actual_date, requested_date
          if (metadata?.overall_fallback) {
            const actualDate = metadata.direct_actual_date || metadata.lifecycle_actual_date
            setFallbackInfo({
              used: true,
              message: `Data from ${actualDate} (requested ${metadata.requested_date})`
            })
          } else {
            setFallbackInfo(null)
          }
          
          if (result.data && result.data.length > 0) {
            // API returns hour-specific data when hour param is provided
            const hourData = result.data[0]
            let intensityValue
            if (timelineState && timelineState.mode === 'future') {
              intensityValue = hourData.forecasted_avg_carbon_intensity_direct || hourData.carbon_intensity_avg_direct
            } else {
              intensityValue = hourData.carbon_intensity_avg_direct
            }
            // Only update if value actually changed
            if (intensityValue !== lastValueRef.current) {
              // Only update if value actually changed
              if (intensityValue !== lastValueRef.current) {
                setValue(intensityValue)
                lastValueRef.current = intensityValue
              }
              lastValueRef.current = intensityValue
            }
            setError(null)
          }
          return // Exit early, no need to fetch
        }
        
        // Not in cache, need to fetch
        setLoading(true)
        setError(null)
        
        let url: string
        if (!timelineState || timelineState.mode === 'now') {
          url = `${API_BASE}/v1/CarbonIntensity?region_code=${apiRegionCode}`
        } else if (timelineState.mode === 'past') {
          url = `${API_BASE}/v1/CarbonIntensityHistory?region_code=${apiRegionCode}&date=${timelineState.date}&hour=${timelineState.hour}`
        } else {
          url = `${API_BASE}/v1/CarbonIntensityForecastsHistory?region_code=${apiRegionCode}&date=${timelineState.date}&hour=${timelineState.hour}`
        }
        
        const response = await fetch(url, { signal: abortController.signal })
        
        if (!response.ok) {
          throw new Error('Failed to fetch carbon intensity')
        }
        
        const result = await response.json()
        
        // Cache the result with metadata
        setCache(cacheKey, result)
        
        // Check for fallback metadata
        // Backend returns: overall_fallback, lifecycle_actual_date, direct_actual_date, requested_date
        if (result.metadata?.overall_fallback) {
          const actualDate = result.metadata.direct_actual_date || result.metadata.lifecycle_actual_date
          setFallbackInfo({
            used: true,
            message: `Data from ${actualDate} (requested ${result.metadata.requested_date})`
          })
        } else {
          setFallbackInfo(null)
        }
        
        if (result.data && result.data.length > 0) {
          // API returns hour-specific data when hour param is provided
          const hourData = result.data[0]
          let intensityValue
          if (timelineState && timelineState.mode === 'future') {
            intensityValue = hourData.forecasted_avg_carbon_intensity_direct || hourData.carbon_intensity_avg_direct
          } else {
            intensityValue = hourData.carbon_intensity_avg_direct
          }
          setValue(intensityValue)
        }
      } catch (err) {
        // Ignore abort errors
        if (err instanceof Error && err.name === 'AbortError') {
          return
        }
        setError(err instanceof Error ? err.message : 'Failed to fetch data')
      } finally {
        setLoading(false)
      }
    }

    fetchCurrent()

    // Cleanup: cancel the request if component unmounts or dependencies change
    return () => {
      abortController.abort()
    }
  }, [regionCode, timelineState?.mode, timelineState?.date, timelineState?.hour]) // All dependencies included

  return { value, loading, error, fallbackInfo }
}

// Export a function to get carbon intensity from the same data source as the map
export function getCarbonIntensityFromCache(regionCode: string | undefined, timelineState?: TimelineState): number | null {
  if (!regionCode) return null
  
  const apiRegionCode = convertToApiRegionCode(regionCode)
  
  let endpoint: string
  let params: Record<string, string | number>
  
  if (!timelineState || timelineState.mode === 'now') {
    endpoint = '/v1/CarbonIntensity'
    params = { region_code: apiRegionCode }
  } else if (timelineState.mode === 'past') {
    endpoint = '/v1/CarbonIntensityHistory'
    params = { region_code: apiRegionCode, date: timelineState.date, hour: timelineState.hour }
  } else {
    endpoint = '/v1/CarbonIntensityForecastsHistory'
    params = { region_code: apiRegionCode, date: timelineState.date, hour: timelineState.hour }
  }
  
  const cacheKey = getCacheKey(endpoint, params)
  const cachedResult = getFromCache(cacheKey)
  
  if (cachedResult && cachedResult.data?.data?.length > 0) {
    const hourData = cachedResult.data.data[0]
    if (timelineState && timelineState.mode === 'future') {
      return hourData.forecasted_avg_carbon_intensity_direct || hourData.carbon_intensity_avg_direct || null
    } else {
      return hourData.carbon_intensity_avg_direct || null
    }
  }
  
  return null
}