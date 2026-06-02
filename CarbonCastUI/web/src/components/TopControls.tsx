import React, { forwardRef, useImperativeHandle } from 'react'
import type { MapRef } from 'react-map-gl/maplibre'
import { setHoveredZone } from './InfoPopover'
import SettingsModal, { SettingsButton } from './SettingsModal'

function ZoomControls({ mapRef }: { mapRef: React.RefObject<MapRef> }) {
  const zoomIn = () => {
    try {
      mapRef.current?.getMap().zoomIn()
    } catch {
      // Zoom in failed silently
    }
  }

  const zoomOut = () => {
    try {
      mapRef.current?.getMap().zoomOut()
    } catch {
      // Zoom out failed silently
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <button
        onClick={zoomIn}
        className="button-animation"
        style={{
          WebkitBackdropFilter:'blur(8px)', 
          backdropFilter:'blur(8px)',
          background:'var(--glassBg)', 
          border:'1px solid var(--glassBorder)',
          color:'var(--glassText)', 
          padding:'10px 12px', 
          borderRadius: '10px', 
          cursor:'pointer',
          boxShadow:'0 10px 15px -3px rgba(0,0,0,0.3), 0 4px 6px -4px rgba(0,0,0,0.3)',
          fontSize: '16px',
          fontWeight: 'bold'
        }}
        aria-label="Zoom in"
        title="Zoom in"
      >
        +
      </button>
      <button
        onClick={zoomOut}
        className="button-animation"
        style={{
          WebkitBackdropFilter:'blur(8px)', 
          backdropFilter:'blur(8px)',
          background:'var(--glassBg)', 
          border:'1px solid var(--glassBorder)',
          color:'var(--glassText)', 
          padding:'10px 12px', 
          borderRadius: '10px', 
          cursor:'pointer',
          boxShadow:'0 10px 15px -3px rgba(0,0,0,0.3), 0 4px 6px -4px rgba(0,0,0,0.3)',
          fontSize: '16px',
          fontWeight: 'bold'
        }}
        aria-label="Zoom out"
        title="Zoom out"
      >
        -
      </button>
    </div>
  )
}

export interface TopControlsRef {
  zoomIn: () => void
  zoomOut: () => void
}

const TopControls = forwardRef<TopControlsRef, { mapRef: React.RefObject<MapRef> }>(
  ({ mapRef }, ref) => {

    useImperativeHandle(ref, () => ({
      zoomIn: () => {
        try {
          mapRef.current?.getMap().zoomIn()
        } catch {
          // Zoom in failed silently
        }
      },
      zoomOut: () => {
        try {
          mapRef.current?.getMap().zoomOut()
        } catch {
          // Zoom out failed silently
        }
      }
    }))

    return (
      <div
        onMouseEnter={() => setHoveredZone(null)}
        style={{ position: 'fixed', top: 16, right: 16, zIndex: 1300 }}>
        {/* Settings Button - replaces old Theme Toggle */}
        <SettingsButton />
        
        {/* Settings Modal - positioned near the button */}
        <SettingsModal />
        
        {/* Zoom Controls */}
        <div style={{ marginTop: 16 }}>
          <ZoomControls mapRef={mapRef} />
        </div>
      </div>
    )
  }
)

TopControls.displayName = 'TopControls'

export default TopControls