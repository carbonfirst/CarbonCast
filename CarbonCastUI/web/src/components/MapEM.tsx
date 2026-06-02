import { useCallback, useEffect, useMemo, useRef, useState, forwardRef, useImperativeHandle } from 'react'
import type { MapRef } from 'react-map-gl/maplibre'
import { Map } from 'react-map-gl/maplibre'
import type { Map as MlMap } from 'maplibre-gl'
import { useNavigate, useSearchParams } from 'react-router-dom'
// Removed useTheme import - now using DOM-based theme detection only
import { setMousePosition, setHoveredZone, setMapMoving, triggerDataUpdate } from './InfoPopover'
import { useCarbonIntensityData, type TimelineState } from '../hooks/cache'
import { apiToMapRegionMapping, getAllSubRegions, getDisplayZoneId } from '../utils/regionMapping'

// Import MapLibre globally to make it available
import maplibregl from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

// MODULE-LEVEL STORAGE: Persists across component remounts caused by route changes
// This is necessary because navigating from /map to /zone/:region causes MainView to remount,
// losing all React state including selectedRegionBounds
const persistentZoomState: {
  bounds: any | null
  regionName: string | null
  timestamp: number
} = {
  bounds: null,
  regionName: null,
  timestamp: 0
}

export interface MapEMRef {
  getMapRef: () => MapRef | null
}

// Color scale function for carbon intensity
function getColor(d: number | undefined, isForecast: boolean = false) {
  const v = d ?? -1
  // In forecast mode, treat 0 as "no data" since zero emissions is practically impossible
  if (isForecast && v === 0) {
    return '#CBD5E1' // Gray for no data
  }
  // Handle valid 0 value - very low/green
  if (v === 0) {
    return '#2fca2c' // Green for 0 carbon intensity (cleanest possible)
  }
  return v > 1200 ? '#48190A'
    : v > 1000 ? '#6C2D00'
    : v > 800 ? '#904006'
    : v > 600 ? '#B4560D'
    : v > 500 ? '#C45F00'
    : v > 400 ? '#D97914'
    : v > 300 ? '#feb204'
    : v > 250 ? '#FFCC00'
    : v > 200 ? '#F2D40C'
    : v > 125 ? '#F7F55F'
    : v > 100 ? '#4cf036'
    : v > 50 ? '#28e40f'
    : v > 0 ? '#2fca2c'
    : '#CBD5E1' // Default gray for no data (undefined or negative)
}

interface MapEMProps {
  selectedRegion?: string | null
  selectedRegionBounds?: any // Bounds to restore zoom after remount
  onDeselect?: () => void
  onRegionSelect?: (region: string, bounds?: any) => void
  timelineState?: TimelineState
}

