import { useState, useEffect, useRef } from 'react'
import { getAdjacentDates as getAdjacentDatesUtil, getCurrentUtcDate, getCurrentUtcHour } from '../utils/dateUtils'
import { PerformanceLogger } from './performance-logger'
import { debugLogger } from '../utils/debugLogger'

export interface TimelineState {
  mode: 'past' | 'now' | 'future'
  date: string
  hour: number
}

// Feature flags to simplify behavior during debugging
const ENABLE_PREFETCH = true // Enable prefetching for smoother experience
const ENABLE_WARM_CACHE = false
// Removed DEBOUNCE_DELAY - not needed (no rate limits)

// Track if localStorage is available and working
let localStorageAvailable = true
let localStorageFailureCount = 0
const MAX_STORAGE_FAILURES = 3

// In-memory cache for ultra-fast access with LRU tracking
const memoryCache = new Map<string, { data: any; metadata?: any; timestamp: number; ttl: number; lastAccessed: number }>()

// Prevent multiple simultaneous requests for same data
const pendingRequests = new Map<string, Promise<any>>()

// CRITICAL: Global listener system for cache updates
// When any hook instance updates the cache, ALL hook instances are notified
// This ensures instant UI updates across all components sharing the same data
const cacheUpdateListeners: Array<(key: string) => void> = []

export const subscribeToCacheUpdates = (listener: (key: string) => void) => {
  cacheUpdateListeners.push(listener)
  return () => {
    const index = cacheUpdateListeners.indexOf(listener)
    if (index > -1) cacheUpdateListeners.splice(index, 1)
  }
}

const notifyCacheUpdate = (key: string) => {
  cacheUpdateListeners.forEach(listener => listener(key))
}

// Abort controllers for cancellable requests
const abortControllers = new Map<string, AbortController>()

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// Cache management functions
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const getCacheKey = (endpoint: string, params: Record<string, any>): string => {
  const sortedParams = Object.keys(params).sort().map(key => `${key}=${params[key]}`).join('&')
  return `${endpoint}?${sortedParams}`
}

// Export getCacheKey for direct cache access by components
export { getCacheKey }

// Version counter that increments every time cache is updated
// Components can watch this to know when to re-read from cache
let cacheVersion = 0
export const getCacheVersion = () => cacheVersion

// Different TTLs based on data type and freshness
const getTTL = (_endpoint: string, mode: string): number => {
  if (mode === 'now') return 5 * 60 * 1000        // 5 minutes for current data
  if (mode === 'past') return 7 * 24 * 60 * 60 * 1000 // 7 days for historical (it doesn't change)
  if (mode === 'future') return 60 * 60 * 1000    // 1 hour for forecasts
  
  return 3600000 // Default 1 hour
}

// Hybrid caching: memory first, then localStorage (if available)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const getFromCache = (key: string): any => {
  // Check memory cache first (fastest)
  const memoryData = memoryCache.get(key)
  if (memoryData && Date.now() - memoryData.timestamp < memoryData.ttl) {
    // Update last accessed time for LRU tracking
    memoryData.lastAccessed = Date.now()
    // CRITICAL: Properly handle arrays vs objects when cloning data
    let clonedData = memoryData.data
    if (memoryData.data) {
      if (Array.isArray(memoryData.data)) {
        // For arrays, use array spread to maintain array type
        clonedData = [...memoryData.data]
      } else if (typeof memoryData.data === 'object') {
        // For objects, use object spread
        clonedData = { ...memoryData.data }
      }
    }
    return {
      data: clonedData,
      metadata: memoryData.metadata ? { ...memoryData.metadata } : memoryData.metadata,
      _cacheHit: Date.now() // Move cache hit marker to top level to avoid data corruption
    }
  }

  // Fall back to localStorage only if it's available
  if (!localStorageAvailable) {
    return null
  }

  try {
    const cached = localStorage.getItem(key)
    if (cached) {
      // Try to decompress if it looks compressed
      const jsonStr = cached.includes('~rc') || cached.includes('~ci') ? decompressJSON(cached) : cached
      const { data, metadata, timestamp } = JSON.parse(jsonStr)
      if (Date.now() - timestamp < 3600000) {
        // Also store in memory for next time
        memoryCache.set(key, { data, metadata, timestamp, ttl: 3600000, lastAccessed: Date.now() })
        // CRITICAL: Properly handle arrays vs objects when cloning data
        let clonedData = data
        if (data) {
          if (Array.isArray(data)) {
            // For arrays, use array spread to maintain array type
            clonedData = [...data]
          } else if (typeof data === 'object') {
            // For objects, use object spread
            clonedData = { ...data }
          }
        }
        return {
          data: clonedData,
          metadata: metadata ? { ...metadata } : metadata,
          _cacheHit: Date.now() // Move cache hit marker to top level to avoid data corruption
        }
      }
    }
  } catch {
    // Remove corrupted entry
    try {
      localStorage.removeItem(key)
    } catch {}
  }
  return null
}

// Maximum cache size in bytes (4MB to be safe with 5MB localStorage limit)
const MAX_CACHE_SIZE = 4 * 1024 * 1024

// Maximum size for a single cache entry (500KB)
const MAX_ENTRY_SIZE = 500 * 1024

// Get approximate size of a string in bytes
const getByteSize = (str: string): number => {
  return new Blob([str]).size
}

// Simple compression using repeated string replacement (for JSON data)
const compressJSON = (data: string): string => {
  // Only compress if data is large enough
  if (data.length < 1000) return data
  
  // Common repeated strings in our JSON data
  const replacements = [
    ['region_code', '~rc'],
    ['carbon_intensity', '~ci'],
    ['UTC time', '~ut'],
    ['forecast_time', '~ft'],
    ['timestamp', '~ts'],
    ['metadata', '~md'],
    ['data', '~d'],
  ]
  
  let compressed = data
  for (const [search, replace] of replacements) {
    compressed = compressed.replace(new RegExp(search, 'g'), replace)
  }
  
  return compressed
}

// Decompress JSON data
const decompressJSON = (data: string): string => {
  const replacements = [
    ['~rc', 'region_code'],
    ['~ci', 'carbon_intensity'],
    ['~ut', 'UTC time'],
    ['~ft', 'forecast_time'],
    ['~ts', 'timestamp'],
    ['~md', 'metadata'],
    ['~d', 'data'],
  ]
  
  let decompressed = data
  for (const [search, replace] of replacements) {
    decompressed = decompressed.replace(new RegExp(search.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g'), replace)
  }
  
  return decompressed
}

// Get total localStorage size for our cache entries
const getTotalCacheSize = (): number => {
  let totalSize = 0
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith('/v1/')) {
      const item = localStorage.getItem(key)
      if (item) {
        totalSize += getByteSize(key) + getByteSize(item)
      }
    }
  }
  return totalSize
}

