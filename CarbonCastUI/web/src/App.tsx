import './index.css'
import { useEffect, useState, useRef, useMemo } from 'react'
import { Routes, Route, Navigate, useParams, useSearchParams } from 'react-router-dom'
import MapEM, { type MapEMRef } from './components/MapEM'
import Timeline from './components/Timeline'
import { warmCache, initializeCache, useCarbonIntensityData } from './hooks/cache'
import type { TimelineState } from './hooks/cache'
// Removed legacy TopControls/MenuDrawer in favor of EM-style controls
import LegendGlass from './components/LegendGlass'
import InfoPopover from './components/InfoPopover'
// MapLibre migration: remove Leaflet-specific layers
import TopControls from './components/TopControls'
// Sidebar and panels
import AppSidebar from './components/AppSidebar'
import LeftPanelEM from './components/LeftPanelEM'
import DataStatusIndicator, { type FallbackInfo } from './components/DataStatusIndicator'
import { getCurrentUtcDate, getCurrentUtcHour } from './utils/dateUtils'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/map" replace />} />
      <Route path="/map" element={<MainView />} />
      <Route path="/zone/:region" element={<ZoneRoute />} />
    </Routes>
  )
}

function ZoneRoute() {
  const { region } = useParams()
  return <MainView region={region} />
}

