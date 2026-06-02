import { useState, useEffect } from 'react'
import { setHoveredZone } from './InfoPopover'

export interface FallbackInfo {
  used: boolean
  message?: string
}

interface DataStatusIndicatorProps {
  fallbackInfo: FallbackInfo | null
}

// Parse the fallback message to extract dates
// Expected format: "Data from 2024-12-04 (requested 2024-12-06)"
function parseFallbackMessage(message?: string): { actualDate: string | null; requestedDate: string | null } {
  if (!message) {
    return { actualDate: null, requestedDate: null }
  }
  
  // Try to match the format "Data from YYYY-MM-DD (requested YYYY-MM-DD)"
  const match = message.match(/Data from (\d{4}-\d{2}-\d{2}) \(requested (\d{4}-\d{2}-\d{2})\)/)
  
  if (match) {
    return {
      actualDate: match[1],
      requestedDate: match[2]
    }
  }
  
  // Alternative format: check for "Forecast unavailable" messages
  if (message.includes('Forecast unavailable')) {
    return { actualDate: null, requestedDate: null }
  }
  
  return { actualDate: null, requestedDate: null }
}

// Format date for display (e.g., "Dec 4, 2024")
function formatDateForDisplay(dateString: string | null): string {
  if (!dateString) return 'Unknown'
  
  try {
    const date = new Date(dateString + 'T00:00:00')
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    })
  } catch {
    return dateString
  }
}

export default function DataStatusIndicator({ fallbackInfo }: DataStatusIndicatorProps) {
  // Track which specific message has been dismissed (so same message doesn't re-appear)
  const [dismissedMessage, setDismissedMessage] = useState<string | undefined>(undefined)
  
  // For animation only
  const [isVisible, setIsVisible] = useState(false)
  
  // Should we show the banner?
  // YES if: fallback is used AND current message hasn't been dismissed
  const shouldShow = fallbackInfo?.used === true &&
                     fallbackInfo?.message !== undefined &&
                     fallbackInfo.message !== dismissedMessage
  
  // Handle visibility transitions for animation
  useEffect(() => {
    if (shouldShow) {
      // Small delay for enter animation
      const timer = setTimeout(() => {
        setIsVisible(true)
      }, 50)
      return () => clearTimeout(timer)
    } else {
      setIsVisible(false)
    }
  }, [shouldShow])
  
  // Clear dismissed state when fallback becomes inactive
  // This ensures banner will show fresh next time fallback is used
  useEffect(() => {
    if (!fallbackInfo?.used) {
      setDismissedMessage(undefined)
    }
  }, [fallbackInfo?.used])
  
  // Handle dismiss - immediately set the dismissed message
  const handleDismiss = () => {
    // Set dismissed message immediately (no delay) to prevent race conditions
    setDismissedMessage(fallbackInfo?.message)
  }
  
  // Don't render if we shouldn't show
  if (!shouldShow) {
    return null
  }
  
  // IMPORTANT: Parse from fallbackInfo.message DIRECTLY every render (not from state)
  const { actualDate, requestedDate } = parseFallbackMessage(fallbackInfo?.message)
  const isForecastUnavailable = fallbackInfo?.message?.includes('Forecast unavailable')
  
  return (
    <div
      onMouseEnter={() => setHoveredZone(null)}
      style={{
        position: 'fixed',
        top: 16,
        right: 70, // Positioned to the left of TopControls
        zIndex: 1250,
        maxWidth: '320px',
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateY(0) scale(1)' : 'translateY(-10px) scale(0.95)',
        transition: 'opacity 0.3s ease, transform 0.3s ease',
        pointerEvents: isVisible ? 'auto' : 'none'
      }}
    >
      <div
        style={{
          WebkitBackdropFilter: 'blur(64px) saturate(200%)',
          backdropFilter: 'blur(64px) saturate(200%)',
          background: 'var(--fallbackBannerBg)',
          border: '1px solid var(--fallbackBannerBorder)',
          borderRadius: '16px',
          boxShadow: '0 16px 32px -4px rgba(0,0,0,0.08), 0 8px 16px -2px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.3)',
          overflow: 'hidden'
        }}
      >
        {/* Warning accent line at top */}
        <div
          style={{
            height: '2px',
            background: 'linear-gradient(90deg, rgba(245, 158, 11, 0.5), rgba(251, 191, 36, 0.7), rgba(245, 158, 11, 0.5))',
            width: '100%'
          }}
        />
        
        <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
          {/* Warning icon */}
          <div
            style={{
              fontSize: '18px',
              lineHeight: 1,
              flexShrink: 0,
              marginTop: '2px'
            }}
          >
            ⚠️
          </div>
          
          {/* Content */}
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: '0.8125rem',
                fontWeight: 600,
                color: 'var(--glassText)',
                marginBottom: '4px',
                letterSpacing: '-0.01em'
              }}
            >
              {isForecastUnavailable ? 'Forecast Unavailable' : 'Data Not Available for Requested Date'}
            </div>
            
            {isForecastUnavailable ? (
              <div
                style={{
                  fontSize: '0.75rem',
                  color: 'var(--muted)',
                  lineHeight: 1.4
                }}
              >
                Showing historical data instead
              </div>
            ) : (
              <div style={{ fontSize: '0.75rem', color: 'var(--muted)', lineHeight: 1.5 }}>
                {actualDate && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '2px' }}>
                    <span style={{ opacity: 0.8 }}>Showing:</span>
                    <span style={{ fontWeight: 500 }}>{formatDateForDisplay(actualDate)}</span>
                  </div>
                )}
                {requestedDate && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ opacity: 0.8 }}>Requested:</span>
                    <span style={{ fontWeight: 500, textDecoration: 'line-through', opacity: 0.7 }}>
                      {formatDateForDisplay(requestedDate)}
                    </span>
                  </div>
                )}
                {!actualDate && !requestedDate && fallbackInfo.message && (
                  <div>{fallbackInfo.message}</div>
                )}
              </div>
            )}
          </div>
          
          {/* Dismiss button */}
          <button
            onClick={handleDismiss}
            aria-label="Dismiss notification"
            style={{
              background: 'transparent',
              border: 'none',
              padding: '4px',
              cursor: 'pointer',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--glassText)',
              opacity: 0.5,
              transition: 'opacity 0.2s ease, background-color 0.2s ease',
              flexShrink: 0,
              marginTop: '-2px',
              marginRight: '-4px'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.opacity = '1'
              e.currentTarget.style.backgroundColor = 'rgba(0, 0, 0, 0.1)'
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.opacity = '0.5'
              e.currentTarget.style.backgroundColor = 'transparent'
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}