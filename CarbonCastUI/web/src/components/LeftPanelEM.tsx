import React, { useMemo, memo, useCallback } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import Logo from './Logo'
import { useEnergyMix, useCarbonIntensityHistory } from '../hooks/useEnergyData'
import { type TimelineState, useCarbonIntensityData } from '../hooks/cache'
import { getRegionDisplayName, convertToApiRegionCode, getDisplayZoneId } from '../utils/regionMapping'
import { setHoveredZone } from './InfoPopover'
import { getCurrentUtcDate, getCurrentUtcHour } from '../utils/dateUtils'
// Extract defaultTimelineState to prevent object recreation
const defaultTimelineState: TimelineState = {
  mode: 'now',
  date: getCurrentUtcDate(),
  hour: getCurrentUtcHour()
}

// Separate component for carbon intensity value display
// The hook now auto-syncs with cache, so we just use the hook directly
const CarbonIntensityValue = ({ regionCode, timelineState }: {
  regionCode: string;
  timelineState?: TimelineState;
}) => {
  const currentTimelineState = timelineState || defaultTimelineState
  
  // Call hook - it now has built-in cache sync, and use loading state
  const { data: carbonData, loading } = useCarbonIntensityData(currentTimelineState)
  
  // Get data array from hook
  const dataArray = Array.isArray(carbonData?.data) ? carbonData.data as Array<Record<string, unknown>> : null
  
  // COMPUTE VALUE DIRECTLY from hook data
  let displayValue: number | null = null
  let isDataAvailable = false
  let regionFound = false
  
  // Data is available if we have an array (even if empty) - this means the API responded
  if (dataArray !== null) {
    isDataAvailable = true
  }
  
  if (dataArray && dataArray.length > 0 && regionCode) {
    const apiRegionCode = convertToApiRegionCode(regionCode)
    const regionRow = dataArray.find((row) => row.region_code === apiRegionCode)
    
    if (regionRow) {
      regionFound = true
      if (currentTimelineState.mode === 'future') {
        displayValue = (regionRow.forecasted_avg_carbon_intensity_direct ||
                 regionRow.carbon_intensity_avg_direct ||
                 regionRow.carbon_intensity ||
                 null) as number | null
      } else {
        displayValue = (regionRow.carbon_intensity_avg_direct ||
                 regionRow.carbon_intensity ||
                 null) as number | null
      }
    }
  }
  
  // Helper function to get intensity level and color with theme awareness
  const getIntensityLevel = useCallback((val: number) => {
    const isDark = document.documentElement.classList.contains('dark')
    
    if (val < 100) return { label: 'Very Low', color: isDark ? '#22c55e' : '#16a34a' }
    if (val < 200) return { label: 'Low', color: isDark ? '#86efac' : '#65a30d' }
    if (val < 300) return { label: 'Moderate', color: isDark ? '#ffd700' : '#ca8a04' }
    if (val < 400) return { label: 'High', color: isDark ? '#fb923c' : '#ea580c' }
    return { label: 'Very High', color: isDark ? '#f87171' : '#dc2626' }
  }, [])
  
  // Determine what message to show when there's no display value
  // Priority: 1. Still loading, 2. Data loaded but empty/region not found
  if (displayValue === null || displayValue === undefined) {
    let statusMessage = 'Loading...'
    
    // If not loading and data has been fetched (even if empty), show appropriate message
    if (!loading && isDataAvailable) {
      if (currentTimelineState.mode === 'future') {
        statusMessage = 'No forecast data available'
      } else if (!regionFound && dataArray && dataArray.length > 0) {
        statusMessage = 'Region not available'
      } else {
        statusMessage = 'No data available'
      }
    }
    
    return (
      <span style={{ fontSize: '0.875rem', color: 'var(--muted)', marginTop: '0.25rem', position: 'relative', fontWeight: 500 }}>
        {statusMessage}
      </span>
    )
  }
  
  // At this point displayValue is guaranteed to be non-null
  const intensityColor = getIntensityLevel(displayValue).color
  const renderedText = `${Math.round(displayValue)} gCO₂eq/kWh`
  
  return (
    <span
      data-testid="carbon-intensity-value"
      data-value={Math.round(displayValue)}
      style={{ fontSize: '0.875rem', color: intensityColor, marginTop: '0.25rem', position: 'relative', fontWeight: 500 }}
    >
      {renderedText}
    </span>
  )
}
CarbonIntensityValue.displayName = 'CarbonIntensityValue'

function MapMobileHeader() {
  return (
    <div style={{
      display: 'flex',
      width: '100%',
      alignItems: 'center',
      justifyContent: 'space-between',
      background: 'linear-gradient(to bottom, rgba(0,0,0,0.6), transparent)',
      paddingBottom: '1rem',
      paddingLeft: '0.75rem',
      paddingTop: 'max(0.75rem, env(safe-area-inset-top))'
    }}>
      <Logo />
    </div>
  )
}