function MainView({ region }: { region?: string }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null)
  const [selectedRegionBounds, setSelectedRegionBounds] = useState<any>(null) // Store bounds for zoom restoration
  const [showLeftPanel, setShowLeftPanel] = useState(false)
  const [timelineState, setTimelineState] = useState<TimelineState>({
    mode: 'now',
    date: getCurrentUtcDate(),
    hour: getCurrentUtcHour()
  })
  
  // CRITICAL FIX: State for forcing LeftPanelEM update when date changes
  // This ensures the panel re-renders immediately when a new date is selected (while panel is already open)
  const [leftPanelForceKey, setLeftPanelForceKey] = useState(0)
  
  // Get background loading state and data from the data hook
  // backgroundLoading is TRUE when loading remaining 23 hours in the background
  // loadingProgress tracks 0-100% completion
  const { data: carbonData, backgroundLoading, loadingProgress } = useCarbonIntensityData(timelineState)
  
  // SIMPLIFIED: Just show overlay when backgroundLoading is true
  // This doesn't interfere with progressive loading - map still updates as data arrives
  // The overlay only shows during the full-day background fetch, not the instant priority fetch
  const showLoadingOverlay = backgroundLoading

  // Extract fallback info from the carbon data
  // Primary method: Compare requested date with actual data dates in the response
  // This works even when the API doesn't return explicit fallback_metadata
  // Compute fallback info from carbon data
  // Uses two methods:
  // 1. Explicit metadata from API (overall_fallback flag)
  // 2. Date comparison (if data date != requested date)
  const fallbackInfo = useMemo((): FallbackInfo | null => {
    if (!carbonData) {
      return null
    }
    
    const carbonDataObj = carbonData as Record<string, unknown>
    // Note: dataArray scanning was removed - we only use API-provided metadata for fallback detection now
    // const dataArray = carbonDataObj.data as Array<{ 'UTC time'?: string }> | undefined
    
    // Method 1: Check explicit metadata (if API provides it)
    // PRIORITY: Always use API-provided metadata when available - it has the correct dates
    const metadata = carbonDataObj.metadata as {
      overall_fallback?: boolean
      lifecycle_fallback?: boolean
      direct_fallback?: boolean
      lifecycle_actual_date?: string
      direct_actual_date?: string
      requested_date?: string
    } | undefined
    
    const fallbackMetadata = carbonDataObj.fallback_metadata as {
      lifecycle_fallback?: boolean
      direct_fallback?: boolean
      lifecycle_actual_date?: string
      direct_actual_date?: string
      requested_date?: string
    } | undefined
    
    // STALE GUARD: Check if metadata matches the current requested date
    // Only trust metadata if its requested_date matches what we're asking for
    const metadataExists = metadata !== undefined && metadata !== null
    const metadataHasRequestedDate = metadataExists && typeof metadata?.requested_date === 'string' && metadata.requested_date !== ''
    const metadataMatchesCurrentRequest = metadataHasRequestedDate && metadata!.requested_date === timelineState.date
    
    const fallbackMetadataExists = fallbackMetadata !== undefined && fallbackMetadata !== null
    const fallbackMetadataHasRequestedDate = fallbackMetadataExists && typeof fallbackMetadata?.requested_date === 'string' && fallbackMetadata.requested_date !== ''
    const fallbackMetadataMatchesCurrentRequest = fallbackMetadataHasRequestedDate && fallbackMetadata!.requested_date === timelineState.date
    
    // ONLY use metadata if it explicitly matches the current request
    // This prevents showing stale fallback info from previous date requests
    if (metadataMatchesCurrentRequest && metadata?.overall_fallback && metadata?.lifecycle_actual_date) {
      const actualDate = metadata.lifecycle_actual_date
      const requestedDate = metadata.requested_date!
      return {
        used: true,
        message: `Data from ${actualDate} (requested ${requestedDate})`
      }
    }
    
    // Also check fallback_metadata (some APIs return it separately)
    // Only use if it matches current request
    if (fallbackMetadataMatchesCurrentRequest && (fallbackMetadata?.lifecycle_fallback || fallbackMetadata?.direct_fallback)) {
      const actualDate = fallbackMetadata!.lifecycle_actual_date || fallbackMetadata!.direct_actual_date
      if (actualDate) {
        const requestedDate = fallbackMetadata!.requested_date!
        return {
          used: true,
          message: `Data from ${actualDate} (requested ${requestedDate})`
        }
      }
    }
    
    // Method 2: DISABLED - Only use API-provided metadata for fallback detection
    // Data scanning was causing incorrect banners because:
    // 1. It would scan stale data during date transitions
    // 2. It couldn't distinguish between actual fallback and intermediate states
    // The API now provides proper fallback_metadata with requested_date, so we rely on that
    
    // If metadata exists but doesn't indicate fallback, explicitly return null
    // This ensures we don't show banner when API says no fallback
    if (metadataMatchesCurrentRequest && metadata?.overall_fallback === false) {
      return null
    }
    
    // No metadata match for current request - wait for data to arrive
    return null
  }, [carbonData, timelineState.date, timelineState.mode, timelineState.hour])

  // Track previous timeline state for debugging
  const prevTimelineStateRef = useRef<TimelineState | null>(null)
  
  // 🔴🔴🔴 Store previous date to detect actual changes
  const prevDateRef = useRef<string>(timelineState.date)
  
  // CRITICAL FIX: Watch for timelineState.date changes and force LeftPanelEM refresh
  // This ensures the panel updates immediately when user selects a new date while panel is open
  useEffect(() => {
    const prevDate = prevDateRef.current
    
    // Only increment if date actually changed (not on initial mount with same date)
    if (prevDate !== timelineState.date) {
      setLeftPanelForceKey(prev => prev + 1)
    }
    
    prevDateRef.current = timelineState.date
  }, [timelineState.date])
  
  // SIMPLIFIED: Just pass state changes through
  // backgroundLoading from cache hook handles showing/hiding the overlay automatically
  const handleTimelineChange = (newState: TimelineState) => {
    setTimelineState(newState)
  }

  // Refs for map control
  const mapRef = useRef<MapEMRef>(null)
  const mapLibreRef = useRef<any>(null)
  
  // Create a stable ref object for TopControls
  useEffect(() => {
    if (mapRef.current) {
      mapLibreRef.current = mapRef.current.getMapRef()
    }
  })
  
  // Theme is now applied in the useTheme hook itself

  // Removed problematic redirect logic that was causing UI refresh
  // Zone routes should be handled normally without forced redirects
  // legacy menu removed
  // const [mlMap, setMlMap] = useState<any>(null)

  // Sync selected region with URL param - only when navigating TO a region via direct URL
  // This effect should NOT reset state when region is undefined, because:
  // 1. When using replaceState (instead of navigate), React Router doesn't update the region prop
  // 2. The panel visibility is controlled by handleRegionSelect/handleDeselect for user interactions
  // 3. We only want this effect to handle the case of direct URL navigation to /zone/:region
  useEffect(() => {
    if (region) {
      // User navigated directly to /zone/:region URL - sync state from URL
      setSelectedRegion(region)
      setShowLeftPanel(true)
    }
    // Intentionally NOT resetting state when region is undefined
    // User interactions (clicks) control the panel via handleRegionSelect/handleDeselect
  }, [region])

  // Handle deselection without any navigation - pure state update
  const handleDeselect = () => {
    setSelectedRegion(null)
    setSelectedRegionBounds(null) // Clear bounds on deselect
    setShowLeftPanel(false)  // Hide panel immediately
    // Update URL directly without navigation to avoid any refresh behavior
    const qs = searchParams.toString()
    const newUrl = `/map${qs ? `?${qs}` : ''}`
    window.history.replaceState(null, '', newUrl)
  }
  
  // Handle region selection - opens panel immediately and stores bounds for zoom restoration
  const handleRegionSelect = (region: string, bounds?: any) => {
    setSelectedRegion(region)
    if (bounds) {
      setSelectedRegionBounds(bounds)
    }
    setShowLeftPanel(true)  // Open panel immediately on click!
    // Navigation to update URL happens inside MapEM
  }

  // Initialize timeline state from URL params on mount
  useEffect(() => {
    const mode = (searchParams.get('mode') as TimelineState['mode']) || undefined
    const date = searchParams.get('date') || undefined
    const hourParam = searchParams.get('hour')
    const hour = hourParam != null ? Number(hourParam) : undefined

    setTimelineState((prev) => ({
      mode: mode ?? prev.mode,
      date: date ?? prev.date,
      hour: hour != null && !Number.isNaN(hour) ? hour : prev.hour
    }))
    // run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Debounce ONLY URL updates to prevent browser crashes (100 replaceState per 10s limit)
  // Data updates remain instant
  const urlUpdateTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  
  useEffect(() => {
    prevTimelineStateRef.current = { ...timelineState }
    
    // Clear any pending URL update
    if (urlUpdateTimerRef.current) {
      clearTimeout(urlUpdateTimerRef.current)
    }
    
    // Small debounce just for URL to prevent browser security error
    // Data updates are still instant - this only affects the URL bar
    urlUpdateTimerRef.current = setTimeout(() => {
      const current = new URLSearchParams(searchParams)
      current.set('mode', timelineState.mode)
      current.set('date', timelineState.date)
      current.set('hour', String(timelineState.hour))
      setSearchParams(current, { replace: true })
    }, 100) // 100ms debounce for URL only - prevents browser crash
    
    // Cleanup timer on unmount
    return () => {
      if (urlUpdateTimerRef.current) {
        clearTimeout(urlUpdateTimerRef.current)
      }
    }
  }, [timelineState.mode, timelineState.date, timelineState.hour, searchParams, setSearchParams])

  // Initialize cache on app startup - clear corrupted entries and then warm cache
  useEffect(() => {
    initializeCache()  // Clean up and initialize localStorage
    warmCache()         // Prefetch common data
  }, [])

  // No side panel; clicks handled inside MapEM

  // Map now spans full width; left panel overlays like EM

  return (
    <div style={{ position: 'fixed', inset: 0, overflow: 'hidden' }}>
      {/* App Sidebar - Electricity Maps style vertical navigation */}
      <AppSidebar />
      
      {/* Main content area - adjusted for sidebar */}
      <div style={{
        position: 'absolute',
        left: window.innerWidth >= 768 ? '63px' : '0',
        right: 0,
        top: 0,
        bottom: 0,
        transition: 'left 0.3s ease'
      }}>
        {/* Map layer - should be visible */}
        <MapEM
          ref={mapRef}
          selectedRegion={selectedRegion}
          selectedRegionBounds={selectedRegionBounds}
          onDeselect={handleDeselect}
          onRegionSelect={handleRegionSelect}
          timelineState={timelineState}
        />

        {/* Timeline is self-positioned (fixed) - date button is DISABLED in "now" mode */}
        {/* Click "Past" or "Future" first, then the date button becomes clickable */}
        {/* Timeline is locked while background data loads - shows loading overlay with progress */}
        <Timeline
          timelineState={timelineState}
          onTimelineChange={handleTimelineChange}
          isLocked={showLoadingOverlay}
          loadingProgress={loadingProgress}
          loadingMessage="Loading data for all regions..."
        />

        <InfoPopover timelineState={timelineState} />
        <LegendGlass />
        
        {/* Data status indicator - shows when fallback data is being used */}
        <DataStatusIndicator fallbackInfo={fallbackInfo} />
        
        {/* Top controls with theme toggle and zoom - positioned to avoid overlaps */}
        <TopControls mapRef={mapLibreRef} />

        {/* LeftPanel (EM-style) opens when a region is selected */}
        {/* Render structural EM left panel; content placeholders inside */}
        {/* Pass selectedRegion as prop because replaceState doesn't update React Router's useParams() */}
        {/* CRITICAL FIX: Pass carbonData from App to avoid multiple hook instances with separate state */}
        {/* This ensures the panel gets the same data as the map instantly */}
        {showLeftPanel && selectedRegion && (
          <LeftPanelEM
            key={`${selectedRegion}-${leftPanelForceKey}`}
            onClose={handleDeselect}
            timelineState={timelineState}
            region={selectedRegion}
          />
        )}
      </div>
    </div>
  )
}

export default App
