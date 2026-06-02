import React, { useState, useRef } from 'react'

interface TimelineLoadingOverlayProps {
  isLoading: boolean
  progress?: number // 0-100 percentage, optional for indeterminate loading
  message?: string
}

export const TimelineLoadingOverlay: React.FC<TimelineLoadingOverlayProps> = ({
  isLoading,
  progress,
  message = 'Loading data for all regions...'
}) => {
  // For exit animation: keep component mounted briefly after isLoading becomes false
  const [isExiting, setIsExiting] = useState(false)
  const exitTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const wasLoadingRef = useRef(isLoading)
  
  // Detect transition from loading -> not loading for exit animation
  if (wasLoadingRef.current && !isLoading) {
    // Start exit animation
    setIsExiting(true)
    wasLoadingRef.current = false
    
    // Clear after exit animation completes
    if (exitTimeoutRef.current) clearTimeout(exitTimeoutRef.current)
    exitTimeoutRef.current = setTimeout(() => {
      setIsExiting(false)
    }, 200)
  } else if (isLoading && !wasLoadingRef.current) {
    // Entering - update ref immediately
    wasLoadingRef.current = true
    // Clear any pending exit timeout
    if (exitTimeoutRef.current) {
      clearTimeout(exitTimeoutRef.current)
      exitTimeoutRef.current = null
    }
    setIsExiting(false)
  }
  
  // Don't render if not loading AND not exiting
  if (!isLoading && !isExiting) return null
  
  const isIndeterminate = progress === undefined || progress === null
  
  // Get responsive positioning that matches Timeline
  const isDesktop = typeof window !== 'undefined' && window.innerWidth >= 768
  
  return (
    <div
      style={{
        position: 'fixed',
        // Position to the right of the Timeline slider
        // Timeline is at: left: calc(63px + 0.75rem), width: calc(13vw + 15rem - 1.5rem)
        // So we start at: left + width + gap
        left: isDesktop
          ? 'calc(63px + 0.75rem + 13vw + 15rem - 1.5rem + 12px)'
          : '0.75rem',
        bottom: 22, // Slightly higher to align with Timeline slider bottom
        zIndex: 1250,
        maxWidth: isDesktop ? '240px' : 'calc(100% - 1.5rem)',
        width: isDesktop ? '240px' : undefined,
        // INSTANT appearance when loading, smooth fade out when done
        opacity: isLoading ? 1 : 0,
        transform: isLoading
          ? 'translateY(0) scale(1)'
          : 'translateY(10px) scale(0.95)',
        // No transition on entry (instant), smooth transition on exit
        transition: isLoading ? 'none' : 'opacity 0.3s ease, transform 0.3s ease',
        pointerEvents: isLoading ? 'auto' : 'none'
      }}
    >
      <div
        style={{
          WebkitBackdropFilter: 'blur(64px) saturate(200%)',
          backdropFilter: 'blur(64px) saturate(200%)',
          background: 'var(--timelineBg)',
          border: '1px solid var(--timelineBorder)',
          borderRadius: 16,
          boxShadow: '0 16px 32px -4px rgba(0,0,0,0.08), 0 8px 16px -2px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.3)',
          overflow: 'hidden'
        }}
      >
        {/* Green accent line at top */}
        <div
          style={{
            height: '2px',
            background: 'linear-gradient(90deg, #16A34A, #22C55E, #16A34A)',
            width: '100%'
          }}
        />
        
        <div style={{ padding: '10px 12px' }}>
          {/* Top row: Icon + Message */}
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', marginBottom: '8px' }}>
            {/* Loading icon */}
            <div
              style={{
                fontSize: '14px',
                lineHeight: 1,
                flexShrink: 0,
                marginTop: '1px',
                animation: 'pulse-lock 2s ease-in-out infinite'
              }}
            >
              🔒
            </div>
            
            {/* Content */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div
                style={{
                  fontSize: '11px',
                  fontWeight: 500,
                  color: '#22C55E',
                  marginBottom: '2px',
                  letterSpacing: '-0.01em',
                  lineHeight: '1.2'
                }}
              >
                Timeline Locked
              </div>
              <div
                style={{
                  fontSize: '11px',
                  color: '#4ADE80',
                  lineHeight: 1.3
                }}
              >
                {message}
              </div>
            </div>
          </div>
          
          {/* Progress bar */}
          <div style={{
            width: '100%',
            height: 5,
            backgroundColor: 'rgba(34, 197, 94, 0.2)',
            borderRadius: 9999,
            overflow: 'hidden',
            position: 'relative',
            marginBottom: '6px'
          }}>
            {isIndeterminate ? (
              // Indeterminate animation
              <div style={{
                position: 'absolute',
                top: 0,
                left: 0,
                height: '100%',
                width: '40%',
                background: 'linear-gradient(90deg, transparent, #22C55E, transparent)',
                borderRadius: 9999,
                animation: 'indeterminate-progress 1.5s ease-in-out infinite'
              }} />
            ) : (
              // Determinate progress
              <div style={{
                height: '100%',
                width: `${Math.min(100, Math.max(0, progress))}%`,
                background: 'linear-gradient(90deg, #16A34A, #22C55E)',
                borderRadius: 9999,
                transition: 'width 0.2s ease-out',
                boxShadow: '0 0 8px rgba(34, 197, 94, 0.5)'
              }} />
            )}
          </div>
          
          {/* Progress percentage row */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{
              fontSize: '10px',
              color: '#4ADE80',
              opacity: 0.8,
              lineHeight: '1.2'
            }}>
              Loading all regions...
            </span>
            <span style={{
              fontSize: '11px',
              fontWeight: 600,
              color: '#22C55E',
              lineHeight: '1.2'
            }}>
              {isIndeterminate ? '...' : `${Math.round(progress)}%`}
            </span>
          </div>
        </div>
        
        <style>{`
          @keyframes pulse-lock {
            0%, 100% {
              opacity: 1;
              transform: scale(1);
            }
            50% {
              opacity: 0.6;
              transform: scale(1.1);
            }
          }
          
          @keyframes indeterminate-progress {
            0% {
              transform: translateX(-100%);
            }
            100% {
              transform: translateX(300%);
            }
          }
        `}</style>
      </div>
    </div>
  )
}

export default TimelineLoadingOverlay