const OuterPanel = memo(({ children }: { children: React.ReactNode }) => {
  const location = useLocation()
  const isMapRoute = location.pathname.startsWith('/map')
  
  return (
    <>
      <div style={{
        pointerEvents: 'none',
        position: 'absolute',
        left: 0,
        right: 0,
        top: 0,
        zIndex: 20,
        display: window.innerWidth < 640 ? 'block' : 'none'
      }}>
        <MapMobileHeader />
      </div>
      <div
        data-testid="left-panel"
        style={{
          pointerEvents: 'none',
          position: 'absolute',
          inset: 0,
          zIndex: 10,
          width: window.innerWidth >= 640 ? 'calc(13vw + 15rem)' : '100%',
          display: isMapRoute ? (window.innerWidth >= 640 ? 'flex' : 'none') : (window.innerWidth >= 640 ? 'flex' : 'block')
        }}
      >
        {children}
      </div>
    </>
  )
})
OuterPanel.displayName = 'OuterPanel'

// ZoneHeader component - CarbonIntensityValue calls hook directly
const ZoneHeader = ({ zoneId, onClose, timelineState }: {
  zoneId: string;
  onClose?: () => void;
  timelineState?: TimelineState;
}) => {
  const handleClose = useCallback(() => {
    if (onClose) {
      onClose()
    }
  }, [onClose])

  // Get the display zone ID (parent region for grouped zones like SE-SE1 -> SE)
  const displayZoneId = useMemo(() => getDisplayZoneId(zoneId), [zoneId])
  const displayName = useMemo(() => getRegionDisplayName(displayZoneId), [displayZoneId])

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '0.75rem 1.25rem',  // Reduced top/bottom padding
      paddingTop: '0.75rem',  // Reduced top padding
      borderBottom: '1px solid var(--panelBorder)',
      backgroundColor: 'var(--panelBg)',
      backdropFilter: 'blur(30px) saturate(200%)',
      WebkitBackdropFilter: 'blur(30px) saturate(200%)',
      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
      margin: 0,
      marginTop: 0,  // No top margin - header must be flush with top
      marginBottom: 0,  // Ensure no margin at bottom
      position: 'sticky',  // Make header sticky
      top: 0,  // Stick to the very top of the container
      zIndex: 1  // Ensure it stays above scrolling content
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.75rem',
        minWidth: 0,
        flex: 1
      }}>
        {/* Back button */}
        <button
          onClick={handleClose}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '36px',
            height: '36px',
            borderRadius: '12px',
            border: '1px solid var(--panelBorder)',
            background: 'var(--buttonBg)',
            color: 'var(--panelText)',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
            boxShadow: '0 2px 8px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.05)'
          }}
          aria-label="Back to map"
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--buttonBgHover)'
            e.currentTarget.style.transform = 'scale(1.05)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'var(--buttonBg)'
            e.currentTarget.style.transform = 'scale(1)'
          }}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            display: 'flex',
            alignItems: 'baseline',
            gap: '0.5rem',
            marginBottom: '0.125rem'
          }}>
            <span style={{
              fontSize: '1.375rem',
              fontWeight: 700,
              lineHeight: 1.2,
              color: 'var(--panelText)',
              letterSpacing: '-0.01em'
            }}>
              {displayZoneId}
            </span>
            <span style={{
              fontSize: '0.875rem',
              fontWeight: 500,
              color: 'var(--subText)', // Use subText for better contrast
              opacity: 0.9
            }}>
              {displayName}
            </span>
          </div>
          <CarbonIntensityValue
            regionCode={displayZoneId}
            timelineState={timelineState}
          />
        </div>
      </div>
      
      {/* Share and more actions */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem'
      }}>
        <button
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '32px',
            height: '32px',
            borderRadius: '8px',
            border: 'none',
            background: 'var(--buttonBg)',
            color: 'var(--muted)',
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
          aria-label="Share"
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'var(--buttonBgHover)'
            e.currentTarget.style.transform = 'scale(1.05)'
            e.currentTarget.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.1)'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'var(--buttonBg)'
            e.currentTarget.style.transform = 'scale(1)'
            e.currentTarget.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.05)'
          }}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="18" cy="5" r="3" />
            <circle cx="6" cy="12" r="3" />
            <circle cx="18" cy="19" r="3" />
            <path d="M8.59 13.51l6.83 3.98M15.41 6.51l-6.82 3.98" />
          </svg>
        </button>
      </div>
    </div>
  )
}
ZoneHeader.displayName = 'ZoneHeader'