// Set cache in both memory and localStorage with size limits
const setCache = (key: string, result: any, ttl?: number): void => {
  const cacheTTL = ttl || 3600000
  
  // Extract data and metadata
  const data = result.data || result
  const metadata = result.metadata
  
  // Always store in memory cache (with smart LRU eviction)
  if (memoryCache.size > 100) {
    // Remove least recently used entries, but keep frequently accessed ones
    const entriesToRemove = Array.from(memoryCache.entries())
      .sort((a, b) => {
        // Sort by last accessed time (LRU)
        const aScore = a[1].lastAccessed || a[1].timestamp
        const bScore = b[1].lastAccessed || b[1].timestamp
        return aScore - bScore
      })
      .slice(0, 20)
    entriesToRemove.forEach(([k]) => memoryCache.delete(k))
  }
  
  memoryCache.set(key, {
    data,
    metadata,
    timestamp: Date.now(),
    ttl: cacheTTL,
    lastAccessed: Date.now()
  })
  
  // Increment version to signal all hooks to re-read from cache
  cacheVersion++
  
  // Notify listeners immediately so they can re-read from the updated cache
  notifyCacheUpdate(key)

  // Only try localStorage if it's available
  if (!localStorageAvailable) {
    return
  }

  // Store in localStorage with quota management
  try {
    const dataObj = {
      data,
      metadata,
      timestamp: Date.now()
    }
    
    let dataStr = JSON.stringify(dataObj)
    
    // Skip if entry is too large
    if (getByteSize(dataStr) > MAX_ENTRY_SIZE) {
      return
    }
    
    // Try compression for larger entries
    if (dataStr.length > 5000) {
      const compressed = compressJSON(dataStr)
      if (compressed.length < dataStr.length * 0.9) {
        dataStr = compressed
      }
    }
    
    // Check if adding this would exceed our limit
    const currentSize = getTotalCacheSize()
    const newItemSize = getByteSize(key) + getByteSize(dataStr)
    
    if (currentSize + newItemSize > MAX_CACHE_SIZE) {
      clearOldCacheEntries(true) // Force aggressive cleanup
      
      // Re-check size after cleanup
      const newSize = getTotalCacheSize()
      if (newSize + newItemSize > MAX_CACHE_SIZE) {
        return
      }
    }
    
    localStorage.setItem(key, dataStr)
    
    // Reset failure count on success
    localStorageFailureCount = 0
    
    // CRITICAL: Notify all listeners that cache was updated
    // This triggers re-renders in ALL hook instances sharing this data
    notifyCacheUpdate(key)
    
  } catch (e: any) {
    localStorageFailureCount++
    
    if (e.name === 'QuotaExceededError') {
      // Try aggressive cleanup
      clearOldCacheEntries(true)
      
      // Try one more time with a smaller dataset
      try {
        const minimalData = {
          data,
          metadata,
          timestamp: Date.now()
        }
        const minimalStr = compressJSON(JSON.stringify(minimalData))
        
        if (getByteSize(minimalStr) < MAX_ENTRY_SIZE / 2) {
          localStorage.setItem(key, minimalStr)
          localStorageFailureCount = 0
        } else {
          throw new Error('Data still too large')
        }
      } catch {
        // If we've failed too many times, disable localStorage
        if (localStorageFailureCount >= MAX_STORAGE_FAILURES) {
          localStorageAvailable = false
        }
      }
    } else {
      // Disable localStorage after too many failures
      if (localStorageFailureCount >= MAX_STORAGE_FAILURES) {
        localStorageAvailable = false
      }
    }
  }
}

// Get adjacent dates for prefetching - using timezone-neutral utility
const getAdjacentDates = getAdjacentDatesUtil

// Background fetch and cache
const fetchAndCache = async (endpoint: string, params: Record<string, any>, key: string, mode: string): Promise<void> => {
  try {
    const url = new URL(`${API_BASE}${endpoint}`)
    Object.entries(params).forEach(([k, v]) => url.searchParams.append(k, v.toString()))
    
    const response = await fetch(url.toString())
    if (response.ok) {
      const result = await response.json()
      const ttl = getTTL(endpoint, mode)
      setCache(key, { data: result.data, metadata: result.metadata }, ttl)
    }
  } catch {
    // Silent fail for prefetch
  }
}

// Prefetch adjacent time periods
const prefetchAdjacentData = async (endpoint: string, currentParams: Record<string, any>, mode: string) => {
  if (!ENABLE_PREFETCH) return
  if (mode === 'now') return // No prefetching for current data
  
  const adjacentHours = [-1, 1] // Previous and next hour
  const adjacentDates = getAdjacentDates(currentParams.date)
  
  // Prefetch adjacent hours
  for (const hour of adjacentHours) {
    const params = { ...currentParams, hour: currentParams.hour + hour }
    if (params.hour >= 0 && params.hour < 24) {
      const key = getCacheKey(endpoint, params)
      if (!memoryCache.has(key)) {
        // Prefetch in background
        fetchAndCache(endpoint, params, key, mode).catch(() => {})
      }
    }
  }
  
  // Prefetch adjacent dates
  for (const date of adjacentDates) {
    const params = { ...currentParams, date }
    const key = getCacheKey(endpoint, params)
    if (!memoryCache.has(key)) {
      // Prefetch in background
      fetchAndCache(endpoint, params, key, mode).catch(() => {})
    }
  }
}

// Fetch with deduplication and cancellation
const fetchWithDeduplication = async (endpoint: string, params: Record<string, any>, mode: string): Promise<any> => {
  const key = getCacheKey(endpoint, params)
  
  // If request is already pending, wait for it
  if (pendingRequests.has(key)) {
    return pendingRequests.get(key)
  }
  
  // Cancel any previous request for this endpoint (but different params)
  const endpointKey = endpoint
  const existingController = abortControllers.get(endpointKey)
  if (existingController) {
    existingController.abort()
    abortControllers.delete(endpointKey)
  }
  
  // Create new abort controller
  const abortController = new AbortController()
  abortControllers.set(endpointKey, abortController)
  
  // Create new request
  const request = fetchData(endpoint, params, mode, abortController.signal)
  pendingRequests.set(key, request)
  
  try {
    const result = await request
    return result
  } catch (err: any) {
    throw err
  } finally {
    pendingRequests.delete(key)
    if (abortControllers.get(endpointKey) === abortController) {
      abortControllers.delete(endpointKey)
    }
  }
}