const MapEM = forwardRef<MapEMRef, MapEMProps>(
  ({ selectedRegion, selectedRegionBounds, onDeselect, onRegionSelect, timelineState }, ref) => {
  const mapRef = useRef<MapRef | null>(null)
  
  // Track last applied colors to avoid redundant setFeatureState calls
  const lastAppliedColorsRef = useRef<Record<string, string>>({})
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [isLoaded, setIsLoaded] = useState(false)
  
  // Use a ref to track loaded state directly (bypasses React state issues)
  const isLoadedRef = useRef(false)
  
  // Track MapLibre availability through map instance
  const [maplibreglAvailable, setMaplibreglAvailable] = useState(false)
  // Using DOM-based theme detection only for reliability
  
  // Track first click after load
  const firstClickAfterLoadRef = useRef(true)
  const clickCountRef = useRef(0)
  const mapInitTimeRef = useRef<number>(0)
  
  // Store zoom state to survive navigation
  const savedZoomStateRef = useRef<{ center: [number, number]; zoom: number } | null>(null)
  

  const geo: any = (window as any).statesData || (window as any).statesData1
  
  // Fetch carbon intensity data
  const defaultTimelineState: TimelineState = {
    mode: 'now',
    date: new Date().toISOString().split('T')[0],
    hour: new Date().getHours()
  }
  const { data: carbonData, _updateId } = useCarbonIntensityData(timelineState || defaultTimelineState)
  
  // NOTE: This effect will be moved after zoneToValue declaration to fix dependency order
  
  // Use centralized region mapping
  
  // Remove dataVersion - it's not helping and adds complexity
  
  // Create a map of region codes to carbon intensity values
  // PROGRESSIVE LOADING FIX: Use carbonData directly as dependency
  // This ensures we recompute immediately when any new data arrives (priority or background)
  const zoneToValue = useMemo(() => {
    const currentTimelineState = timelineState || defaultTimelineState
    // Access data directly from carbonData
    const carbonDataArray = carbonData?.data as unknown[] | undefined
    
    const map: Record<string, number> = {}
    
    // Early return if no data
    if (!carbonDataArray || !Array.isArray(carbonDataArray) || carbonDataArray.length === 0) {
      return map
    }
    
    // Data is available, proceed with processing
      
      
      // Determine which field to use based on timeline mode and data structure
      // Try multiple possible field names for carbon intensity
      const possibleIntensityFields = [
        'carbon_intensity_avg_direct',
        'forecasted_avg_carbon_intensity_direct',
        'carbon_intensity',
        'avg_carbon_intensity_direct',
        'carbonIntensity',
        'value'
      ]
      
      // Try multiple possible field names for hour/time
      const possibleTimeFields = [
        'UTC time',
        'hour',
        'UTC_time',
        'utc_hour',
        'time',
        'timestamp_hour'
      ]
      
      // For past/future modes, filter by the specific hour
      let dataToProcess: unknown[] = carbonDataArray
      
      if (currentTimelineState.mode !== 'now') {
        // Try to find the time field that exists in the data
        let timeField: string | null = null
        
        if (carbonDataArray.length > 0) {
          const sampleItem = carbonDataArray[0] as Record<string, unknown>
          timeField = possibleTimeFields.find(field => sampleItem[field] !== undefined) || null
        }
        
        if (timeField) {
          // The API now handles fallback internally, so we don't need to check for date mismatches
            
          dataToProcess = carbonDataArray.filter((item: unknown) => {
            const row = item as Record<string, unknown>
            const timeValue = row[timeField as string]
            if (timeValue !== undefined) {
              let hour: number | null = null
              
              // Handle different time formats
              if (typeof timeValue === 'string') {
                // Check if it's an ISO datetime string like "2023-09-21T09:00:00"
                if (timeValue.includes('T')) {
                  // Handle ISO format: "2023-09-21T09:00:00" or "2023-09-21T09:00:00Z"
                  const parts = timeValue.split('T')
                  if (parts.length === 2) {
                    const timePart = parts[1] // Get "09:00:00" or "09:00:00Z" part
                    const hourStr = timePart.split(':')[0] // Get "09" part
                    hour = parseInt(hourStr)
                  }
                } else if (timeValue.includes(' ')) {
                  // Check if it's a datetime string like "2023-09-13 00:00:00"
                  const timePart = timeValue.split(' ')[1] // Get "00:00:00" part
                  if (timePart) {
                    const hourStr = timePart.split(':')[0] // Get "00" part
                    hour = parseInt(hourStr)
                  }
                } else if (timeValue.includes(':')) {
                  // Handle time-only format like "00:00:00"
                  const hourStr = timeValue.split(':')[0]
                  hour = parseInt(hourStr)
                } else {
                  // Try parsing as a simple number string
                  hour = parseInt(timeValue)
                }
              } else if (typeof timeValue === 'number') {
                hour = timeValue
              }
              
              // Compare the extracted hour with the selected hour
              if (hour !== null && !isNaN(hour)) {
                return hour === currentTimelineState.hour
              }
            }
            return false // Exclude items without valid time field in past/future modes
          })
        }
      }
      
      dataToProcess.forEach((item: unknown) => {
        const row = item as Record<string, unknown>
        if (row.region_code) {
          // Find the intensity field that exists in this row
          let intensityValue: number | undefined
          
          // First try the mode-specific field
          // NOTE: Backend may return string values (from CSV fallback), so we need to handle both
          if (currentTimelineState.mode === 'future') {
            const rawValue = row['forecasted_avg_carbon_intensity_direct']
            if (rawValue !== undefined && rawValue !== null) {
              intensityValue = typeof rawValue === 'string' ? parseFloat(rawValue) : (rawValue as number)
            }
          } else {
            const rawValue = row['carbon_intensity_avg_direct']
            if (rawValue !== undefined && rawValue !== null) {
              intensityValue = typeof rawValue === 'string' ? parseFloat(rawValue) : (rawValue as number)
            }
          }
          
          // If not found, try other possible fields
          if (intensityValue === undefined) {
            for (const field of possibleIntensityFields) {
              if (row[field] !== undefined && row[field] !== null) {
                // Handle string values that might need parsing
                const rawValue = row[field]
                const value = typeof rawValue === 'string' ? parseFloat(rawValue) : rawValue as number
                if (!isNaN(value)) {
                  intensityValue = value
                  break
                }
              }
            }
          }
          
          if (intensityValue !== undefined && !isNaN(intensityValue)) {
            // In future mode, treat 0 as "no data" since zero emissions is practically impossible
            if (currentTimelineState.mode === 'future' && intensityValue === 0) {
              // Skip adding 0 values in future mode - they'll show as gray
              return
            }
            // Map the API region code to the map region name using centralized mapping
            const regionCode = row.region_code as string
            const mapRegionName = apiToMapRegionMapping[regionCode] || regionCode
            map[mapRegionName] = intensityValue
            
            // Also apply the same value to all sub-regions in the group
            // This ensures grouped regions (like SE-SE1, SE-SE2, etc.) share the same color
            const subRegions = getAllSubRegions(mapRegionName)
            subRegions.forEach(subRegion => {
              if (subRegion !== mapRegionName) {
                map[subRegion] = intensityValue
              }
            })
          }
        }
      })
    
    // Trigger InfoPopover update when zone values change
    if (Object.keys(map).length > 0) {
      triggerDataUpdate()
    }
    
    return map
  // PROGRESSIVE LOADING FIX: Include carbonData directly in dependencies
  // This ensures immediate update when priority fetch data arrives
  // _updateId alone wasn't sufficient because carbonData might update first
  }, [carbonData, _updateId, timelineState?.mode, timelineState?.hour])


  // Expose map ref to parent components
  useImperativeHandle(ref, () => ({
    getMapRef: () => mapRef.current
  }))

  const interactiveLayerIds = useMemo(() => ['zones-fill'], [])

    const mapStyle = useMemo(() => {
    // Create basic style that will always show the map
    const baseStyle: any = {
      version: 8,
      sources: {},
      layers: [
        {
          id: 'background',
          type: 'background',
          paint: {
            'background-color': '#E6E8EB' // Default light theme, updated via paint properties
          }
        }
      ]
    }

    // Only add geojson layers if data is available
    if (geo && geo.features && geo.features.length > 0) {
      baseStyle.sources = {
        world: {
          type: 'geojson',
          data: geo,
          promoteId: 'zoneName' in (geo.features[0]?.properties || {}) ? 'zoneName' : 'name'
        }
      }
      
      // Create initial style with feature-state based colors (updated via setFeatureState per zone)
      baseStyle.layers.push(
        {
          id: 'zones-fill',
          type: 'fill',
          source: 'world',
          paint: {
            // Use feature-state for color - this is updated per-zone via setFeatureState()
            // No CSS transition needed since feature state updates are instant
            'fill-color': [
              'coalesce',
              ['feature-state', 'color'],  // Read color from feature state
              '#CBD5E1'                     // Default fallback color (gray)
            ],
            'fill-opacity': [ 'case', ['boolean', ['feature-state','hover'], false], 0.9, 0.8 ]
          }
        },
        {
          id: 'zones-outline',
          type: 'line',
          source: 'world',
          paint: {
            'line-color': '#A3A3A3', // Default light theme, updated via paint properties
            'line-width': 1.25
          }
        },
        {
          id: 'zones-selected',
          type: 'line',
          source: 'world',
          filter: ['==', ['coalesce',['get','zoneName'],['get','name']], ''], // Default to no selection
          paint: {
            'line-color': '#f59e0b', // Default light theme, updated via paint properties
            'line-width': 3
          }
        }
      )
    }

    return baseStyle
  }, [geo]) // Only depend on geo, not on zoneToValue to prevent map reloads!

  // Create a stable theme update function - only handles theme colors, not zone fill colors
  // Zone fill colors are now updated via setFeatureState in a separate effect
  const updateMapTheme = useCallback(() => {
    const map = mapRef.current?.getMap()
    if (!map) {
      return
    }
    
    // Always read current theme directly from DOM
    const isDark = document.documentElement.classList.contains('dark')
    
    // Apply theme immediately without delay
    try {
      // Update background color
      map.setPaintProperty('background', 'background-color', isDark ? '#111827' : '#E6E8EB')
      
      // Update zones outline color
      if (map.getLayer('zones-outline')) {
        map.setPaintProperty('zones-outline', 'line-color', isDark ? 'rgba(255,255,255,0.3)' : '#A3A3A3')
      }
      
      // Update selected zone color
      if (map.getLayer('zones-selected')) {
        map.setPaintProperty('zones-selected', 'line-color', isDark ? '#fbbf24' : '#f59e0b')
      }
    } catch {
      // Silent error handling
    }
  }, [])

  // Apply theme and carbon intensity colors when map loads
  useEffect(() => {
    if (isLoaded) {
      updateMapTheme()
    }
  }, [isLoaded, updateMapTheme])
  
  // FEATURE STATE API: Update individual zone colors via setFeatureState
  // This is much faster than rebuilding the entire case expression via setPaintProperty
  // No CSS transitions needed - feature state updates are instant
  useEffect(() => {
    const map = mapRef.current?.getMap()
    if (!map || !isLoaded) {
      return
    }
    
    const zoneCount = Object.keys(zoneToValue).length
    if (zoneCount === 0) {
      return
    }
    
    const isForecast = timelineState?.mode === 'future'
    
    // Update each zone's color via setFeatureState
    Object.entries(zoneToValue).forEach(([zoneId, value]) => {
      if (typeof value !== 'number' || isNaN(value)) {
        return
      }
      
      const fillColor = getColor(value, isForecast)
      
      // Only update if color changed (optimization)
      const lastColor = lastAppliedColorsRef.current[zoneId]
      if (lastColor === fillColor) {
        return
      }
      
      try {
        map.setFeatureState(
          { source: 'world', id: zoneId },
          { color: fillColor }
        )
        lastAppliedColorsRef.current[zoneId] = fillColor
      } catch {
        // Silently ignore - zone might not exist in the current view
      }
    })
  }, [zoneToValue, isLoaded, timelineState?.mode, timelineState?.hour])

  // Check for MapLibre availability
  useEffect(() => {
    const checkMaplibregl = () => {
      // More thorough check for MapLibre availability
      if (typeof maplibregl !== 'undefined' && maplibregl.LngLatBounds) {
        setMaplibreglAvailable(true)
        return true
      }
      return false
    }

    // Check immediately
    if (checkMaplibregl()) return

    // If not available, poll every 50ms for faster detection
    const interval = setInterval(() => {
      if (checkMaplibregl()) {
        clearInterval(interval)
      }
    }, 50)

    // Stop checking after 5 seconds
    const timeout = setTimeout(() => {
      clearInterval(interval)
    }, 5000)

    return () => {
      clearInterval(interval)
      clearTimeout(timeout)
    }
  }, []) // Check immediately on mount

  // Fallback: ensure map is considered loaded after a reasonable timeout
  useEffect(() => {
    const fallbackTimeout = setTimeout(() => {
      if (!isLoadedRef.current) {
        // Only consider loaded if MapLibre is also available
        if (typeof maplibregl !== 'undefined' && maplibregl.LngLatBounds) {
          setIsLoaded(true)
          isLoadedRef.current = true
          setMaplibreglAvailable(true)
        }
      }
    }, 2000) // 2 second fallback to ensure MapLibre is ready

    return () => {
      clearTimeout(fallbackTimeout)
    }
  }, []) // Remove isLoaded dependency to prevent restart

  // Watch for DOM class changes using MutationObserver (more reliable than events)
  useEffect(() => {
    if (!isLoaded) return
    
    let lastTheme: boolean | null = null
    
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
          const isDark = document.documentElement.classList.contains('dark')
          
          // Only update if theme actually changed to prevent unnecessary updates
          if (lastTheme !== isDark) {
            lastTheme = isDark
            updateMapTheme()
          }
        }
      })
    })
    
    // Initialize with current theme
    lastTheme = document.documentElement.classList.contains('dark')
    
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class']
    })
    
    return () => {
      observer.disconnect()
    }
  }, [isLoaded, updateMapTheme])

  const setHover = useCallback((map: MlMap, id: string | number | null, hover: boolean) => {
    try { if (id != null) map.setFeatureState({ source:'world', id }, { hover }) } catch {}
  }, [])

  const onMapLoad = useCallback(() => {
    // Check if MapLibre is available before considering the map loaded
    const checkAndSetLoaded = () => {
      if (typeof maplibregl !== 'undefined' && maplibregl.LngLatBounds) {
        const map = mapRef.current?.getMap()
        setIsLoaded(true)
        isLoadedRef.current = true
        setMaplibreglAvailable(true)
        // Reset first click flag when map loads
        firstClickAfterLoadRef.current = true
        clickCountRef.current = 0
        mapInitTimeRef.current = Date.now()
        
        // CRITICAL FIX: Check module-level persistent bounds FIRST
        // This is the primary source because it survives component remounts
        const timeSinceBoundsSet = Date.now() - persistentZoomState.timestamp
        const boundsStillValid = persistentZoomState.bounds && timeSinceBoundsSet < 5000 // Valid for 5 seconds
        
        if (map && boundsStillValid && persistentZoomState.regionName) {
          // Use persistent module-level bounds (survives remount)
          // Wait a bit for the map to be fully ready, then restore zoom
          setTimeout(() => {
            if (persistentZoomState.bounds) {
              try {
                map.fitBounds(persistentZoomState.bounds, {
                  padding: 80,
                  duration: 0, // Instant - no animation on restore
                  maxZoom: 4.5
                })
                // Clear after successful restore
                persistentZoomState.bounds = null
                persistentZoomState.regionName = null
                persistentZoomState.timestamp = 0
              } catch {
                // Silent error handling
              }
            }
          }, 100) // Shorter delay since this is critical path
        } else if (map && selectedRegionBounds && selectedRegion) {
          // Fallback to prop-based bounds (for cases where route doesn't change)
          setTimeout(() => {
            if (selectedRegionBounds) {
              try {
                map.fitBounds(selectedRegionBounds, {
                  padding: 80,
                  duration: 0,
                  maxZoom: 4.5
                })
              } catch {
                // Silent error handling
              }
            }
          }, 200)
        } else if (map && savedZoomStateRef.current && selectedRegion) {
          // Third fallback to saved ref state
          setTimeout(() => {
            if (savedZoomStateRef.current) {
              map.setCenter(savedZoomStateRef.current.center)
              map.setZoom(savedZoomStateRef.current.zoom)
              savedZoomStateRef.current = null
            }
          }, 200)
        }
        
        // Apply theme and carbon intensity colors immediately on load
        // Add a small delay to ensure map is fully ready
        setTimeout(() => {
          updateMapTheme()
        }, 100)
      } else {
        // Retry after a short delay
        setTimeout(checkAndSetLoaded, 50)
      }
    }
    
    checkAndSetLoaded()
  }, [updateMapTheme, selectedRegion, selectedRegionBounds])

  const onMouseMove = useCallback((event: any) => {
    const map = mapRef.current?.getMap()
    const feature = event.features?.[0]
    if (!map) return
    
    // Optimized mouse position update (minimal calculations)
    const rect = map.getCanvas().getBoundingClientRect()
    setMousePosition({
      x: rect.left + event.point.x,
      y: rect.top + event.point.y
    })
    
    // Efficient hover state management
    const hoveredId = (map as any).__hoveredId as (string | number | null)
    const newFeatureId = feature?.id
    
    // Only update if hover state actually changes
    if (hoveredId !== newFeatureId) {
      // Clear previous hover
      if (hoveredId != null) {
        setHover(map, hoveredId, false)
      }
      
      // Set new hover
      if (newFeatureId != null) {
        setHover(map, newFeatureId, true)
        const name = feature.properties?.zoneName || feature.properties?.name
        // Use the same carbon intensity value from zoneToValue
        // This is built from the same data source as the left panel
        const carbonIntensity = name ? zoneToValue[name] : undefined
        setHoveredZone(name || null, carbonIntensity)
      } else {
        setHoveredZone(null, null)
      }
      
      ;(map as any).__hoveredId = newFeatureId
    } else if (newFeatureId != null) {
      // CRITICAL FIX: Update value even if hovering same zone when data changes
      const name = feature.properties?.zoneName || feature.properties?.name
      const carbonIntensity = name ? zoneToValue[name] : undefined
      const currentValue = (window as any).__currentHoverValue
      if (carbonIntensity !== currentValue) {
        (window as any).__currentHoverValue = carbonIntensity
        setHoveredZone(name || null, carbonIntensity)
      }
    }
  }, [setHover, zoneToValue])

  const onMouseLeave = useCallback(() => {
    const map = mapRef.current?.getMap()
    if (!map) return
    const hoveredId = (map as any).__hoveredId as (string | number | null)
    if (hoveredId != null) setHover(map, hoveredId, false)
    ;(map as any).__hoveredId = null
    ;(window as any).__currentHoverValue = null
    setHoveredZone(null, null)
  }, [setHover])

  const onClick = useCallback((event: any) => {
    const feature = event.features?.[0]
    const name = feature?.properties?.zoneName || feature?.properties?.name
    
    // Increment click counter
    clickCountRef.current++
    const isFirstClick = firstClickAfterLoadRef.current
    
    // Don't allow region selection until map is fully loaded
    if (!isLoadedRef.current) {
      return
    }
    
    // Check if MapLibre is available - detect it directly
    const mlActuallyAvailable = typeof maplibregl !== 'undefined' && maplibregl.LngLatBounds
    
    // Update state if MapLibre is now available but state doesn't reflect it
    if (mlActuallyAvailable && !maplibreglAvailable) {
      setMaplibreglAvailable(true)
    }
    
    // Check if MapLibre is available either from state or direct detection
    if (!mlActuallyAvailable) {
      return
    }
    
    if (name) {
      // Get all sub-regions for this zone (for grouped selection)
      const allSubRegions = getAllSubRegions(name)
      const displayZoneId = getDisplayZoneId(name) // Get parent region ID for display
      
      // IMMEDIATE: Update visual selection (before any navigation or zoom)
      const map = mapRef.current?.getMap()
      if (map && map.getLayer('zones-selected')) {
        // For grouped regions, select all sub-regions together
        if (allSubRegions.length > 1) {
          map.setFilter('zones-selected', ['in', ['coalesce',['get','zoneName'],['get','name']], ['literal', allSubRegions]])
        } else {
          // Single region - use the simple filter
          map.setFilter('zones-selected', ['==', ['coalesce',['get','zoneName'],['get','name']], name])
        }
      }
      
      // IMMEDIATE: Notify parent about selection (opens left panel immediately)
      if (onRegionSelect) {
        // Calculate bounds for the parent to store
        let bounds = null
        if (feature?.geometry && typeof maplibregl !== 'undefined' && maplibregl.LngLatBounds) {
          const boundsObj = new maplibregl.LngLatBounds()
          const coords = feature.geometry.coordinates[0]
          if (Array.isArray(coords)) {
            coords.forEach((coord: number[]) => {
              boundsObj.extend([coord[0], coord[1]] as [number, number])
            })
            bounds = boundsObj
          }
        }
        
        // Use the display zone ID (parent region) for navigation and display
        onRegionSelect(displayZoneId, bounds)
      }
      
      // Cancel any ongoing geolocation to prevent conflicts
      
      if (map) {
        // Immediately mark that a region has been selected to prevent geolocation conflicts
        ;(map as any).__currentSelectedRegion = name
        
        // Mark that user has interacted with the map
        ;(map as any).__userInteracted = true
        
        // Invalidate the current geolocation session
        delete (map as any).__geolocationSession
        
        // Force cancel any geolocation immediately and aggressively
        if ((map as any).__cancelGeolocation) {
          ;(map as any).__cancelGeolocation()
        }
        
        // Also cancel any pending flyTo from geolocation
        if ((map as any).__geolocationFlyTo) {
          clearTimeout((map as any).__geolocationFlyTo)
          delete (map as any).__geolocationFlyTo
        }
        
        // IMMEDIATE zoom to the clicked feature - simplified approach!
        if (feature?.geometry) {
          try {
            // Create bounds using maplibregl directly - we've already verified it's available
            const bounds = new maplibregl.LngLatBounds()
            const coords = feature.geometry.coordinates[0] // Assuming polygon

            if (Array.isArray(coords)) {
              coords.forEach((coord: number[]) => {
                bounds.extend([coord[0], coord[1]] as [number, number])
              })
              
              // CRITICAL: Store bounds in module-level storage BEFORE navigation
              // This persists across component remounts caused by route changes
              persistentZoomState.bounds = bounds
              persistentZoomState.regionName = name
              persistentZoomState.timestamp = Date.now()
              
              // SIMPLIFIED: Just call fitBounds directly - no waiting!
              // The map is already working (selection and panel work), so zoom should work too
              try {
                map.fitBounds(bounds, {
                  padding: 80,
                  duration: 800,
                  maxZoom: 4.5 // Much less zoomed in - shows region without excessive detail
                })
                
                // Save zoom state after animation completes (for restoration after navigation)
                setTimeout(() => {
                  const postZoomCenter = map.getCenter()
                  const postZoomZoom = map.getZoom()
                  
                  // Store the zoom state for restoration after navigation
                  savedZoomStateRef.current = {
                    center: [postZoomCenter.lng, postZoomCenter.lat],
                    zoom: postZoomZoom
                  }
                }, 850) // Save state just after animation completes
              } catch {
                // Silent error handling
              }
            }
          } catch {
            // Silent error handling
          }
        }
      }
      
      // Navigate using React Router - but only for URL update, not for functionality
      // Use the display zone ID (parent region) for the URL
      const qs = searchParams.toString()
      const navigationPath = `/zone/${encodeURIComponent(displayZoneId)}${qs ? `?${qs}` : ''}`
      
      // CRITICAL: Delay navigation to allow zoom animation to complete
      // The fitBounds animation takes 800ms, so we wait before navigating
      // This ensures users see the smooth zoom animation before the route change causes remount
      const ANIMATION_DURATION = 800
      const navigationDelay = map ? ANIMATION_DURATION : 0
      
      // Delay URL update to allow zoom animation to complete visually
      // Parent already knows about selection (panel opens immediately), this is just for URL update
      // CRITICAL FIX: Use replaceState instead of navigate() to prevent React Router remount
      // navigate() would trigger route matching, causing MainView to unmount/remount and lose state
      setTimeout(() => {
        // Use replaceState instead of navigate to avoid triggering React Router remount
        // This updates the URL for shareability without causing component unmount/remount
        window.history.replaceState(null, '', navigationPath)
      }, navigationDelay)
      
      // Mark that first click has been processed
      if (isFirstClick) {
        firstClickAfterLoadRef.current = false
      }
      
      // Don't call updateMapTheme here - let the effect hooks handle it with proper data
      // The selectedRegion effect will trigger the update automatically
    } else {
      // Click on empty area - deselect current region (no navigation, no refresh)
      if (selectedRegion && onDeselect) {
        const map = mapRef.current?.getMap()
        if (map) {
          // Clear the selected region marker
          delete (map as any).__currentSelectedRegion
          
          // Mark that user has interacted with the map
          ;(map as any).__userInteracted = true
        }
        onDeselect()
        
        // Don't call updateMapTheme here - let the effect hooks handle it with proper data
      }
      
      // Mark that first click has been processed even for empty clicks
      if (isFirstClick) {
        firstClickAfterLoadRef.current = false
      }
    }
  }, [navigate, searchParams, selectedRegion, onDeselect, onRegionSelect, zoneToValue, carbonData, timelineState])

  useEffect(() => {
    const map = mapRef.current?.getMap()
    if (!map || !isLoaded) {
      return
    }
    try {
      // For grouped regions, select all sub-regions together
      const allSubRegions = selectedRegion ? getAllSubRegions(selectedRegion) : []
      if (allSubRegions.length > 1) {
        map.setFilter('zones-selected', ['in', ['coalesce',['get','zoneName'],['get','name']], ['literal', allSubRegions]])
      } else {
        map.setFilter('zones-selected', ['==', ['coalesce',['get','zoneName'],['get','name']], selectedRegion || '' ])
      }
      // Force update map theme after selection change to ensure colors persist
      // Use a small delay to ensure the data is ready
      setTimeout(() => {
        updateMapTheme()
      }, 0)
    } catch {
      // Silent error handling
    }
  }, [selectedRegion, isLoaded, updateMapTheme, zoneToValue, carbonData])

  // Center on approximate IP-based geolocation on startup/refresh
  useEffect(() => {
    const map = mapRef.current?.getMap()
    // CRITICAL FIX: Also check persistent state for recently selected region
    // This prevents geolocation from overriding zoom on component remount
    const recentlySelectedRegion = persistentZoomState.regionName &&
                                   (Date.now() - persistentZoomState.timestamp) < 10000
    if (!map || !isLoaded || selectedRegion || recentlySelectedRegion) {
      return // Don't auto-center if a region is already selected or was recently selected
    }
    
    let cancelled = false
    let geolocationTimeoutId: ReturnType<typeof setTimeout> | null = null
    
    // Immediately mark this geolocation session so it can be cancelled
    const sessionId = Math.random().toString(36)
    ;(map as any).__geolocationSession = sessionId

    const flyTo = (lat: number, lon: number) => {
      // More aggressive checks to prevent overriding user interactions
      const currentSelectedRegion = (map as any).__currentSelectedRegion
      const currentSession = (map as any).__geolocationSession
      
      if (!cancelled && !selectedRegion && !currentSelectedRegion && currentSession === sessionId) {
        // Use a timeout that can be cancelled if user interacts
        const timeoutId = setTimeout(() => {
          // Quadruple-check right before executing
          const stillNoSelection = !(map as any).__currentSelectedRegion && !selectedRegion
          const stillValidSession = (map as any).__geolocationSession === sessionId
          const noUserInteraction = !(map as any).__userInteracted
          
          if (!cancelled && stillNoSelection && stillValidSession && noUserInteraction) {
            try { 
              map.flyTo({ center: [lon, lat], zoom: 3, duration: 1500 })
            } catch (e) {
              // Silent error handling
            }
          }
          delete (map as any).__geolocationFlyTo
        }, 100) // Reduced delay for faster cancellation
        
        // Store timeout so it can be cancelled
        ;(map as any).__geolocationFlyTo = timeoutId
      }
    }

    const tryIpApi = async () => {
      try {
        const res = await fetch('https://ipapi.co/json/')
        if (!res.ok) throw new Error('ipapi.co failed')
        const j = await res.json()
        const lat = Number(j.latitude)
        const lon = Number(j.longitude)
        if (!cancelled && Number.isFinite(lat) && Number.isFinite(lon)) {
          // Additional check right before flyTo
          const currentSelectedRegion = (map as any).__currentSelectedRegion
          if (!selectedRegion && !currentSelectedRegion) {
            flyTo(lat, lon)
          }
        }
        return true
      } catch {
        return false
      }
    }

    const tryIpWho = async () => {
      try {
        const res = await fetch('https://ipwho.is/')
        if (!res.ok) throw new Error('ipwho.is failed')
        const j = await res.json()
        const lat = Number(j.latitude)
        const lon = Number(j.longitude)
        if (!cancelled && Number.isFinite(lat) && Number.isFinite(lon)) {
          const currentSelectedRegion = (map as any).__currentSelectedRegion
          if (!selectedRegion && !currentSelectedRegion) {
            flyTo(lat, lon)
          }
        }
      } catch {
        // keep default view
      }
    }

    // Try geolocation after a delay to ensure map is fully loaded
    geolocationTimeoutId = setTimeout(async () => {
      // Triple-check before starting geolocation
      if (!cancelled && !selectedRegion && !(map as any).__currentSelectedRegion) {
        const ok = await tryIpApi()
        if (!ok && !cancelled && !selectedRegion && !(map as any).__currentSelectedRegion) {
          await tryIpWho()
        }
      }
    }, 1000)

    // Store cleanup function on map instance for external cancellation
    ;(map as any).__cancelGeolocation = () => {
      cancelled = true
      if (geolocationTimeoutId) {
        clearTimeout(geolocationTimeoutId)
        geolocationTimeoutId = null
      }
    }

    return () => { 
      cancelled = true
      if (geolocationTimeoutId) {
        clearTimeout(geolocationTimeoutId)
      }
      // Clean up the cancellation function
      if ((map as any).__cancelGeolocation) {
        delete (map as any).__cancelGeolocation
      }
      // Clean up the geolocation session
      delete (map as any).__geolocationSession
    }
  }, [isLoaded, selectedRegion])

  return (
    <div style={{ position:'absolute', inset:0, zIndex: 1, width: '100%', height: '100%' }}>
      <Map
        ref={mapRef}
        mapLib={import('maplibre-gl') as any}
        initialViewState={
          // CRITICAL: If we have persistent bounds from a recent click, start at those coordinates
          // This prevents the visual flash of EU coordinates before restoring to clicked region
          persistentZoomState.bounds && (Date.now() - persistentZoomState.timestamp) < 5000
            ? {
                // Use the center of the bounds as initial view
                longitude: (persistentZoomState.bounds.getWest() + persistentZoomState.bounds.getEast()) / 2,
                latitude: (persistentZoomState.bounds.getSouth() + persistentZoomState.bounds.getNorth()) / 2,
                zoom: 3.5 // Reasonable zoom level for region view
              }
            : { longitude: 6.528, latitude: 50.905, zoom: 2.5 } // Default EU view
        }
        style={{ position:'absolute', inset:0, width: '100%', height: '100%' }}
        mapStyle={mapStyle}
        interactiveLayerIds={interactiveLayerIds}
        cursor="grab"
        dragRotate={false}
        onLoad={onMapLoad}
        onMouseMove={onMouseMove}
        onMouseLeave={onMouseLeave}
        onClick={onClick}
        onMoveStart={() => setMapMoving(true)}
        onMoveEnd={() => setMapMoving(false)}
      />
    </div>
  )
})

MapEM.displayName = 'MapEM'

export default MapEM