const DisplayByEmissionToggle = memo(() => {
  return (
    <div style={{
      marginBottom: '0.75rem',  // Reduced from 1.5rem to 0.75rem
      display: 'inline-flex',
      alignItems: 'center',
      padding: '4px',
      borderRadius: '28px',
      backgroundColor: 'var(--toggleInactiveBg)',
      backdropFilter: 'blur(24px) saturate(200%)',
      WebkitBackdropFilter: 'blur(24px) saturate(200%)',
      border: '1px solid var(--panelBorder)',
      boxShadow: 'inset 0 2px 4px rgba(0, 0, 0, 0.1), 0 1px 2px rgba(0, 0, 0, 0.05)'
    }}>
      <button style={{
        borderRadius: '24px',
        backgroundColor: 'var(--toggleActiveBg)',
        padding: '0.5rem 1.25rem',
        fontSize: '0.875rem',
        fontWeight: 600,
        color: 'var(--panelText)',
        border: 'none',
        cursor: 'pointer',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
        boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15), 0 2px 4px rgba(0, 0, 0, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.1)'
      }}>Electricity</button>
      <button style={{
        borderRadius: '24px',
        backgroundColor: 'transparent',
        padding: '0.5rem 1.25rem',
        fontSize: '0.875rem',
        fontWeight: 500,
        color: 'var(--muted)',
        border: 'none',
        cursor: 'pointer',
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)'
      }}>Emissions</button>
    </div>
  )
})
DisplayByEmissionToggle.displayName = 'DisplayByEmissionToggle'

// Bar chart constants (inspired by electricitymaps - matching their constants.ts)
const BAR_CONSTANTS = {
  LABEL_MAX_WIDTH: 110,      // Space for icon + label
  ROW_HEIGHT: 14,            // Height of each bar row (electricitymaps uses 13)
  PADDING_Y: 6,              // Vertical padding between rows (electricitymaps uses 7)
  PADDING_X: 20,             // Horizontal padding (electricitymaps uses 25)
  X_AXIS_HEIGHT: 22,         // Height for the axis
  RECT_OPACITY: 0.85,        // Bar opacity
  SCALE_TICKS: 4,            // Number of axis ticks
  ICON_SIZE: 14,             // Icon size
  TEXT_ADJUST_Y: 11,         // Text vertical adjustment
}

// Production source legend icon (inspired by electricitymaps ProductionSourceLegend)
const ProductionSourceLegend = memo(({ mode, color }: { mode: string; color: string }) => {
  return (
    <svg width={BAR_CONSTANTS.ICON_SIZE} height={BAR_CONSTANTS.ICON_SIZE}>
      <rect
        x={0}
        y={0}
        width={BAR_CONSTANTS.ICON_SIZE}
        height={BAR_CONSTANTS.ICON_SIZE}
        rx={3}
        fill={color}
        opacity={0.9}
      />
      {/* Inner icon based on source type */}
      <g transform="translate(2, 2)">
        {mode === 'solar' && (
          <circle cx={5} cy={5} r={3} fill="none" stroke="white" strokeWidth="1.2" />
        )}
        {mode === 'wind' && (
          <path d="M5 1 L5 9 M2 5 Q5 3 8 5" fill="none" stroke="white" strokeWidth="1.2" />
        )}
        {mode === 'hydro' && (
          <path d="M2 5 Q5 2 8 5 Q5 8 2 5" fill="none" stroke="white" strokeWidth="1.2" />
        )}
        {mode === 'nuclear' && (
          <>
            <circle cx={5} cy={5} r={3.5} fill="none" stroke="white" strokeWidth="1.2" />
            <circle cx={5} cy={5} r={1} fill="white" />
          </>
        )}
        {mode === 'coal' && (
          <rect x={2} y={2} width={6} height={6} rx={1} fill="none" stroke="white" strokeWidth="1.2" />
        )}
        {(mode === 'natural gas' || mode === 'nat_gas') && (
          <path d="M5 2 Q8 5 5 8 Q2 5 5 2" fill="none" stroke="white" strokeWidth="1.2" />
        )}
        {mode === 'oil' && (
          <ellipse cx={5} cy={5} rx={2.5} ry={3.5} fill="none" stroke="white" strokeWidth="1.2" />
        )}
        {mode === 'biomass' && (
          <path d="M5 8 L5 5 M3 5 Q5 2 7 5" fill="none" stroke="white" strokeWidth="1.2" />
        )}
        {mode === 'geothermal' && (
          <path d="M2 8 Q3 5 5 2 Q7 5 8 8" fill="none" stroke="white" strokeWidth="1.2" />
        )}
        {mode === 'other' && (
          <circle cx={5} cy={5} r={2.5} fill="none" stroke="white" strokeWidth="1.2" />
        )}
      </g>
    </svg>
  )
})
ProductionSourceLegend.displayName = 'ProductionSourceLegend'

