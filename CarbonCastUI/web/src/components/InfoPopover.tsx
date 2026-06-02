import { useState, useEffect } from 'react'
import { useCarbonIntensityData, type TimelineState } from '../hooks/cache'
import { apiToMapRegionMapping } from '../utils/regionMapping'

// Optimized state management for maximum performance and minimal latency
let mousePosition = { x: 0, y: 0 }
let hoveredZone: string | null = null
let hoveredZoneValue: number | null = null
let isMapMoving = false
const listeners: (() => void)[] = []

// Debounced updates for smooth performance
let updateFrame: number | null = null

const scheduleUpdate = () => {
  if (updateFrame === null) {
    updateFrame = requestAnimationFrame(() => {
      listeners.forEach(fn => fn())
      updateFrame = null
    })
  }
}

export const setMousePosition = (pos: { x: number, y: number }) => {
  mousePosition = pos
  scheduleUpdate() // Use RAF for smooth updates
}

export const setHoveredZone = (zone: string | null, value?: number | null) => {
  if (hoveredZone !== zone || hoveredZoneValue !== value) { // Only update if changed
    hoveredZone = zone
    hoveredZoneValue = value ?? null
    scheduleUpdate()
  }
}

export const setMapMoving = (moving: boolean) => {
  if (isMapMoving !== moving) { // Only update if changed
    isMapMoving = moving
    scheduleUpdate()
  }
}

export const getHoveredZone = () => hoveredZone
export const getHoveredZoneValue = () => hoveredZoneValue

// NEW: Trigger update when data changes
export const triggerDataUpdate = () => {
  scheduleUpdate()
}

// Smart tooltip positioning function (simplified from EM's getSafeTooltipPosition)
const getSafeTooltipPosition = (
  mouseX: number, 
  mouseY: number, 
  tooltipWidth: number, 
  tooltipHeight: number
) => {
  const screenWidth = window.innerWidth
  const screenHeight = window.innerHeight
  const margin = 16
  const buffer = 24 // Extra space to prevent tooltip hovering - like EM
  
  let x = mouseX + buffer // Default offset to right with buffer
  let y = mouseY - tooltipHeight - buffer // Default offset above with buffer
  
  // Flip to left if would overflow right edge
  if (x + tooltipWidth + margin > screenWidth) {
    x = mouseX - tooltipWidth - buffer
  }
  
  // Flip to below if would overflow top edge
  if (y < margin) {
    y = mouseY + buffer
  }
  
  // Ensure doesn't go below screen
  if (y + tooltipHeight + margin > screenHeight) {
    y = screenHeight - tooltipHeight - margin
  }
  
  // Ensure doesn't go past left edge
  if (x < margin) {
    x = margin
  }
  
  return { x, y }
}