// Main fetch function with abort signal
const fetchData = async (endpoint: string, params: Record<string, any>, mode: string, signal?: AbortSignal): Promise<any> => {
  const url = new URL(`${API_BASE}${endpoint}`)
  Object.entries(params).forEach(([key, value]) => {
    url.searchParams.append(key, value.toString())
  })

  const response = await fetch(url.toString(), { signal })
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`)
  }

  const result = await response.json()
  
  // NORMALIZE: The API returns fallback_metadata at root level, normalize it to metadata
  // API returns: fallback_metadata.lifecycle_fallback, fallback_metadata.direct_fallback
  // UI expects: metadata.overall_fallback
  let normalizedResult = result
  if (result?.fallback_metadata) {
    const fm = result.fallback_metadata
    const overall_fallback = fm.lifecycle_fallback || fm.direct_fallback
    normalizedResult = {
      ...result,
      metadata: {
        ...(result.metadata || {}),
        overall_fallback,
        lifecycle_fallback: fm.lifecycle_fallback,
        direct_fallback: fm.direct_fallback,
        lifecycle_actual_date: fm.lifecycle_actual_date,
        direct_actual_date: fm.direct_actual_date,
        requested_date: fm.requested_date,
        message: fm.message
      }
    }
  }
  
  const ttl = getTTL(endpoint, mode)
  setCache(getCacheKey(endpoint, params), normalizedResult, ttl)
  return normalizedResult
}

// Cache warming on app startup
export const warmCache = async () => {
  if (!ENABLE_WARM_CACHE) return
  // UTC clock: the API filters date+hour in UTC
  const currentHour = getCurrentUtcHour()
  const currentDate = getCurrentUtcDate()
  
  // Prefetch current data and adjacent hours
  const endpoints = ['/v1/CarbonIntensity', '/v1/EnergySources']
  
  for (const endpoint of endpoints) {
    // Current hour
    const currentParams = { date: currentDate, hour: currentHour }
    const currentKey = getCacheKey(endpoint, currentParams)
    if (!memoryCache.has(currentKey)) {
      fetchAndCache(endpoint, currentParams, currentKey, 'now').catch(() => {})
    }
    
    // Adjacent hours
    for (let hour = Math.max(0, currentHour - 1); hour <= Math.min(23, currentHour + 1); hour++) {
      if (hour !== currentHour) {
        const params = { date: currentDate, hour }
        const key = getCacheKey(endpoint, params)
        if (!memoryCache.has(key)) {
          fetchAndCache(endpoint, params, key, 'past').catch(() => {})
        }
      }
    }
  }
}

// Cache for full day data - stores all 24 hours for a date
const fullDayCache = new Map<string, { data: any; timestamp: number }>()

// Memoization cache for filtered hour data
const filteredHourCache = new Map<string, any>()

// Helper function to filter full day data for a specific hour - with memoization
function filterDataForHour(fullDayData: any, targetHour: number, date?: string): any {
  PerformanceLogger.startTimer(`filter_hour_${targetHour}_${date || 'unknown'}`)
  if (!fullDayData?.data || !Array.isArray(fullDayData.data)) {
    return fullDayData
  }
  
  // Extract date from first data item if not provided
  const dataDate = date || (fullDayData.data[0]?.['UTC time']?.split('T')[0]) || 'unknown'
  
  // Create a cache key that INCLUDES THE DATE to prevent cross-date cache pollution
  const cacheKey = `${dataDate}-${targetHour}-${fullDayData.data.length}-${fullDayData.data[0]?.region_code || ''}`
  
  // Check if we've already filtered this exact data for this hour
  const cached = filteredHourCache.get(cacheKey)
  if (cached) {
    return cached
  }
  
  // Count unique dates in the data
  const uniqueDates = new Set()
  const uniqueRegions = new Set()
  
  // For forecast data, there might be multiple forecast periods per region
  // We need to handle this differently
  const seenRegions = new Set<string>()
  const filteredData: any[] = []
  
  fullDayData.data.forEach((item: any) => {
    // Track unique regions
    if (item.region_code) {
      uniqueRegions.add(item.region_code)
    }
    
    // Try different time field formats
    const timeFields = ['UTC time', 'hour', 'UTC_time', 'utc_hour', 'time', 'forecast_time']
    
    for (const field of timeFields) {
      if (item[field] !== undefined) {
        let hour: number | null = null
        const timeValue = item[field]
        
        if (typeof timeValue === 'string') {
          // Handle ISO datetime like "2023-09-13T00:00:00Z"
          if (timeValue.includes('T')) {
            const [datePart, timePart] = timeValue.split('T')
            uniqueDates.add(datePart)
            const hourStr = timePart.split(':')[0]
            hour = parseInt(hourStr)
          }
          // Handle datetime string like "2023-09-13 00:00:00"
          else if (timeValue.includes(' ')) {
            const [datePart, timePart] = timeValue.split(' ')
            uniqueDates.add(datePart)
            if (timePart) {
              const hourStr = timePart.split(':')[0]
              hour = parseInt(hourStr)
            }
          } else if (timeValue.includes(':')) {
            const hourStr = timeValue.split(':')[0]
            hour = parseInt(hourStr)
          } else {
            hour = parseInt(timeValue)
          }
        } else if (typeof timeValue === 'number') {
          hour = timeValue
        }
        
        if (hour !== null && !isNaN(hour) && hour === targetHour) {
          // For forecast data, only keep one entry per region (deduplicate)
          const regionCode = item.region_code || item.region
          if (regionCode) {
            if (!seenRegions.has(regionCode)) {
              seenRegions.add(regionCode)
              filteredData.push(item)
            }
          } else {
            // If no region code, include it anyway
            filteredData.push(item)
          }
          break // Found the hour, no need to check other time fields
        }
      }
    }
  })
  
  // CRITICAL: Preserve API's fallback metadata if it exists
  // The API provides accurate lifecycle_actual_date and direct_actual_date
  // We should NOT overwrite these with synthesized dates from data scanning
  let metadata = fullDayData.metadata ? { ...fullDayData.metadata } : {}
  
  // Check if data spans multiple dates (indicates fallback occurred)
  // But ONLY synthesize metadata if the API didn't already provide it
  const uniqueDateArray = Array.from(uniqueDates) as string[]
  const apiAlreadyProvidedFallbackInfo = metadata.lifecycle_actual_date || metadata.direct_actual_date || metadata.overall_fallback
  
  if (uniqueDateArray.length > 1 && !apiAlreadyProvidedFallbackInfo) {
    // Find the fallback date (the date that's NOT the requested date)
    const requestedDate = dataDate
    const fallbackDates = uniqueDateArray.filter(d => d !== requestedDate)
    
    if (fallbackDates.length > 0) {
      // Count how many items are from fallback dates
      let fallbackCount = 0
      for (const item of filteredData) {
        const itemDate = item['UTC time']?.split(/[T\s]/)[0]
        if (itemDate && itemDate !== requestedDate) {
          fallbackCount++
        }
      }
      
      if (fallbackCount > 0) {
        // Synthesize fallback metadata for the UI ONLY if API didn't provide it
        metadata = {
          ...metadata,
          overall_fallback: true,
          lifecycle_fallback: true,
          direct_fallback: true,
          lifecycle_actual_date: fallbackDates[0],
          direct_actual_date: fallbackDates[0],
          requested_date: requestedDate,
          _fallbackCount: fallbackCount,
          _totalCount: filteredData.length,
          _detectedBy: 'filterDataForHour_synthesized'
        }
      }
    }
  }
  
  const result = {
    ...fullDayData,
    data: filteredData,
    metadata, // Include synthesized metadata with fallback info
    _filteredDate: dataDate,  // Track which date this data is from
    _filteredHour: targetHour  // Track which hour this was filtered for
  }
  
  // Cache the result - limit cache size
  if (filteredHourCache.size > 50) {
    // Remove oldest entries
    const keysToDelete = Array.from(filteredHourCache.keys()).slice(0, 10)
    keysToDelete.forEach(key => filteredHourCache.delete(key))
  }
  filteredHourCache.set(cacheKey, result)
  
  PerformanceLogger.endTimer(`filter_hour_${targetHour}_${date || 'unknown'}`)
  return result
}

// Carbon Intensity Data Hook - with progressive loading
export const useCarbonIntensityData = (timelineState: TimelineState) => {
  const [data, setData] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [backgroundLoading, setBackgroundLoading] = useState(false)
  // Track loading progress (0-100)
  const [loadingProgress, setLoadingProgress] = useState<number>(0)
  // CRITICAL FIX: Track data updates with a separate state to ensure consumers detect changes
  // This state is updated whenever setData() is called, providing a reliable signal for re-renders
  const [dataUpdateId, setDataUpdateId] = useState<number>(() => Date.now())
  // Track cache version to re-read when cache is updated by another hook instance
  const [, setLastCacheVersion] = useState(cacheVersion)
  
  // CRITICAL: Subscribe to cache updates and re-read from cache when updated
  // This ensures this hook instance sees data from other hook instances
  useEffect(() => {
    const handleCacheUpdate = (key: string) => {
      // Check if this update is relevant to our current request
      const endpoint = timelineState.mode === 'past'
        ? '/v1/CarbonIntensityHistory'
        : timelineState.mode === 'future'
          ? '/v1/CarbonIntensityForecastsHistory'
          : '/v1/CarbonIntensity'
      
      // If the cache update is for data we care about, re-read from cache
      if (key.includes(endpoint) && key.includes(timelineState.date)) {
        // Re-read from cache
        const hourParams = { region_code: 'all', date: timelineState.date, hour: timelineState.hour }
        const cacheKey = getCacheKey(endpoint, hourParams)
        const cachedData = getFromCache(cacheKey)
        
        if (cachedData && cachedData.data) {
          const updateTime = Date.now()
          const newData = {
            data: Array.isArray(cachedData.data) ? [...cachedData.data] : cachedData.data,
            metadata: cachedData.metadata ? { ...cachedData.metadata } : cachedData.metadata,
            _updateId: updateTime,
            _fromCacheReRead: true,
            _date: timelineState.date,
            _hour: timelineState.hour
          }
          setData(newData)
          setDataUpdateId(updateTime)
          setLoading(false)
        }
      }
      
      // Update our tracked cache version
      setLastCacheVersion(cacheVersion)
    }
    
    const unsubscribe = subscribeToCacheUpdates(handleCacheUpdate)
    return unsubscribe
  }, [timelineState.date, timelineState.hour, timelineState.mode])
  const currentDayDataRef = useRef<{ date: string; mode: string; data: any; metadata?: any } | null>(null)
  // Track the CURRENT date being viewed - used to prevent stale background fetches from overwriting fresh data
  const currentDateRef = useRef<string>(timelineState.date)
  // Track the PREVIOUS date - used to detect date changes while panel is open
  const previousDateRef = useRef<string>(timelineState.date)
  // Store fallback metadata separately so it persists across state updates
  const fallbackMetadataRef = useRef<{
    overall_fallback?: boolean
    lifecycle_fallback?: boolean
    direct_fallback?: boolean
    lifecycle_actual_date?: string
    direct_actual_date?: string
    requested_date?: string
    message?: string
  } | null>(null)
  // Track when date/mode effect is handling a new date fetch - hour effect should skip in this case
  const dateChangeFetchingRef = useRef<string | null>(null)
  

  // Effect for fetching data when date or mode changes
  useEffect(() => {
    // CRITICAL DATE CHANGE DETECTION
    previousDateRef.current = timelineState.date
    
    // CRITICAL: Clear fallback metadata ref when date changes
    // This prevents stale metadata (with old requested_date) from polluting new requests
    fallbackMetadataRef.current = null
    
    // Update the currentDateRef so background fetch completion handlers know the current date
    currentDateRef.current = timelineState.date
    
    // CRITICAL: Mark that we're handling a date fetch - hour effect should NOT overwrite our data
    // This prevents hour effect from reading stale cache and overwriting fresh priority fetch data
    dateChangeFetchingRef.current = timelineState.date
    
    const fetchData = async () => {
      try {
        if (timelineState.mode === 'now') {
          // For "now" mode, fetch current data without hour parameter
          const endpoint = '/v1/CarbonIntensity'
          const params = { region_code: 'all' }
          const cacheKey = getCacheKey(endpoint, params)
          
          // Check cache
          const cachedResult = getFromCache(cacheKey)
          if (cachedResult) {
            // CRITICAL: Force new object reference with unique ID for React to detect change
            const updateTime = Date.now()
            const newData = {
              data: cachedResult.data ? [...cachedResult.data] : cachedResult.data,
              metadata: cachedResult.metadata ? { ...cachedResult.metadata } : cachedResult.metadata,
              _updateId: updateTime,
              _fromCache: true,
              _date: timelineState.date,
              _hour: timelineState.hour
            }
            setData(newData)
            setDataUpdateId(updateTime)
            setError(null)
            setLoading(false) // Ensure loading is set to false
            // CRITICAL FIX: Clear the date fetching flag so hour effect can run
            dateChangeFetchingRef.current = null
            return
          }
          
          // Fetch new data
          setLoading(true)
          setError(null)
          const result = await fetchWithDeduplication(endpoint, params, timelineState.mode)
          // Force new object reference for React to detect change
          const updateTime = Date.now()
          const newData = {
            data: result.data ? [...result.data] : result.data,
            metadata: result.metadata ? { ...result.metadata } : result.metadata,
            _updateId: updateTime,
            _date: timelineState.date,
            _hour: timelineState.hour
          }
          setData(newData)
          setDataUpdateId(updateTime)
          setError(null)
          setLoading(false) // Ensure loading is set to false
        } else {
          // For past/future modes, implement progressive loading
          const dateStr = timelineState.date
          const endpoint = timelineState.mode === 'past'
            ? '/v1/CarbonIntensityHistory'
            : '/v1/CarbonIntensityForecastsHistory'
          
          // Create a cache key for the full day (without hour parameter)
          const dayKey = `${endpoint}-${dateStr}-fullday`
          
          // Check if we already have all data for this day in cache
          const fullDayData = fullDayCache.get(dayKey)
          const now = Date.now()
          
          if (fullDayData && (now - fullDayData.timestamp < 7 * 24 * 60 * 60 * 1000)) {
            // We have cached data for this day - store it and filter for the specific hour
            const fullData = fullDayData.data
            
            // IMPORTANT: Validate that the cached data is actually for the requested date
            if (fullData.metadata?.actual_date && fullData.metadata.actual_date !== dateStr) {
              fullDayCache.delete(dayKey)
            } else {
              // INSTANT return for cached data - no loading animation needed
              currentDayDataRef.current = { date: dateStr, mode: timelineState.mode, data: fullData.data, metadata: fullData.metadata }
              const hourData = filterDataForHour(fullData, timelineState.hour, dateStr)
              debugLogger.log('CACHE', `Returning filtered data for ${dateStr} hour ${timelineState.hour}`)
              debugLogger.log('STATE UPDATE', 'Setting data from full day cache', {
                filteredHourDataLength: hourData.data?.length
              })
              debugLogger.log('REF UPDATE', `Updated currentDayDataRef with ${fullData.data?.length} items for ${dateStr}`)
              // Force new object reference for React to detect change
              // CRITICAL: Use hourData.metadata which may contain synthesized fallback info
              // from filterDataForHour when mixed dates are detected
              const updateTime = Date.now()
              const newData = {
                data: hourData.data ? [...hourData.data] : hourData.data,
                metadata: hourData.metadata ? { ...hourData.metadata } : hourData.metadata,
                _updateId: updateTime,
                _date: dateStr,
                _hour: timelineState.hour,
                _fromCache: true
              }
              setData(newData)
              setDataUpdateId(updateTime)
              setError(null)
              setLoading(false)
              setBackgroundLoading(false) // Ensure no loading state for cached data
              
              // CRITICAL FIX: Clear the date fetching flag so hour effect can run
              dateChangeFetchingRef.current = null
              return
            }
          }
          
          // PROGRESSIVE LOADING: First check ALL cache locations for current hour
          // This ensures instant update when date changes
          PerformanceLogger.startTimer(`priority_hour_fetch_${dateStr}_${timelineState.hour}`)
          
          // ALWAYS check with region_code: 'all' to get ALL regions
          const hourParams = { region_code: 'all', date: dateStr, hour: timelineState.hour }
          const hourCacheKey = getCacheKey(endpoint, hourParams)
          
          // Enhanced cache checking - check multiple cache locations
          let cachedHourResult = getFromCache(hourCacheKey)
          
          // If not in primary cache, check if we have it from a previous full day fetch
          if (!cachedHourResult || !cachedHourResult.data) {
            // Check if this hour was cached individually from a previous session
            const alternativeKeys = [
              getCacheKey(endpoint, { date: dateStr, hour: timelineState.hour, region_code: 'all' }),
              getCacheKey(endpoint, { date: dateStr, hour: timelineState.hour }),
            ]
            
            for (const altKey of alternativeKeys) {
              const altResult = getFromCache(altKey)
              if (altResult && altResult.data) {
                cachedHourResult = altResult
                break
              }
            }
          }
          
          // Check if we have valid cached data
          let shouldUseCachedData = false
          if (cachedHourResult && cachedHourResult.data) {
            // Validate the cached data is for the correct date
            if (cachedHourResult.metadata?.actual_date && cachedHourResult.metadata.actual_date !== dateStr) {
              // Cache has wrong date - skip
            } else {
              shouldUseCachedData = true
            }
          }
          
          if (shouldUseCachedData) {
            // INSTANT return for cached data - no loading animation needed
            const cacheUpdateTime = Date.now()
            const dataLength = Array.isArray(cachedHourResult.data) ? cachedHourResult.data.length :
                              cachedHourResult.data ? 1 : 0;
            debugLogger.log('STATE UPDATE', 'Setting data from hour cache', { dataLength })
            
            // CRITICAL: Ensure we're setting ALL regions data
            if (Array.isArray(cachedHourResult.data)) {
              // Store ALL regions in currentDayDataRef for hour effect
              currentDayDataRef.current = {
                date: dateStr,
                mode: timelineState.mode,
                data: cachedHourResult.data, // All 58 regions
                metadata: cachedHourResult.metadata
              }
              debugLogger.log('REF UPDATE', `Updated currentDayDataRef from cache with ${cachedHourResult.data.length} items`)
            }
            
            const newData = {
              data: Array.isArray(cachedHourResult.data) ? [...cachedHourResult.data] : cachedHourResult.data,
              metadata: cachedHourResult.metadata ? { ...cachedHourResult.metadata } : cachedHourResult.metadata,
              _updateId: cacheUpdateTime,
              _fromCache: true,
              _date: dateStr,
              _hour: timelineState.hour,
              _instant: true // Mark cached data as instant too
            }
            setData(newData)
            setDataUpdateId(cacheUpdateTime)
            setError(null)
            setLoading(false)
            setBackgroundLoading(false) // Ensure no loading state for cached data
            
            // CRITICAL FIX: Clear the date fetching flag so hour effect can run
            dateChangeFetchingRef.current = null
            
            // End the timer since we found cached data
            PerformanceLogger.endTimer(`priority_hour_fetch_${dateStr}_${timelineState.hour}`)
            
            // Start background fetch for remaining hours (but skip if we already have full day)
            if (!fullDayCache.has(dayKey)) {
              // Continue with background fetch below
            } else {
              return // We have everything we need
            }
          }
          
          // If not cached, IMMEDIATELY fetch current hour with high priority
          if (!shouldUseCachedData) {
            // Don't set loading to true here - we want to keep showing the last value
            // Only show loading if we have no data at all
            if (!data) {
              setLoading(true)
            }
            setError(null)
            
            // Create AbortController for this priority request
            const priorityController = new AbortController()
            
            try {
              PerformanceLogger.startTimer(`priority_hour_network_${dateStr}_${timelineState.hour}`)
              // CRITICAL FIX: Always fetch ALL regions for the hour, not just one
              const fullHourParams = { region_code: 'all', date: dateStr, hour: timelineState.hour }
              const url = new URL(`${API_BASE}${endpoint}`)
              Object.entries(fullHourParams).forEach(([key, value]) => {
                url.searchParams.append(key, value.toString())
              })
              
              // PRIORITY FETCH - with timeout to ensure fast response
              const fetchPromise = fetch(url.toString(), {
                signal: priorityController.signal
                // Removed X-Priority header due to CORS issues
              })
              
              // Add timeout for priority fetch (2 seconds max)
              const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => {
                  priorityController.abort()
                  reject(new Error('Priority fetch timeout'))
                }, 2000)
              })
              
              const response = await Promise.race([fetchPromise, timeoutPromise]) as Response
              
              if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`)
              }
              
              let hourResult = await response.json()
              
              // NORMALIZE: The API returns fallback_metadata at root level, normalize it to metadata
              // API returns: fallback_metadata.lifecycle_fallback, fallback_metadata.direct_fallback
              // UI expects: metadata.overall_fallback
              if (hourResult?.fallback_metadata) {
                const fm = hourResult.fallback_metadata
                const overall_fallback = fm.lifecycle_fallback || fm.direct_fallback
                hourResult = {
                  ...hourResult,
                  metadata: {
                    ...(hourResult.metadata || {}),
                    overall_fallback,
                    lifecycle_fallback: fm.lifecycle_fallback,
                    direct_fallback: fm.direct_fallback,
                    lifecycle_actual_date: fm.lifecycle_actual_date,
                    direct_actual_date: fm.direct_actual_date,
                    requested_date: fm.requested_date,
                    message: fm.message
                  }
                }
              }
              
              PerformanceLogger.endTimer(`priority_hour_network_${dateStr}_${timelineState.hour}`)
              PerformanceLogger.endTimer(`priority_hour_fetch_${dateStr}_${timelineState.hour}`)
              
              // EARLY FALLBACK DETECTION: Scan priority fetch data for fallback dates
              // This allows the banner to show immediately (within ~1 second) instead of
              // waiting for the full background fetch to complete (~8-10 seconds)
              if (hourResult.data && Array.isArray(hourResult.data) && !hourResult.metadata?.overall_fallback) {
                const requestedDate = dateStr // e.g., "2023-06-26"
                const uniqueDates = new Set<string>()
                
                hourResult.data.forEach((item: any) => {
                  const itemDate = item['UTC time']?.split('T')[0]
                  if (itemDate) uniqueDates.add(itemDate)
                })
                
                // If we see a different date, it's likely fallback data
                const otherDates = [...uniqueDates].filter(d => d !== requestedDate)
                if (otherDates.length > 0) {
                  const fallbackDate = otherDates[0] // e.g., "2023-01-03"
                  
                  // Update the fallbackMetadataRef immediately so banner shows fast
                  fallbackMetadataRef.current = {
                    requested_date: requestedDate,
                    lifecycle_actual_date: fallbackDate,
                    direct_actual_date: fallbackDate,
                    overall_fallback: true,
                    lifecycle_fallback: true,
                    direct_fallback: true,
                    message: `Data unavailable for ${requestedDate}, showing ${fallbackDate} instead`
                  }
                  
                  // Also update hourResult.metadata so setData includes it
                  hourResult = {
                    ...hourResult,
                    metadata: {
                      ...(hourResult.metadata || {}),
                      ...fallbackMetadataRef.current
                    }
                  }
                }
              }
              
              // Count unique regions to verify we have all data
              if (hourResult.data && Array.isArray(hourResult.data)) {
                const regions = new Set(hourResult.data.map((item: Record<string, unknown>) => item.region_code))
                PerformanceLogger.increment('unique_regions_hour', regions.size)
                
                // CRITICAL: Store ALL regions data in currentDayDataRef
                currentDayDataRef.current = {
                  date: dateStr,
                  mode: timelineState.mode,
                  data: hourResult.data, // This should have ALL 58 regions
                  metadata: hourResult.metadata
                }
                debugLogger.log('REF UPDATE', `Immediately updated currentDayDataRef for ${dateStr} with ${hourResult.data.length} items (all regions)`)
              }
              
              // IMMEDIATELY update the UI with current hour data
              const updateTime = Date.now()
              debugLogger.log('STATE UPDATE', 'Setting data from priority fetch', {
                dataLength: Array.isArray(hourResult.data) ? hourResult.data.length :
                           hourResult.data ? 1 : 0
              })
              debugLogger.log('PRIORITY', `State update called with ${Array.isArray(hourResult.data) ? hourResult.data.length : 'non-array'} items`)
              // Force new object reference for React to detect change
              // Handle both array and non-array data structures
              let dataToSet;
              if (Array.isArray(hourResult.data)) {
                dataToSet = [...hourResult.data];
              } else {
                dataToSet = hourResult.data;
              }
              
              const newData = {
                data: dataToSet,
                metadata: hourResult.metadata ? { ...hourResult.metadata } : hourResult.metadata,
                _updateId: updateTime, // Use same timestamp for tracking
                _date: dateStr,
                _hour: timelineState.hour,
                _instant: true // Mark this as an instant update
              }
              
              // CRITICAL: Store fallback metadata in ref so it persists across state updates
              if (hourResult.metadata?.overall_fallback) {
                fallbackMetadataRef.current = hourResult.metadata
              }
              
              // CRITICAL: This is where setData + setDataUpdateId are called for NEW DATE priority fetch
              setData(newData)
              setDataUpdateId(updateTime)
              setError(null)
              setLoading(false)
              // Clear the date fetching flag - our data is now set
              dateChangeFetchingRef.current = null
              
              // Cache the hour data ONLY with the full region_code=all key
              const ttl = getTTL(endpoint, timelineState.mode)
              const fullHourCacheKey = getCacheKey(endpoint, { region_code: 'all', date: dateStr, hour: timelineState.hour })
              setCache(fullHourCacheKey, hourResult, ttl)
            } catch (err) {
              setError(err instanceof Error ? err.message : 'Unknown error')
              setLoading(false)
              
              // CRITICAL FIX: Clear the date fetching flag on error so HOUR EFFECT can run
              // when background fetch completes
              dateChangeFetchingRef.current = null
              
              // If priority fetch fails, still try background fetch
            }
          }
          
          // BACKGROUND LOADING: Fetch remaining hours in background
          // Start progress simulation - this runs for both new fetches AND joining existing requests
          setBackgroundLoading(true)
          setLoadingProgress(0) // Reset progress
          
          // Start simulated progress updates
          // Since we can't track actual network progress easily, we simulate it
          // Progress goes from 0-90% during fetch, then jumps to 100% on completion
          let simulatedProgress = 0
          const progressInterval = setInterval(() => {
            // Gradually increase progress, slowing down as it approaches 90%
            const remaining = 90 - simulatedProgress
            const increment = Math.max(1, remaining * 0.08) // 8% of remaining
            simulatedProgress = Math.min(90, simulatedProgress + increment)
            setLoadingProgress(Math.round(simulatedProgress))
          }, 200) // Update every 200ms
          
          // Helper to cleanup progress simulation
          const cleanupProgress = (success: boolean) => {
            clearInterval(progressInterval)
            if (success) {
              setLoadingProgress(100)
              // Slight delay before hiding loading to show 100% briefly
              setTimeout(() => {
                setBackgroundLoading(false)
                setLoadingProgress(0) // Reset for next time
              }, 300)
            } else {
              setLoadingProgress(0)
              setBackgroundLoading(false)
            }
          }
          
          // Check if there's already a pending request for this day
          const pendingKey = `${endpoint}-${dateStr}-pending`
          if (pendingRequests.has(pendingKey)) {
            try {
              const result = await pendingRequests.get(pendingKey)
              fullDayCache.set(dayKey, { data: result, timestamp: now })
              // CRITICAL: Update currentDayDataRef with ALL regions data
              if (result?.data && Array.isArray(result.data)) {
                // CRITICAL FIX: Run filterDataForHour to get synthesized metadata
                // This ensures metadata has fallback info even when API doesn't provide it
                const currentHourFiltered = filterDataForHour(result, timelineState.hour, dateStr)
                const mergedMetadata = currentHourFiltered.metadata || result.metadata
                
                currentDayDataRef.current = {
                  date: dateStr,
                  mode: timelineState.mode,
                  data: result.data, // ALL regions for ALL hours
                  metadata: mergedMetadata // USE MERGED, not raw!
                }
                
                // CRITICAL: Update fallbackMetadataRef so it persists
                if (mergedMetadata?.overall_fallback) {
                  fallbackMetadataRef.current = mergedMetadata
                }
                
                // DON'T call setData here - the priority fetch already set the data with
                // correct metadata. The hour effect will use currentDayDataRef when needed.
                // Calling setData here was overwriting the priority fetch's normalized metadata.
              }
              // CRITICAL FIX: Clear the date fetching flag so HOUR EFFECT can process the data
              dateChangeFetchingRef.current = null
              cleanupProgress(true)
            } catch {
              // CRITICAL FIX: Clear the date fetching flag on error so HOUR EFFECT can run
              dateChangeFetchingRef.current = null
              cleanupProgress(false)
            }
            return
          }
          
          // Create promise for full day fetch
          const fullDayPromise = (async () => {
            try {
              // Fetch all hours at once by not specifying hour parameter
              const params = { region_code: 'all', date: dateStr }
              const url = new URL(`${API_BASE}${endpoint}`)
              Object.entries(params).forEach(([key, value]) => {
                url.searchParams.append(key, value.toString())
              })
              
              const response = await fetch(url.toString())
              if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`)
              }
              
              let result = await response.json()
              
              // NORMALIZE: The API returns fallback_metadata at root level, normalize it to metadata
              // This is critical for the DataStatusIndicator to work correctly
              if (result?.fallback_metadata) {
                const fm = result.fallback_metadata
                const overall_fallback = fm.lifecycle_fallback || fm.direct_fallback
                result = {
                  ...result,
                  metadata: {
                    ...(result.metadata || {}),
                    overall_fallback,
                    lifecycle_fallback: fm.lifecycle_fallback,
                    direct_fallback: fm.direct_fallback,
                    lifecycle_actual_date: fm.lifecycle_actual_date,
                    direct_actual_date: fm.direct_actual_date,
                    requested_date: fm.requested_date,
                    message: fm.message
                  }
                }
              }
              
              PerformanceLogger.endTimer(`full_day_fetch_${dateStr}`)
              PerformanceLogger.logDataSize(`full_day_data_${dateStr}`, result)
              
              // Set progress to 100% once data is received
              setLoadingProgress(100)
              
              // Validate data
              if (result?.data && Array.isArray(result.data)) {
                PerformanceLogger.increment('total_items_fetched', result.data.length)
                
                // Check metadata for fallback information
                // Backend returns: overall_fallback, lifecycle_actual_date, direct_actual_date, requested_date
                if (result?.metadata?.overall_fallback) {
                  // Fallback detected - API used data from different date
                }
                
                // Count unique regions in the data
                const regions = new Set(result.data.map((item: Record<string, unknown>) => item.region_code || item.region))
                PerformanceLogger.increment('unique_regions_full_day', regions.size)
              }
              
              return result
            } catch (error) {
              throw error
            }
          })()
          
          // Store the pending promise
          pendingRequests.set(pendingKey, fullDayPromise)
          
          // Handle background fetch completion
          fullDayPromise.then((result) => {
            // Cache the full day data WITH DATE VALIDATION
            fullDayCache.set(dayKey, { data: result, timestamp: now })
            
            // Only update currentDayDataRef if this is still the current date being viewed
            // Use currentDateRef.current (live ref) instead of timelineState.date (stale closure)
            if (currentDateRef.current === dateStr) {
              // CRITICAL FIX: First run filterDataForHour to get synthesized metadata
              // This ensures currentDayDataRef has the correct fallback info for hour effect
              const currentHourData = filterDataForHour(result, timelineState.hour, dateStr)
              
              // IMPORTANT: Use currentHourData.metadata which may contain synthesized fallback info
              // from filterDataForHour when mixed dates are detected
              const mergedMetadata = currentHourData.metadata || result.metadata
              
              // CRITICAL FIX: Store MERGED metadata in currentDayDataRef, not raw result.metadata
              // This ensures hour effect gets the synthesized fallback info when it reads from ref
              currentDayDataRef.current = {
                date: dateStr,
                mode: timelineState.mode,
                data: result.data, // ALL regions, ALL hours
                metadata: mergedMetadata // USE MERGED, not raw!
              }
              debugLogger.log('REF UPDATE', `Updated currentDayDataRef for ${dateStr} with ${result.data?.length} items, metadata.overall_fallback=${mergedMetadata?.overall_fallback}`)
              
              // CRITICAL: Update fallbackMetadataRef so it persists even if state gets overwritten
              if (mergedMetadata?.overall_fallback) {
                fallbackMetadataRef.current = mergedMetadata
              }
              
              const bgUpdateTime = Date.now()
              const newData = {
                data: currentHourData.data ? [...currentHourData.data] : currentHourData.data,
                metadata: mergedMetadata ? { ...mergedMetadata } : mergedMetadata,
                _updateId: bgUpdateTime,
                _triggeredBy: 'background_complete',
                _date: dateStr,
                _hour: timelineState.hour
              }
              setData(newData)
              setDataUpdateId(bgUpdateTime)
            } else {
              debugLogger.log('REF SKIP', `Not updating currentDayDataRef - date changed from ${dateStr} to ${timelineState.date}`)
            }
            
            // Cache each hour individually with ALL regions for that hour
            if (result?.data && Array.isArray(result.data)) {
              const ttl = getTTL(endpoint, timelineState.mode)
              for (let h = 0; h < 24; h++) {
                const hourParams = { region_code: 'all', date: dateStr, hour: h }
                const hourKey = getCacheKey(endpoint, hourParams)
                const hourData = filterDataForHour(result, h, dateStr)
                // CRITICAL: Cache the FULL hour data with all regions
                // CRITICAL: Use hourData.metadata which may contain synthesized fallback info
                // from filterDataForHour when mixed dates are detected (not result.metadata!)
                setCache(hourKey, {
                  data: hourData.data, // This should have 58 items (all regions for this hour)
                  metadata: hourData.metadata
                }, ttl)
              }
            }
            
            // CRITICAL FIX: Clear the date fetching flag so HOUR EFFECT can process the data
            dateChangeFetchingRef.current = null
            cleanupProgress(true)
          }).catch(() => {
            // CRITICAL FIX: Clear the date fetching flag on error so HOUR EFFECT can run
            dateChangeFetchingRef.current = null
            cleanupProgress(false)
          }).finally(() => {
            pendingRequests.delete(pendingKey)
          })
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
        setLoading(false)
        setBackgroundLoading(false)
        // CRITICAL FIX: Clear the date fetching flag on outer error so HOUR EFFECT isn't blocked
        dateChangeFetchingRef.current = null
      }
    }

    fetchData()
  // Only trigger on date/mode changes, not hour changes
  }, [timelineState.mode, timelineState.date])

  // CRITICAL FIX: Separate effect for hour changes to ensure proper re-renders
  // This effect handles both slider moves AND date changes with same hour
  useEffect(() => {
    // Skip for 'now' mode
    if (timelineState.mode === 'now') {
      return
    }
    
    // NOTE: We removed the early return that skipped when dateChangeFetchingRef was set.
    // This was causing the side panel to not update when date changed because:
    // 1. HOUR EFFECT would skip due to flag
    // 2. DATE/MODE EFFECT would complete and clear flag
    // 3. HOUR EFFECT wouldn't re-run because dependencies hadn't changed
    //
    // The data sources below are all date-aware (they check if data matches the requested date),
    // so there's no risk of using stale data. If no data exists for the new date yet,
    // HOUR EFFECT will simply return early at line 1476-1479 without calling setData.
    if (dateChangeFetchingRef.current === timelineState.date) {
      // Note: date/mode effect is fetching, but continuing to check for cached data
    }

    const dateStr = timelineState.date
    const endpoint = timelineState.mode === 'past'
      ? '/v1/CarbonIntensityHistory'
      : '/v1/CarbonIntensityForecastsHistory'

    // Try to get data from multiple sources in order of preference:
    // 1. Filter from currentDayDataRef (if it has full day data)
    // 2. Check hour-specific cache
    // 3. Check full day cache and filter
    
    let hourData: { data: unknown[] | null; metadata?: unknown } | null = null
    let dataSource = 'none'

    // Source 1: Try currentDayDataRef if it has data for the correct date
    if (currentDayDataRef.current && currentDayDataRef.current.date === dateStr) {
      const filtered = filterDataForHour(
        {
          data: currentDayDataRef.current.data,
          metadata: currentDayDataRef.current.metadata
        },
        timelineState.hour,
        dateStr
      )
      
      if (filtered.data && filtered.data.length > 0) {
        hourData = filtered
        dataSource = 'currentDayDataRef'
      }
    }

    // Source 2: If ref didn't have data, check hour-specific cache
    if (!hourData || !hourData.data || hourData.data.length === 0) {
      const hourParams = { region_code: 'all', date: dateStr, hour: timelineState.hour }
      const hourCacheKey = getCacheKey(endpoint, hourParams)
      const cachedHourResult = getFromCache(hourCacheKey)
      
      if (cachedHourResult && cachedHourResult.data &&
          (Array.isArray(cachedHourResult.data) ? cachedHourResult.data.length > 0 : true)) {
        hourData = {
          data: Array.isArray(cachedHourResult.data) ? cachedHourResult.data : [cachedHourResult.data],
          metadata: cachedHourResult.metadata
        }
        dataSource = 'hourCache'
      }
    }

    // Source 3: If still no data, check full day cache
    if (!hourData || !hourData.data || hourData.data.length === 0) {
      const dayKey = `${endpoint}-${dateStr}-fullday`
      const fullDayData = fullDayCache.get(dayKey)
      
      if (fullDayData && fullDayData.data) {
        const filtered = filterDataForHour(fullDayData.data, timelineState.hour, dateStr)
        
        if (filtered.data && filtered.data.length > 0) {
          hourData = filtered
          dataSource = 'fullDayCache'
          
          // CRITICAL FIX: Use filtered.metadata (which may have synthesized fallback info)
          // instead of fullDayData.data.metadata (raw from API)
          currentDayDataRef.current = {
            date: dateStr,
            mode: timelineState.mode,
            data: fullDayData.data.data,
            metadata: filtered.metadata // USE MERGED, not raw!
          }
          
          // CRITICAL: Update fallbackMetadataRef so it persists
          if (filtered.metadata?.overall_fallback) {
            fallbackMetadataRef.current = filtered.metadata
          }
        }
      }
    }

    // If we still have no data, return (data will come from pending fetch)
    if (!hourData || !hourData.data || hourData.data.length === 0) {
      return
    }

    // CRITICAL: Create new object reference with unique ID to force React re-render
    const hourEffectUpdateTime = Date.now()
    const newData = {
      data: hourData.data ? [...hourData.data] : hourData.data,
      metadata: hourData.metadata ? { ...hourData.metadata } : hourData.metadata,
      _updateId: hourEffectUpdateTime, // Unique ID to force re-render
      _triggeredBy: 'hour_effect',
      _dataSource: dataSource,
      _date: dateStr,
      _hour: timelineState.hour
    }

    // Use callback form to ensure we're always creating a new reference
    setData(() => newData)
    setDataUpdateId(hourEffectUpdateTime)

    debugLogger.log('HOUR_EFFECT', `Set ${newData.data?.length} items for hour ${timelineState.hour}`, {
      updateId: newData._updateId,
      date: dateStr,
      dataSource
    })

  }, [timelineState.hour, timelineState.date, timelineState.mode]) // React to hour OR date changes

  // PROGRESSIVE LOADING FIX: Simplified return value computation
  // Heavy memoization was preventing immediate updates when priority fetch data arrived
  // Now we compute values directly, relying on React's natural batching for performance
  
  const stateMetadata = (data as Record<string, unknown> | null)?.metadata as Record<string, unknown> | undefined
  const refMetadata = fallbackMetadataRef.current
  
  // Compute final metadata - merge state and ref metadata
  let finalMetadata = stateMetadata
  if (refMetadata && refMetadata.requested_date === timelineState.date) {
    // fallbackMetadataRef has fresh data for current date - use it
    finalMetadata = { ...stateMetadata, ...refMetadata }
  } else if (stateMetadata?.overall_fallback) {
    // State metadata has fallback info - use it
    finalMetadata = stateMetadata
  } else if (refMetadata?.overall_fallback) {
    // RefMetadata has fallback but might be stale - merge with state
    finalMetadata = { ...stateMetadata, ...refMetadata }
  }
  
  // Compute the data object with fallback info
  const dataWithFallback = data ? {
    ...(data as Record<string, unknown>),
    metadata: finalMetadata,
    fallback_metadata: fallbackMetadataRef.current,
    _date: timelineState.date  // CRITICAL FIX: Always use the requested date
  } as Record<string, unknown> : null

  // Calculate data length
  const dataLength = dataWithFallback?.data
    ? (Array.isArray(dataWithFallback.data) ? (dataWithFallback.data as unknown[]).length : 1)
    : 0

  // Return without heavy memoization - let React handle re-render batching
  // dataUpdateId is the stable signal that consumers should use to detect actual data changes
  return {
    data: dataWithFallback,
    loading,
    error,
    backgroundLoading,
    loadingProgress,
    // CRITICAL FIX: Return dataUpdateId as _updateId so consumers have a reliable signal
    _updateId: dataUpdateId,
    _dataLength: dataLength,
    _date: timelineState.date
  }
}

// Energy Sources Data Hook
export const useEnergySourcesData = (region: string, timelineState: TimelineState) => {
  const [data, setData] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!region) return

    const fetchData = async () => {
      setLoading(true)
      setError(null)

      try {
        let endpoint: string
        let params: Record<string, string | number> = { region_code: region }

        if (timelineState.mode === 'now') {
          endpoint = '/v1/EnergySources'
        } else {
          const dateStr = timelineState.date
          const hour = timelineState.hour
          
          if (timelineState.mode === 'past') {
            endpoint = '/v1/EnergySourcesHistory'
            params = { ...params, date: dateStr, hour: hour }
          } else {
            endpoint = '/v1/EnergySourcesForecastsHistory'
            params = { ...params, date: dateStr, hour: hour }
          }
        }

        // Check cache first
        const cacheKey = getCacheKey(endpoint, params)
        const cachedResult = getFromCache(cacheKey)
        
        if (cachedResult) {
          setData(cachedResult.data)
          setLoading(false)
          
          // Prefetch adjacent data in background
          if (ENABLE_PREFETCH && timelineState.mode !== 'now') {
            prefetchAdjacentData(endpoint, params, timelineState.mode)
          }
          return
        }

        // Fetch with deduplication
        const result = await fetchWithDeduplication(endpoint, params, timelineState.mode)
        setData(result.data)
        
        // Prefetch adjacent data
        if (ENABLE_PREFETCH && timelineState.mode !== 'now') {
          prefetchAdjacentData(endpoint, params, timelineState.mode)
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [region, timelineState.mode, timelineState.date, timelineState.hour])

  return { data, loading, error }
}

// Historical Carbon Intensity Hook
export const useHistoricalCarbonIntensity = (region: string, timelineState: TimelineState) => {
  const [data, setData] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!region || timelineState.mode === 'now') return

    const fetchData = async () => {
      setLoading(true)
      setError(null)

      try {
        const endpoint = timelineState.mode === 'past'
          ? '/v1/CarbonIntensityHistory'
          : '/v1/CarbonIntensityForecastsHistory'
        
        const params = {
          region_code: region,
          date: timelineState.date,
          hour: timelineState.hour
        }

        // Check cache first
        const cacheKey = getCacheKey(endpoint, params)
        const cachedResult = getFromCache(cacheKey)
        
        if (cachedResult) {
          setData(cachedResult.data)
          setLoading(false)
          
          // Prefetch adjacent data in background
          if (ENABLE_PREFETCH) prefetchAdjacentData(endpoint, params, timelineState.mode)
          return
        }

        // Fetch with deduplication
        const result = await fetchWithDeduplication(endpoint, params, timelineState.mode)
        setData(result.data)
        
        // Prefetch adjacent data
        if (ENABLE_PREFETCH) prefetchAdjacentData(endpoint, params, timelineState.mode)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [region, timelineState.mode, timelineState.date, timelineState.hour])

  return { data, loading, error }
}

// Carbon Intensity Forecasts Hook (using camelCase for legacy compatibility)
export const useCarbonIntensityForecasts = (regionCode: string, forecastPeriod?: number) => {
  const [data, setData] = useState<Record<string, unknown> | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!regionCode) return

    const fetchData = async () => {
      setLoading(true)
      setError(null)

      try {
        const endpoint = '/v1/CarbonIntensityForecasts'
        const params: Record<string, string | number> = {
          regionCode: regionCode
        }
        
        // Add forecastPeriod if provided
        if (forecastPeriod !== undefined) {
          params.forecastPeriod = forecastPeriod
        }

        // Check cache first
        const cacheKey = getCacheKey(endpoint, params)
        const cachedResult = getFromCache(cacheKey)
        
        if (cachedResult) {
          setData(cachedResult.data)
          setLoading(false)
          return
        }

        // Fetch with deduplication
        const result = await fetchWithDeduplication(endpoint, params, 'future')
        setData(result.data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    fetchData()
  }, [regionCode, forecastPeriod])

  return { data, loading, error }
}

// Clear old cache entries from localStorage with LRU eviction
const clearOldCacheEntries = (aggressive: boolean = false) => {
  if (!localStorageAvailable) return
  
  const entries: Array<{ key: string; timestamp: number; size: number }> = []
  const now = Date.now()
  
  // Collect all cache entries with their metadata
  const keys: string[] = []
  for (let i = 0; i < localStorage.length; i++) {
    const key = localStorage.key(i)
    if (key && key.startsWith('/v1/')) {
      keys.push(key) // Store keys first to avoid iteration issues
    }
  }
  
  // Process collected keys
  for (const key of keys) {
    try {
      const item = localStorage.getItem(key)
      if (item) {
        // Try to parse (handle both compressed and uncompressed)
        const jsonStr = item.includes('~rc') || item.includes('~ci') ? decompressJSON(item) : item
        const parsed = JSON.parse(jsonStr)
        const timestamp = parsed.timestamp || 0
        const size = getByteSize(key) + getByteSize(item)
        entries.push({ key, timestamp, size })
      }
    } catch {
      // Invalid entry, mark for removal immediately
      try {
        localStorage.removeItem(key)
      } catch {
        // Ignore error - invalid entry already logged
      }
    }
  }
  
  // Sort by timestamp (oldest first)
  entries.sort((a, b) => a.timestamp - b.timestamp)
  
  let keysToRemove: string[] = []
  
  if (aggressive) {
    // Remove 75% of entries when aggressive (more aggressive than before)
    const removeCount = Math.max(1, Math.ceil(entries.length * 0.75))
    keysToRemove = entries.slice(0, removeCount).map(e => e.key)
  } else {
    // Remove entries older than 15 minutes (reduced from 30)
    const ageThreshold = 15 * 60 * 1000
    keysToRemove = entries
      .filter(e => now - e.timestamp > ageThreshold)
      .map(e => e.key)
    
    // If nothing old enough, remove at least 30% of oldest entries (increased from 20%)
    if (keysToRemove.length === 0 && entries.length > 5) {
      const removeCount = Math.max(1, Math.ceil(entries.length * 0.3))
      keysToRemove = entries.slice(0, removeCount).map(e => e.key)
    }
  }
  
  // Remove selected entries
  let removedCount = 0
  let totalSizeRemoved = 0
  
  keysToRemove.forEach(key => {
    try {
      const item = localStorage.getItem(key)
      if (item) {
        totalSizeRemoved += getByteSize(key) + getByteSize(item)
      }
      localStorage.removeItem(key)
      // Also remove from memory cache
      memoryCache.delete(key)
      removedCount++
    } catch {
      // Ignore removal errors
    }
  })
}

// Utility function to clear all cache (useful for debugging and recovery)
export const clearCache = () => {
  memoryCache.clear()
  fullDayCache.clear()
  filteredHourCache.clear()
  pendingRequests.clear()
  abortControllers.forEach(controller => controller.abort())
  abortControllers.clear()
  
  // Clear API-related localStorage entries
  if (localStorageAvailable) {
    try {
      const keysToRemove: string[] = []
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i)
        if (key && key.startsWith('/v1/')) {
          keysToRemove.push(key)
        }
      }
      keysToRemove.forEach(key => {
        try {
          localStorage.removeItem(key)
        } catch {
          // Ignore removal error
        }
      })
      
      // Reset localStorage availability
      localStorageAvailable = true
      localStorageFailureCount = 0
    } catch {
      // Ignore clear errors
    }
  }
}

// Initialize cache on startup - clear if corrupted or too full
export const initializeCache = () => {
  try {
    // Test localStorage availability
    const testKey = '__cache_test__'
    localStorage.setItem(testKey, 'test')
    localStorage.removeItem(testKey)
    
    // Check total cache size
    const totalSize = getTotalCacheSize()
    
    // If cache is too full (>80% of limit), clear old entries
    if (totalSize > MAX_CACHE_SIZE * 0.8) {
      clearOldCacheEntries(true)
    }
    
    // Clear any corrupted entries
    const keys: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key && key.startsWith('/v1/')) {
        keys.push(key)
      }
    }
    
    let corruptedCount = 0
    keys.forEach(key => {
      try {
        const item = localStorage.getItem(key)
        if (item) {
          // Try to parse to check if valid
          const jsonStr = item.includes('~rc') || item.includes('~ci') ? decompressJSON(item) : item
          JSON.parse(jsonStr)
        }
      } catch {
        // Corrupted entry, remove it
        try {
          localStorage.removeItem(key)
          corruptedCount++
        } catch {
          // Ignore removal error
        }
      }
    })
    
    localStorageAvailable = true
    localStorageFailureCount = 0
    
  } catch {
    localStorageAvailable = false
    
    // Try to clear everything as last resort
    try {
      localStorage.clear()
    } catch {
      // Ignore removal error
    }
  }
}
// Utility function to get cache stats
export const getCacheStats = () => {
  return {
    memoryCacheSize: memoryCache.size,
    pendingRequests: pendingRequests.size,
    memoryCacheKeys: Array.from(memoryCache.keys()),
    fullDayCacheSize: fullDayCache.size,
    fullDayCacheKeys: Array.from(fullDayCache.keys()),
    filteredHourCacheSize: filteredHourCache.size,
    filteredHourCacheKeys: Array.from(filteredHourCache.keys())
  }
}

// Debug function to validate cache integrity
export const validateCacheIntegrity = () => {
  const issues: string[] = []
  
  // Check memory cache
  memoryCache.forEach((value, key) => {
    if (!value.data) {
      issues.push(`Memory cache entry ${key} has no data`)
    }
    if (!value.timestamp) {
      issues.push(`Memory cache entry ${key} has no timestamp`)
    }
  })
  
  // Check full day cache
  fullDayCache.forEach((value, key) => {
    if (!value.data) {
      issues.push(`Full day cache entry ${key} has no data`)
    }
    if (!value.timestamp) {
      issues.push(`Full day cache entry ${key} has no timestamp`)
    }
    
    // Validate date consistency
    const dateMatch = key.match(/(\d{4}-\d{2}-\d{2})/)
    if (dateMatch) {
      const expectedDate = dateMatch[1]
      if (value.data?.metadata?.actual_date && value.data.metadata.actual_date !== expectedDate) {
        issues.push(`Full day cache entry ${key} has mismatched date: expected ${expectedDate}, got ${value.data.metadata.actual_date}`)
      }
    }
  })
  
  // Check filtered hour cache
  filteredHourCache.forEach((value, key) => {
    if (!value.data) {
      issues.push(`Filtered hour cache entry ${key} has no data`)
    }
    
    // Parse the cache key to validate consistency
    const keyParts = key.split('-')
    if (keyParts.length >= 4) {
      const [year, month, day, hour] = keyParts
      const date = `${year}-${month}-${day}`
      const hourNum = parseInt(hour)
      
      if (value._filteredDate && value._filteredDate !== date) {
        issues.push(`Filtered cache key ${key} date mismatch: key=${date}, data=${value._filteredDate}`)
      }
      if (value._filteredHour !== undefined && value._filteredHour !== hourNum) {
        issues.push(`Filtered cache key ${key} hour mismatch: key=${hourNum}, data=${value._filteredHour}`)
      }
    }
  })
  
  return { valid: issues.length === 0, issues }
}

// Test function for multi-date caching
export const testMultiDateCaching = async () => {
  const testDates = [
    '2024-01-15',
    '2024-01-16',
    '2024-01-17'
  ]
  
  const testHours = [0, 12, 23]
  
  for (const date of testDates) {
    for (const hour of testHours) {
      const endpoint = '/v1/CarbonIntensityHistory'
      const params = { region_code: 'all', date, hour }
      const cacheKey = getCacheKey(endpoint, params)
      
      // First fetch - should miss cache
      getFromCache(cacheKey)
    }
  }
  
  // Validate cache integrity
  const validation = validateCacheIntegrity()
  
  // Get cache stats
  const stats = getCacheStats()
  
  return { validation, stats }
}