// Horizontal bar component (inspired by electricitymaps HorizontalBar)
const HorizontalBar = memo(({
  value,
  maxValue,
  color,
  barAreaWidth
}: {
  value: number;
  maxValue: number;
  color: string;
  barAreaWidth: number;
}) => {
  const barWidth = maxValue > 0 ? Math.max(0, (value / maxValue) * barAreaWidth) : 0
  
  if (barWidth <= 0) return null
  
  return (
    <rect
      className="pointer-events-none"
      x={BAR_CONSTANTS.LABEL_MAX_WIDTH}
      y={0}
      width={barWidth}
      height={BAR_CONSTANTS.ROW_HEIGHT}
      fill={color}
      opacity={BAR_CONSTANTS.RECT_OPACITY}
      shapeRendering="crispEdges"
      rx={1}
    />
  )
})
HorizontalBar.displayName = 'HorizontalBar'

// Production source row (inspired by electricitymaps ProductionSourceRow)
const ProductionSourceRow = memo(({
  source,
  index,
  maxValue,
  barAreaWidth,
  onMouseOver,
  onMouseOut
}: {
  source: { name: string; value: number; percentage: number; color: string };
  index: number;
  maxValue: number;
  barAreaWidth: number;
  onMouseOver?: (source: string) => void;
  onMouseOut?: () => void;
}) => {
  const yOffset = index * (BAR_CONSTANTS.ROW_HEIGHT + BAR_CONSTANTS.PADDING_Y)
  const barEndX = BAR_CONSTANTS.LABEL_MAX_WIDTH + (maxValue > 0 ? (source.value / maxValue) * barAreaWidth : 0)
  const sourceName = source.name.toLowerCase().replace(' ', '_')
  
  return (
    <g
      transform={`translate(0, ${yOffset})`}
      onMouseEnter={() => onMouseOver?.(source.name)}
      onMouseLeave={onMouseOut}
      style={{ cursor: 'pointer' }}
    >
      {/* Row hover background */}
      <rect
        x={0}
        y={-1}
        width={barAreaWidth + BAR_CONSTANTS.LABEL_MAX_WIDTH + 50}
        height={BAR_CONSTANTS.ROW_HEIGHT + 2}
        fill="transparent"
        className="hover:fill-[var(--rowHoverBg)]"
      />
      
      {/* Source icon */}
      <ProductionSourceLegend mode={sourceName} color={source.color} />
      
      {/* Source name */}
      <text
        x={BAR_CONSTANTS.ICON_SIZE + 6}
        y={BAR_CONSTANTS.TEXT_ADJUST_Y}
        fontSize="12"
        fill="var(--panelText)"
        fontWeight="500"
        className="pointer-events-none select-none"
      >
        {source.name}
      </text>
      
      {/* Horizontal bar */}
      <HorizontalBar
        value={source.value}
        maxValue={maxValue}
        color={source.color}
        barAreaWidth={barAreaWidth}
      />
      
      {/* Value and percentage at end of bar */}
      <text
        x={barEndX + 6}
        y={BAR_CONSTANTS.TEXT_ADJUST_Y}
        fontSize="11"
        fill="var(--subText)"
        fontWeight="500"
        className="pointer-events-none select-none"
      >
        {source.value >= 1000
          ? `${(source.value / 1000).toFixed(1)} GW`
          : `${source.value.toFixed(0)} MW`
        }
        <tspan fill="var(--muted)" dx="4">({source.percentage.toFixed(0)}%)</tspan>
      </text>
    </g>
  )
})
ProductionSourceRow.displayName = 'ProductionSourceRow'

// Axis component (inspired by electricitymaps Axis)
const BarChartAxis = memo(({
  maxValue,
  barAreaWidth,
  chartHeight
}: {
  maxValue: number;
  barAreaWidth: number;
  chartHeight: number;
}) => {
  // Generate nice round tick values - only 3 ticks for better readability
  const generateNiceTicks = (max: number): number[] => {
    if (max <= 0) return [0]
    
    // Find a nice round step value
    const magnitude = Math.pow(10, Math.floor(Math.log10(max)))
    const normalized = max / magnitude
    
    let step: number
    if (normalized <= 2) {
      step = magnitude * 0.5
    } else if (normalized <= 5) {
      step = magnitude
    } else {
      step = magnitude * 2
    }
    
    // Generate ticks from 0 up to max
    const ticks: number[] = [0]
    let tick = step
    while (tick < max * 0.95) { // Stop before getting too close to max
      ticks.push(tick)
      tick += step
    }
    
    return ticks
  }
  
  const ticks = generateNiceTicks(maxValue)
  
  // Compact format - just show numbers, unit shown in header
  const formatValue = (val: number): string => {
    if (val === 0) return '0'
    if (val >= 1000) {
      const gw = val / 1000
      return gw >= 10 ? `${Math.round(gw)}` : `${gw.toFixed(1)}`
    }
    return `${Math.round(val)}`
  }
  
  // Determine unit label based on scale
  const unitLabel = maxValue >= 1000 ? 'GW' : 'MW'
  
  return (
    <g transform={`translate(${BAR_CONSTANTS.LABEL_MAX_WIDTH}, 0)`}>
      {/* Unit label at the end */}
      <text
        x={barAreaWidth + 8}
        y={-6}
        fontSize="9"
        fill="var(--muted)"
        textAnchor="start"
        className="select-none"
        opacity={0.7}
      >
        {unitLabel}
      </text>
      
      {/* Vertical grid lines and tick labels */}
      {ticks.map((tick, i) => {
        const x = maxValue > 0 ? (tick / maxValue) * barAreaWidth : 0
        return (
          <g key={i} transform={`translate(${x}, 0)`}>
            {/* Vertical grid line */}
            <line
              y1={0}
              y2={chartHeight}
              stroke="var(--panelBorder)"
              strokeWidth={1}
              strokeDasharray={i === 0 ? "none" : "3,3"}
              opacity={i === 0 ? 0.8 : 0.4}
            />
            {/* Tick label at top */}
            <text
              y={-6}
              fontSize="10"
              fill="var(--muted)"
              textAnchor="middle"
              className="select-none"
            >
              {formatValue(tick)}
            </text>
          </g>
        )
      })}
    </g>
  )
})
BarChartAxis.displayName = 'BarChartAxis'