export default function InfoPopover({ timelineState }: { timelineState?: TimelineState }) {
  const [, forceUpdate] = useState(0)
  
  // Default timeline state for current time
  const defaultTimelineState: TimelineState = {
    mode: 'now',
    date: new Date().toISOString().split('T')[0],
    hour: new Date().getHours()
  }
  
  // Fetch carbon intensity data
  const { data: carbonData } = useCarbonIntensityData(timelineState || defaultTimelineState)
  
  // Subscribe to state changes with optimized cleanup
  useEffect(() => {
    const listener = () => forceUpdate(n => n + 1)
    listeners.push(listener)
    return () => {
      // Efficient cleanup
      const index = listeners.indexOf(listener)
      if (index > -1) listeners.splice(index, 1)
      
      // Cancel any pending animation frame
      if (updateFrame !== null) {
        cancelAnimationFrame(updateFrame)
        updateFrame = null
      }
    }
  }, [])
  
  // CRITICAL FIX: Force re-render when carbon data changes
  // This ensures the hover card updates automatically when new data arrives
  // Track data changes using the first data item's timestamp or data array length
  const dataArray = Array.isArray(carbonData?.data) ? carbonData.data as Array<Record<string, unknown>> : null
  const dataFingerprint = dataArray
    ? `${dataArray.length}-${dataArray[0]?.['UTC time'] || ''}`
    : null
    
  useEffect(() => {
    // Always update the value if we're hovering over a zone
    if (hoveredZone && dataArray && dataArray.length > 0) {
      // Find the value for the currently hovered zone
      const apiRegionCode = Object.keys(apiToMapRegionMapping).find(
        key => apiToMapRegionMapping[key] === hoveredZone
      )
      
      if (apiRegionCode) {
        const regionData = dataArray.find((row) => row.region_code === apiRegionCode)
        if (regionData) {
          const value = (regionData.carbon_intensity_avg_direct ||
                       regionData.carbon_intensity ||
                       regionData.forecasted_avg_carbon_intensity_direct ||
                       null) as number | null
          if (value !== hoveredZoneValue) {
            hoveredZoneValue = value
            scheduleUpdate() // Trigger re-render
          }
        } else if (hoveredZoneValue !== null) {
          // No data for this region anymore, clear the value
          hoveredZoneValue = null
          scheduleUpdate()
        }
      }
    }
    
    // Even if not hovering, trigger update to ensure component is ready
    // This helps with instant updates when user starts hovering
    scheduleUpdate()
  }, [dataFingerprint, dataArray])
  
  // Hide during map movement but keep in DOM for smooth animations
  if (isMapMoving) {
    return null
  }
  
  const tooltipWidth = 320
  const tooltipHeight = 140
  const position = getSafeTooltipPosition(
    mousePosition.x, 
    mousePosition.y, 
    tooltipWidth, 
    tooltipHeight
  )
  
  return (
    <div 
      style={{
        position: 'fixed',
        left: position.x,
        top: position.y,
        zIndex: 1200,
        pointerEvents: 'none', // Critical: tooltip is non-interactive like EM
        width: tooltipWidth
      }}
    >
      <div style={{
        WebkitBackdropFilter: 'blur(16px)', 
        backdropFilter: 'blur(16px)',
        background: 'var(--glassBg)', 
        border: '1px solid var(--glassBorder)',
        color: 'var(--glassText)', 
        padding: '16px', 
        borderRadius: '16px',
        boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25), 0 0 0 1px rgba(255,255,255,0.05)',
        transition: 'opacity 0.12s cubic-bezier(0.16, 1, 0.3, 1), transform 0.12s cubic-bezier(0.16, 1, 0.3, 1)',
        opacity: hoveredZone ? 1 : 0,
        transform: hoveredZone ? 'translateY(0) scale(1)' : 'translateY(2px) scale(0.98)',
        willChange: 'opacity, transform' // Optimize for animations
        // Note: pointerEvents stays 'none' inherited from parent - tooltip is non-interactive
      }}>
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          marginBottom: '8px' 
        }}>
          <div style={{ 
            fontWeight: 600, 
            fontSize: '16px',
            color: 'var(--glassText)' 
          }}>{hoveredZone || '—'}</div>
          <span style={{ 
            fontSize: '12px', 
            color: 'var(--muted)',
            padding: '2px 6px',
            borderRadius: '6px',
            backgroundColor: 'var(--buttonBg)'
          }}>Live</span>
        </div>
        
        {hoveredZoneValue !== null ? (
          <div style={{
            fontSize: '24px',
            fontWeight: 700,
            color: 'var(--glassText)',
            marginBottom: '8px'
          }}>
            {Math.round(hoveredZoneValue)} <span style={{ fontSize: '14px', fontWeight: 400 }}>gCO₂eq/kWh</span>
          </div>
        ) : (
          <div style={{
            fontSize: '16px',
            fontWeight: 500,
            color: 'var(--muted)',
            marginBottom: '8px',
            fontStyle: 'italic'
          }}>
            No data available
          </div>
        )}
        
        {hoveredZoneValue !== null ? (
          <div style={{
            fontSize: '14px',
            color: 'var(--glassText)',
            marginBottom: '12px',
            lineHeight: '1.4'
          }}>
            Click for detailed energy mix and carbon intensity data
          </div>
        ) : (
          <div style={{
            fontSize: '14px',
            color: 'var(--muted)',
            marginBottom: '12px',
            lineHeight: '1.4'
          }}>
            Data is not available for this region
          </div>
        )}
        
        <div style={{ 
          fontSize: '12px', 
          color: 'var(--muted)', 
          textAlign: 'center',
          fontStyle: 'italic'
        }}>
          Click region to view details
        </div>
      </div>
    </div>
  )
}