// Update electricity mix when data changes - responds to hour changes for timeline slider
const ElectricityMixCard = ({ regionCode, timelineState }: { regionCode: string; timelineState?: TimelineState }) => {
  // Use the actual timelineState including hour for real-time updates as user slides timeline
  const { data: energySources, total, loading, error } = useEnergyMix(regionCode, timelineState)
  
  // Calculate chart dimensions
  const containerRef = React.useRef<HTMLDivElement>(null)
  const [containerWidth, setContainerWidth] = React.useState(300)
  
  React.useEffect(() => {
    if (containerRef.current) {
      const resizeObserver = new ResizeObserver((entries) => {
        for (const entry of entries) {
          setContainerWidth(entry.contentRect.width)
        }
      })
      resizeObserver.observe(containerRef.current)
      return () => resizeObserver.disconnect()
    }
  }, [])
  
  // Filter out only "No data available" entries - show all sources including zeros
  const validSources = energySources.filter(s => s.name !== 'No data available' && s.name !== 'Data unavailable')
  const maxValue = Math.max(...validSources.map(s => s.value), 0)
  const barAreaWidth = Math.max(0, containerWidth - BAR_CONSTANTS.LABEL_MAX_WIDTH - BAR_CONSTANTS.PADDING_X - 80) // Extra space for value labels
  const chartHeight = validSources.length * (BAR_CONSTANTS.ROW_HEIGHT + BAR_CONSTANTS.PADDING_Y)

  return (
    <div
      ref={containerRef}
      style={{
        borderRadius: '16px',
        border: '1px solid var(--panelBorder)',
        backgroundColor: 'var(--cardBg)',
        backdropFilter: 'blur(40px) saturate(200%)',
        WebkitBackdropFilter: 'blur(40px) saturate(200%)',
        padding: '1.25rem',
        marginBottom: '1.25rem',
        boxShadow: '0 12px 48px rgba(0, 0, 0, 0.12), 0 4px 16px rgba(0, 0, 0, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
        position: 'relative',
        overflow: 'hidden'
      }}
    >
      {/* Subtle gradient overlay */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: '80px',
        background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.03) 0%, transparent 100%)',
        pointerEvents: 'none'
      }} />
      
      <div style={{
        marginBottom: '1rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'relative'
      }}>
        <h3 style={{
          fontSize: '1rem',
          fontWeight: 700,
          color: 'var(--panelText)',
          letterSpacing: '-0.01em',
          opacity: 1
        }}>Electricity mix</h3>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem'
        }}>
          <span style={{
            fontSize: '0.8rem',
            color: 'var(--subText)',
            fontWeight: 600,
            opacity: 0.9
          }}>
            {total ? `${(total / 1000).toFixed(1)} GW` : '—'}
          </span>
        </div>
      </div>
      
      {loading && (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>
          Loading...
        </div>
      )}
      
      {error && (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>
          {error}
        </div>
      )}
      
      {!loading && !error && validSources.length > 0 && (
        <svg
          width="100%"
          height={chartHeight + BAR_CONSTANTS.X_AXIS_HEIGHT + 10}
          style={{ overflow: 'visible' }}
        >
          {/* Axis with tick marks */}
          <BarChartAxis
            maxValue={maxValue}
            barAreaWidth={barAreaWidth}
            chartHeight={chartHeight}
          />
          
          {/* Energy source rows */}
          <g transform={`translate(0, ${BAR_CONSTANTS.X_AXIS_HEIGHT})`}>
            {validSources.map((source, index) => (
              <ProductionSourceRow
                key={source.name}
                source={source}
                index={index}
                maxValue={maxValue}
                barAreaWidth={barAreaWidth}
              />
            ))}
          </g>
        </svg>
      )}
      
      {!loading && !error && validSources.length === 0 && (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>
          No data available
        </div>
      )}
    </div>
  )
}
ElectricityMixCard.displayName = 'ElectricityMixCard'

// Update chart when data changes - NO MEMO to ensure re-renders
const CarbonIntensityChart = ({ regionCode, timelineState }: { regionCode: string; timelineState?: TimelineState }) => {
  // Create a stable timeline state that only changes on date/mode changes
  const stableTimelineState = useMemo(() => ({
    ...timelineState,
    hour: 12 // Use fixed hour so it doesn't re-fetch on hour changes
  }), [timelineState?.mode, timelineState?.date])
  
  const { actual, forecast, loading, error } = useCarbonIntensityHistory(regionCode, stableTimelineState as TimelineState)
  
  // Track if loading is taking too long (likely means no data)
  const [loadingTimeout, setLoadingTimeout] = React.useState(false)
  
  React.useEffect(() => {
    if (loading) {
      const timer = setTimeout(() => {
        setLoadingTimeout(true)
      }, 3000) // 3 seconds timeout
      return () => clearTimeout(timer)
    } else {
      setLoadingTimeout(false)
    }
  }, [loading])
  
  const maxValue = useMemo(() => {
    const allValues = [...actual.map(d => d.value), ...forecast.map(d => d.value)]
    return Math.max(700, Math.ceil(Math.max(...allValues) / 100) * 100)
  }, [actual, forecast])

  // Determine if we truly have no data
  const hasNoData = (!loading && actual.length === 0 && forecast.length === 0) ||
                    (loading && loadingTimeout) ||
                    error?.includes('No data available')

  return (
    <div style={{
      borderRadius: '16px',
      border: '1px solid var(--panelBorder)',
      backgroundColor: 'var(--cardBg)',
      backdropFilter: 'blur(40px) saturate(200%)',
      WebkitBackdropFilter: 'blur(40px) saturate(200%)',
      padding: '1.75rem',
      marginBottom: '1.25rem',
      boxShadow: '0 12px 48px rgba(0, 0, 0, 0.12), 0 4px 16px rgba(0, 0, 0, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
      position: 'relative',
      overflow: 'hidden'
    }}>
      <div style={{
        marginBottom: '1rem',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <h3 style={{
          fontSize: '1rem',
          fontWeight: 700, // Increase weight for better contrast
          color: 'var(--panelText)',
          letterSpacing: '-0.01em',
          opacity: 1 // Ensure full opacity
        }}>{
          // In Historical mode the chart compares what actually happened vs the
          // forecast that had been made for that day; in other modes it's a
          // straight forecast view.
          timelineState?.mode === 'past' ? 'Actual vs. Past Forecast' : 'Carbon Intensity Forecast'
        }</h3>
      </div>
      
      {loading && !loadingTimeout && (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>
          Loading...
        </div>
      )}
      
      {error && !hasNoData && (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>
          {error}
        </div>
      )}
      
      {hasNoData && (
        <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--muted)' }}>
          No data available
        </div>
      )}
      
      {!hasNoData && !loading && !error && (actual.length > 0 || forecast.length > 0) && (
        <div style={{
          height: '200px',
          position: 'relative',
          padding: '0.5rem'
        }}>
          {/* Simple line chart visualization */}
          <svg width="100%" height="100%" viewBox="0 0 300 180">
            {/* Grid lines */}
            {[0, 1, 2, 3, 4].map(i => (
              <line
                key={i}
                x1="30"
                y1={i * 40}
                x2="280"
                y2={i * 40}
                stroke="var(--panelBorder)"
                strokeWidth="1"
                strokeDasharray="2,2"
              />
            ))}
            
            {/* Actual data line */}
            {actual.length > 0 && (
              <polyline
                fill="none"
                stroke="#3B82F6"
                strokeWidth="2"
                points={actual.map((d, i) => {
                  const x = 30 + (i * 250 / 24)
                  const y = 160 - (d.value / maxValue * 160)
                  return `${x},${y}`
                }).join(' ')}
              />
            )}
            
            {/* Forecast data line */}
            {forecast.length > 0 && (
              <polyline
                fill="none"
                stroke="#EF4444"
                strokeWidth="2"
                strokeDasharray="5,5"
                points={forecast.map((d, i) => {
                  const x = 30 + (i * 250 / 24)
                  const y = 160 - (d.value / maxValue * 160)
                  return `${x},${y}`
                }).join(' ')}
              />
            )}
            
            {/* Y-axis labels */}
            <text x="25" y="5" fontSize="10" fill="var(--subText)" textAnchor="end">{maxValue}</text>
            <text x="25" y="165" fontSize="10" fill="var(--subText)" textAnchor="end">0</text>
            
            {/* X-axis labels */}
            <text x="30" y="175" fontSize="10" fill="var(--subText)">0h</text>
            <text x="155" y="175" fontSize="10" fill="var(--subText)" textAnchor="middle">12h</text>
            <text x="280" y="175" fontSize="10" fill="var(--subText)" textAnchor="end">24h</text>
          </svg>
          
          {/* Legend */}
          <div style={{
            display: 'flex',
            justifyContent: 'center',
            gap: '1rem',
            marginTop: '0.5rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <div style={{ width: '20px', height: '2px', backgroundColor: '#3B82F6' }} />
              <span style={{ fontSize: '0.75rem', color: 'var(--subText)', fontWeight: 500 }}>Actual</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
              <div style={{ width: '20px', height: '2px', backgroundColor: '#EF4444', borderTop: '2px dashed #EF4444' }} />
              <span style={{ fontSize: '0.75rem', color: 'var(--subText)', fontWeight: 500 }}>Forecast</span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
CarbonIntensityChart.displayName = 'CarbonIntensityChart'

// CarbonIntensityNumericDisplay - The hook now has built-in cache sync
const CarbonIntensityNumericDisplay = ({ regionCode, timelineState }: {
  regionCode: string;
  timelineState?: TimelineState;
}) => {
  const currentTimelineState = timelineState || defaultTimelineState
  
  // Call hook - it now has built-in cache sync, and use loading state
  const { data: carbonData, loading } = useCarbonIntensityData(currentTimelineState)
  
  // Get data array
  const dataArray = Array.isArray(carbonData?.data) ? carbonData.data as Array<Record<string, unknown>> : null
  
  // COMPUTE VALUE DIRECTLY from hook data
  let displayValue: number | null = null
  let isDataAvailable = false
  let regionFound = false
  
  // Data is available if we have an array (even if empty) - this means the API responded
  if (dataArray !== null) {
    isDataAvailable = true
  }
  
  if (dataArray && dataArray.length > 0 && regionCode) {
    const apiRegionCode = convertToApiRegionCode(regionCode)
    const regionRow = dataArray.find((row) => row.region_code === apiRegionCode)
    
    if (regionRow) {
      regionFound = true
      if (currentTimelineState.mode === 'future') {
        displayValue = (regionRow.forecasted_avg_carbon_intensity_direct ||
                 regionRow.carbon_intensity_avg_direct ||
                 regionRow.carbon_intensity ||
                 null) as number | null
      } else {
        displayValue = (regionRow.carbon_intensity_avg_direct ||
                 regionRow.carbon_intensity ||
                 null) as number | null
      }
    }
  }
  
  // Helper function to get intensity level and color
  const getIntensityLevel = useCallback((val: number) => {
    const isDark = document.documentElement.classList.contains('dark')
    
    if (val < 100) return { label: 'Very Low', color: isDark ? '#10B981' : '#059669' }
    if (val < 200) return { label: 'Low', color: isDark ? '#34D399' : '#16a34a' }
    if (val < 300) return { label: 'Moderate', color: isDark ? '#FCD34D' : '#ca8a04' }
    if (val < 400) return { label: 'High', color: isDark ? '#F59E0B' : '#d97706' }
    if (val < 600) return { label: 'Very High', color: isDark ? '#EF4444' : '#dc2626' }
    return { label: 'Extreme', color: isDark ? '#991B1B' : '#7f1d1d' }
  }, [])
  
  // Determine what message to show when there's no display value
  // Priority: 1. Still loading, 2. Data loaded but empty/region not found
  if (!displayValue) {
    let statusMessage = 'Loading...'
    
    // If not loading and data has been fetched (even if empty), show appropriate message
    if (!loading && isDataAvailable) {
      if (currentTimelineState.mode === 'future') {
        statusMessage = 'No forecast data available'
      } else if (!regionFound && dataArray && dataArray.length > 0) {
        statusMessage = 'Region not available'
      } else {
        statusMessage = 'No data available'
      }
    }
    
    return (
      <div style={{ textAlign: 'center', padding: '1rem', color: 'var(--muted)' }}>
        {statusMessage}
      </div>
    )
  }
  
  // At this point displayValue is guaranteed to be non-null
  const level = getIntensityLevel(displayValue)
  const roundedValue = Math.round(displayValue)
  
  return (
    <div
      data-testid="carbon-intensity-numeric"
      data-value={roundedValue}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem'
      }}
    >
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <div style={{
          fontSize: '2rem',
          fontWeight: 700,
          color: level.color,
          position: 'relative',
          letterSpacing: '-0.02em'
        }}>
          {roundedValue}
          <span style={{
            fontSize: '0.875rem',
            fontWeight: 600,
            marginLeft: '0.375rem',
            color: 'var(--subText)',
            opacity: 0.9
          }}>gCO₂eq/kWh</span>
        </div>
      </div>
      <div style={{
        padding: '0.375rem 0.75rem',
        borderRadius: '10px',
        backgroundColor: level.color + '15',
        border: `1px solid ${level.color}30`,
        backdropFilter: 'blur(10px)',
        WebkitBackdropFilter: 'blur(10px)',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.1)'
      }}>
        <div style={{
          fontSize: '0.75rem',
          fontWeight: 600,
          color: level.color,
          letterSpacing: '0.025em'
        }}>
          {level.label}
        </div>
      </div>
      <div style={{
        height: '8px',
        borderRadius: '6px',
        backgroundColor: 'var(--progressBarBg)',
        position: 'relative',
        overflow: 'hidden',
        boxShadow: 'inset 0 2px 4px rgba(0, 0, 0, 0.1)'
      }}>
        <div style={{
          position: 'absolute',
          left: 0,
          top: 0,
          height: '100%',
          width: `${Math.min(100, (displayValue / 1000) * 100)}%`,
          background: `linear-gradient(90deg, ${level.color}dd, ${level.color})`,
          transition: 'width 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2), inset 0 1px 0 rgba(255, 255, 255, 0.2)'
        }} />
      </div>
    </div>
  )
}

// Wrapper for carbon intensity indicator - child calls hook directly
const CarbonIntensityIndicator = ({ regionCode, timelineState }: {
  regionCode: string;
  timelineState?: TimelineState;
}) => {
  return (
    <div style={{
      borderRadius: '16px',
      border: '1px solid var(--panelBorder)',
      backgroundColor: 'var(--cardBg)',
      backdropFilter: 'blur(40px) saturate(200%)',
      WebkitBackdropFilter: 'blur(40px) saturate(200%)',
      padding: '1.25rem',  // Reduced from 1.75rem to 1.25rem
      marginBottom: '1rem',  // Reduced from 1.25rem to 1rem
      boxShadow: '0 12px 48px rgba(0, 0, 0, 0.12), 0 4px 16px rgba(0, 0, 0, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.05)',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Subtle gradient overlay */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        height: '80px',
        background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.03) 0%, transparent 100%)',
        pointerEvents: 'none'
      }} />
      
      <div style={{
        marginBottom: '0.5rem',  // Reduced from 1.25rem to 0.5rem
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'relative'
      }}>
        <h3 style={{
          fontSize: '1rem',  // Slightly smaller title
          fontWeight: 700,
          color: 'var(--panelText)',
          letterSpacing: '-0.01em',
          opacity: 1 // Ensure full opacity
        }}>Carbon Intensity</h3>
      </div>
      
      <CarbonIntensityNumericDisplay
        key={`${regionCode}-${timelineState?.date || 'default'}`}
        regionCode={regionCode}
        timelineState={timelineState}
      />
    </div>
  )
}

// Main panel component - children call hook directly for instant updates
const LeftPanelEM = ({ onClose, timelineState, region: regionProp }: {
  onClose?: () => void;
  timelineState?: TimelineState;
  region?: string;
}) => {
  const { region: urlRegion } = useParams()
  
  // Use prop region if provided, otherwise fall back to URL param
  const region = regionProp || urlRegion

  if (!region) {
    return null
  }

  return (
    <OuterPanel>
      <div
        className="left-panel-container"
        onMouseEnter={() => setHoveredZone(null)}
        style={{
        background: 'var(--panelBg)',
        backdropFilter: 'blur(48px) saturate(200%)',
        WebkitBackdropFilter: 'blur(48px) saturate(200%)',
        display: 'flex',
        flexDirection: 'column',
        height: 'calc(100vh - 175px)',  // Further reduced height
        position: 'relative',
        top: '1rem',  // Create floating effect with 1rem space from top
        paddingTop: 0,  // No padding at the top
        marginTop: 0,  // No margin at the top
        borderRadius: '1.5rem',  // Rounded corners all around for floating appearance
        overflow: 'hidden'  // Ensure content respects border radius
      }}>
        <section style={{
          height: '100%',
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          margin: 0,
          padding: 0,
          paddingTop: 0,  // Explicitly no top padding
          marginTop: 0,  // Explicitly no top margin
          position: 'relative'  // Ensure proper positioning context
        }}>
          <ZoneHeader zoneId={region} onClose={onClose} timelineState={timelineState} />
          <div
            id="panel-scroller"
            style={{
              flex: 1,
              overflowY: 'auto',
              overflowX: 'hidden',
              padding: '1rem',  // Reduced side padding
              paddingTop: '0.5rem'  // Further reduced from 0.75rem to 0.5rem
            }}
          >
            <DisplayByEmissionToggle />
            <CarbonIntensityIndicator regionCode={region} timelineState={timelineState} />
            <ElectricityMixCard regionCode={region} timelineState={timelineState} />
            <CarbonIntensityChart regionCode={region} timelineState={timelineState} />
          </div>
        </section>
      </div>
    </OuterPanel>
  )
}
LeftPanelEM.displayName = 'LeftPanelEM'

export default LeftPanelEM
