import { useEffect, useState, useRef, useCallback, memo, useMemo } from 'react'
import type { TimelineState } from '../hooks/cache'
import DatePicker from 'react-datepicker'
import 'react-datepicker/dist/react-datepicker.css'
import { parseLocalDate, formatLocalDate, addDays, getCurrentLocalDate } from '../utils/dateUtils'
import TimelineLoadingOverlay from './TimelineLoadingOverlay'
import { setHoveredZone } from './InfoPopover'

type Props = {
  timelineState: TimelineState
  onTimelineChange: (newState: TimelineState) => void
  isLocked?: boolean
  loadingProgress?: number
  loadingMessage?: string
}

// Custom Time Slider Component inspired by ElectricityMaps
interface TimeSliderProps {
  value: number
  min: number
  max: number
  disabled: boolean
  onChange: (value: number) => void
}

const TimeSlider = memo(({ value, min, max, disabled, onChange }: TimeSliderProps) => {
  const sliderRef = useRef<HTMLDivElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [showTooltip, setShowTooltip] = useState(false)
  
  // Calculate thumb position as percentage
  const percentage = ((value - min) / (max - min)) * 100
  
  // Generate day/night gradient (6am-6pm is day, rest is night)
  // Using lighter colors for better visibility
  const trackBackground = useMemo(() => {
    const isDark = document.documentElement.classList.contains('dark')
    // Lighter colors that are more visible against frosted glass
    const dayColor = isDark ? 'rgba(140, 140, 140, 0.9)' : 'rgba(245, 245, 245, 1)'
    const nightColor = isDark ? 'rgba(90, 90, 100, 0.9)' : 'rgba(180, 180, 195, 1)'
    
    // 6am = 25%, 6pm = 75% (approximate)
    // Night: 0-6am, Day: 6am-6pm, Night: 6pm-midnight
    return `linear-gradient(90deg,
      ${nightColor} 0%,
      ${nightColor} 25%,
      ${dayColor} 25%,
      ${dayColor} 75%,
      ${nightColor} 75%,
      ${nightColor} 100%
    )`
  }, [])
  
  // Get icon based on time (Sun for day, Moon for night)
  const getTimeIcon = () => {
    if (value >= 6 && value < 18) {
      return (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="4"/>
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/>
        </svg>
      )
    }
    return (
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
      </svg>
    )
  }
  
  // Format hour for display
  const formatHour = (hour: number) => {
    if (hour === 0) return '12:00 AM'
    if (hour === 12) return '12:00 PM'
    if (hour < 12) return `${hour}:00 AM`
    return `${hour - 12}:00 PM`
  }
  
  const handleInteraction = useCallback((clientX: number) => {
    if (disabled || !sliderRef.current) return
    
    const rect = sliderRef.current.getBoundingClientRect()
    const x = clientX - rect.left
    const newPercentage = Math.max(0, Math.min(100, (x / rect.width) * 100))
    const newValue = Math.round((newPercentage / 100) * (max - min) + min)
    
    if (newValue !== value) {
      onChange(newValue)
    }
  }, [disabled, max, min, value, onChange])
  
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (disabled) return
    setIsDragging(true)
    setShowTooltip(true)
    handleInteraction(e.clientX)
  }, [disabled, handleInteraction])
  
  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isDragging) return
    handleInteraction(e.clientX)
  }, [isDragging, handleInteraction])
  
  const handleMouseUp = useCallback(() => {
    setIsDragging(false)
    setShowTooltip(false)
  }, [])
  
  useEffect(() => {
    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove)
      document.addEventListener('mouseup', handleMouseUp)
      return () => {
        document.removeEventListener('mousemove', handleMouseMove)
        document.removeEventListener('mouseup', handleMouseUp)
      }
    }
  }, [isDragging, handleMouseMove, handleMouseUp])
  
  // Touch support
  const handleTouchStart = useCallback((e: React.TouchEvent) => {
    if (disabled) return
    setIsDragging(true)
    setShowTooltip(true)
    handleInteraction(e.touches[0].clientX)
  }, [disabled, handleInteraction])
  
  const handleTouchMove = useCallback((e: React.TouchEvent) => {
    if (!isDragging) return
    handleInteraction(e.touches[0].clientX)
  }, [isDragging, handleInteraction])
  
  const handleTouchEnd = useCallback(() => {
    setIsDragging(false)
    setShowTooltip(false)
  }, [])
  
  return (
    <div style={{
      position: 'relative',
      width: '100%',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center'
    }}>
      {/* Frosted Tooltip - appears above thumb when interacting */}
      <div
        style={{
          position: 'absolute',
          left: `${percentage}%`,
          bottom: 'calc(100% + 6px)',
          transform: 'translateX(-50%)',
          opacity: (showTooltip || isDragging) ? 1 : 0,
          pointerEvents: 'none',
          transition: 'opacity 0.15s ease',
          zIndex: 10
        }}
      >
        <div
          style={{
            padding: '4px 10px',
            borderRadius: 6,
            background: 'var(--frostedGlassBg, rgba(255, 255, 255, 0.1))',
            backdropFilter: 'blur(64px) saturate(200%)',
            WebkitBackdropFilter: 'blur(64px) saturate(200%)',
            border: '1px solid var(--frostedGlassBorder, rgba(255, 255, 255, 0.2))',
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.06), 0 2px 6px rgba(0, 0, 0, 0.03), inset 0 1px 0 rgba(255, 255, 255, 0.3)',
            color: 'var(--glassText)',
            fontSize: '11px',
            fontWeight: 500,
            whiteSpace: 'nowrap',
            letterSpacing: '-0.01em',
            lineHeight: '1.2'
          }}
        >
          {formatHour(value)}
        </div>
        {/* Tooltip arrow */}
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: '100%',
            transform: 'translateX(-50%)',
            width: 0,
            height: 0,
            borderLeft: '4px solid transparent',
            borderRight: '4px solid transparent',
            borderTop: '4px solid var(--fallbackBannerBorder, rgba(156, 163, 175, 0.4))'
          }}
        />
      </div>
      
      {/* Slider Track */}
      <div
        ref={sliderRef}
        onMouseDown={handleMouseDown}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
        style={{
          position: 'relative',
          height: 6,
          width: '100%',
          borderRadius: 3,
          background: trackBackground,
          cursor: disabled ? 'not-allowed' : 'pointer',
          opacity: disabled ? 0.4 : 1,
          transition: 'opacity 0.2s ease'
        }}
      >
        {/* Thumb */}
        <div
          onMouseEnter={() => !disabled && setShowTooltip(true)}
          onMouseLeave={() => !isDragging && setShowTooltip(false)}
          style={{
            position: 'absolute',
            left: `${percentage}%`,
            top: '50%',
            transform: 'translate(-50%, -50%)',
            width: 20,
            height: 20,
            borderRadius: '50%',
            background: 'var(--sliderThumbBg, white)',
            border: '1px solid var(--sliderThumbBorder, rgba(209, 213, 219, 1))',
            boxShadow: isDragging
              ? '0 2px 12px rgba(0, 0, 0, 0.15), 0 1px 4px rgba(0, 0, 0, 0.08)'
              : '0 1px 4px rgba(0, 0, 0, 0.08), 0 1px 2px rgba(0, 0, 0, 0.04)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            cursor: disabled ? 'not-allowed' : 'grab',
            transition: 'box-shadow 0.2s ease, transform 0.1s ease',
            color: 'var(--glassText)',
            ...(isDragging && !disabled ? { cursor: 'grabbing', transform: 'translate(-50%, -50%) scale(1.05)' } : {})
          }}
        >
          {getTimeIcon()}
        </div>
      </div>
      
      {/* Time Axis Labels */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        width: '100%',
        marginTop: 6,
        fontSize: '11px',
        color: 'var(--muted)',
        userSelect: 'none',
        lineHeight: '1.2'
      }}>
        {[0, 6, 12, 18, 23].map(hour => (
          <span
            key={hour}
            onClick={() => !disabled && onChange(hour)}
            style={{
              cursor: disabled ? 'default' : 'pointer',
              padding: '2px 4px',
              borderRadius: 4,
              transition: 'background 0.15s ease',
              fontWeight: value === hour ? 500 : 400,
              color: value === hour ? 'var(--glassText)' : 'var(--muted)'
            }}
            onMouseEnter={(e) => {
              if (!disabled) {
                e.currentTarget.style.background = 'var(--buttonBg)'
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = 'transparent'
            }}
          >
            {hour === 0 ? '12am' : hour === 12 ? '12pm' : hour < 12 ? `${hour}am` : `${hour-12}pm`}
          </span>
        ))}
      </div>
    </div>
  )
})
TimeSlider.displayName = 'TimeSlider'

const Timeline = memo(({
  timelineState,
  onTimelineChange,
  isLocked = false,
  loadingProgress,
  loadingMessage
}: Props) => {
  const [showPicker, setShowPicker] = useState(false)
  const [hoveredOption, setHoveredOption] = useState<'past' | 'now' | 'future' | null>(null)
  const buttonRefs = useRef<{ [key: string]: HTMLButtonElement | null }>({})
  const containerRef = useRef<HTMLDivElement>(null)

  const handleModeChange = (mode: 'past' | 'now' | 'future') => {
    if (isLocked) return // Don't change mode while loading
    onTimelineChange({
      ...timelineState,
      mode
    })
  }

  const handleDateChange = useCallback((date: string) => {
    const today = getCurrentLocalDate()
    
    // IMPORTANT: Respect the user's current mode selection
    // Only change mode when selecting today's date
    let newMode = timelineState.mode
    
    // Special case: if selecting today's date, must use "now" mode
    if (date === today) {
      newMode = 'now'
    }
    
    onTimelineChange({
      ...timelineState,
      date,
      mode: newMode
    })
  }, [onTimelineChange, timelineState])

  // Direct hour change handler - no throttling needed with Feature State API
  const handleHourChange = useCallback((hour: number) => {
    if (isLocked) return // Don't change hour while loading
    onTimelineChange({
      ...timelineState,
      hour: hour
    })
  }, [timelineState, onTimelineChange, isLocked])

  useEffect(() => {
    // keep date within reasonable bounds
    const currentDate = new Date()
    const selectedDate = parseLocalDate(timelineState.date)
    
    if (timelineState.mode === 'future' && selectedDate > new Date(currentDate.getTime() + 7 * 24 * 60 * 60 * 1000)) {
      // Limit future dates to 7 days ahead
      handleDateChange(formatLocalDate(currentDate))
    }
  }, [timelineState.date, timelineState.mode, handleDateChange])

  // Dynamic pill positioning based on actual button positions
  const getPillPosition = () => {
    const activeOption = (hoveredOption && hoveredOption !== timelineState.mode) ? hoveredOption : timelineState.mode
    const button = buttonRefs.current[activeOption]
    const container = containerRef.current
    
    if (!button || !container) {
      // Fallback to hardcoded values if refs aren't ready
      if (activeOption === 'past') return { left: '4px', width: 'calc(33.333% - 2px)' }
      if (activeOption === 'now') return { left: 'calc(33.333% + 2px)', width: 'calc(33.333% - 2px)' }
      return { left: 'calc(66.666% + 0px)', width: 'calc(33.333% - 2px)' }
    }
    
    const containerRect = container.getBoundingClientRect()
    const buttonRect = button.getBoundingClientRect()
    
    // Calculate relative position within container
    const relativeLeft = buttonRect.left - containerRect.left
    const buttonWidth = buttonRect.width
    
    return {
      left: `${relativeLeft}px`,
      width: `${buttonWidth}px`
    }
  }

  // Determine if controls should be visually disabled
  const controlsDisabled = isLocked
  
  return (
    <>
      {/* Loading overlay - positioned above timeline */}
      <TimelineLoadingOverlay
        isLoading={isLocked}
        progress={loadingProgress}
        message={loadingMessage}
      />
      
      <div
        onMouseEnter={() => setHoveredZone(null)}
        style={{
          position:'fixed',
          left: window.innerWidth >= 768 ? 'calc(63px + 0.75rem)' : '0.75rem',
          bottom: 16,
          zIndex: 1200,
          width: window.innerWidth >= 768 ? 'calc(13vw + 15rem - 1.5rem)' : 'calc(100% - 1.5rem)',
          maxWidth: window.innerWidth >= 768 ? 'calc(13vw + 15rem - 1.5rem)' : undefined
        }}>
        <div style={{
          WebkitBackdropFilter:'blur(64px) saturate(200%)', backdropFilter:'blur(64px) saturate(200%)',
          background:'var(--timelineBg)',
          border:'1px solid var(--timelineBorder)',
          borderRadius: 16,
          padding: '12px 14px',
          color:'var(--glassText)',
          display:'flex',
          flexDirection:'column',
          gap: 10,
          boxShadow:'0 16px 32px -4px rgba(0,0,0,0.08), 0 8px 16px -2px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.3)',
          width: '100%',
          opacity: controlsDisabled ? 0.7 : 1,
          transition: 'opacity 0.3s ease',
          position: 'relative'
        }}>
          {/* Locked overlay */}
          {controlsDisabled && (
            <div style={{
              position: 'absolute',
              inset: 0,
              borderRadius: 16,
              backgroundColor: 'rgba(0, 0, 0, 0.02)',
              zIndex: 10,
              cursor: 'not-allowed'
            }} />
          )}
          
          {/* Top row: Mode selector + Date picker */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, width: '100%' }}>
            <div ref={containerRef} style={{
              display:'flex',
              borderRadius: 9999,
              background:'var(--buttonBg)',
              padding: 3,
              position: 'relative',
              flex: '0 0 auto',
              pointerEvents: controlsDisabled ? 'none' : 'auto'
            }}>
              {/* Dynamic Glassmorphic sliding pill */}
              <div style={{
                position: 'absolute',
                top: 3,
                bottom: 3,
                ...getPillPosition(),
                background: 'rgba(255, 255, 255, 0.15)',
                backdropFilter: 'blur(32px)',
                WebkitBackdropFilter: 'blur(32px)',
                borderRadius: 9999,
                border: '1px solid rgba(255, 255, 255, 0.25)',
                boxShadow: '0 16px 40px rgba(0,0,0,0.1), inset 0 1px 0 rgba(255,255,255,0.4)',
                transition: 'left 0.3s cubic-bezier(0.4, 0, 0.2, 1), width 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                zIndex: 1
              }} />
              
              {(['past','now','future'] as const).map((m) => (
                <button key={m}
                  ref={(el) => { buttonRefs.current[m] = el }}
                  onClick={() => handleModeChange(m)}
                  onMouseEnter={() => setHoveredOption(m)}
                  onMouseLeave={() => setHoveredOption(null)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 9999,
                    border:'none',
                    background: 'transparent',
                    color:'var(--glassText)',
                    cursor: 'pointer',
                    transition: 'color 0.2s ease',
                    position: 'relative',
                    zIndex: 2,
                    fontWeight: timelineState.mode === m ? 500 : 400,
                    flex: 1,
                    textAlign: 'center' as const,
                    fontSize: '11px',
                    lineHeight: '1.2',
                    outline: 'none'
                  }}
                  className="timeline-button"
                >{m === 'past' ? 'Historical' : m === 'now' ? 'Real-Time' : 'Future'}</button>
              ))}
            </div>
        
            {/* Date Picker Button - Redesigned with frosted glass look */}
            <button
              onClick={() => {
                // Don't show picker in "now" mode or when locked
                if (timelineState.mode !== 'now' && !controlsDisabled) {
                  setShowPicker(!showPicker)
                }
              }}
              disabled={timelineState.mode === 'now' || controlsDisabled}
              style={{
                padding: '6px 10px',
                borderRadius: 9999,
                border: '1px solid var(--datePickerBorder, rgba(255, 255, 255, 0.2))',
                background: 'var(--datePickerBg, rgba(255, 255, 255, 0.1))',
                backdropFilter: 'blur(12px)',
                WebkitBackdropFilter: 'blur(12px)',
                color: 'var(--glassText)',
                cursor: (timelineState.mode === 'now' || controlsDisabled) ? 'not-allowed' : 'pointer',
                opacity: (timelineState.mode === 'now' || controlsDisabled) ? 0.4 : 1,
                transition: 'all 0.2s ease',
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                position: 'relative',
                flex: '0 0 auto',
                pointerEvents: controlsDisabled ? 'none' : 'auto',
                boxShadow: (timelineState.mode === 'now' || controlsDisabled)
                  ? 'none'
                  : '0 4px 12px rgba(0,0,0,0.08), inset 0 1px 0 rgba(255,255,255,0.15)',
                height: 28
              }}
              title={(timelineState.mode === 'now' || controlsDisabled)
                ? (controlsDisabled ? 'Timeline locked while data loads' : 'Click "Historical" or "Future" first to enable date selection')
                : 'Click to select date'}
            >
              {/* Calendar Icon - SVG for consistency */}
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ opacity: 0.8 }}
              >
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                <line x1="16" y1="2" x2="16" y2="6"/>
                <line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
              </svg>
              
              {/* Date display */}
              <span style={{
                fontSize: '11px',
                fontWeight: 500,
                letterSpacing: '-0.01em',
                lineHeight: '1.2'
              }}>
                {timelineState.date}
              </span>
              
              {/* Chevron indicator when active */}
              {timelineState.mode !== 'now' && (
                <svg
                  width="10"
                  height="10"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  style={{
                    opacity: 0.6,
                    transform: showPicker ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.2s ease'
                  }}
                >
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
              )}
            </button>
            {/* Hint for users in "now" mode - hide if locked to avoid confusion */}
            {timelineState.mode === 'now' && !controlsDisabled && (
              <div style={{
                position: 'absolute',
                bottom: 'calc(100% + 8px)',
                right: 0,
                padding: '5px 8px',
                borderRadius: 6,
                background: 'rgba(59, 130, 246, 0.9)',
                color: 'white',
                fontSize: '10px',
                whiteSpace: 'nowrap',
                boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
                animation: 'pulse 2s infinite',
                lineHeight: '1.2'
              }}>
                ← Click "Historical" or "Future" to change date
                <style>{`
                  @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.7; }
                  }
                `}</style>
              </div>
            )}
          </div>
          
          {/* Bottom row: Time Slider - with frosted glass background */}
          <div style={{
            pointerEvents: controlsDisabled ? 'none' : 'auto',
            width: '100%',
            display: 'flex',
            justifyContent: 'center',
            padding: '6px 10px',
            borderRadius: 10,
            background: 'var(--sliderContainerBg, rgba(255, 255, 255, 0.08))',
            border: '1px solid var(--sliderContainerBorder, rgba(255, 255, 255, 0.1))',
            backdropFilter: 'blur(8px)',
            WebkitBackdropFilter: 'blur(8px)'
          }}>
            <TimeSlider
              value={timelineState.hour}
              min={0}
              max={23}
              disabled={timelineState.mode === 'now' || controlsDisabled}
              onChange={handleHourChange}
            />
          </div>
        </div>
      {showPicker && !controlsDisabled && (
        <div
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 8px)', // Positioned above
            right: 0,
            zIndex: 1400
          }}
          onClick={() => {
            // Calendar container click handler
          }}
        >
          <style>{`
            /* Custom styles for react-datepicker to match your theme */
            .react-datepicker {
              backdrop-filter: blur(36px);
              -webkit-backdrop-filter: blur(36px);
              background: var(--glassBg) !important;
              border: 1px solid var(--glassBorder) !important;
              border-radius: 12px !important;
              font-family: inherit !important;
              box-shadow: 0 28px 56px -8px rgba(0,0,0,0.1), 0 14px 28px -4px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,0.2) !important;
            }
            .react-datepicker__header {
              background: transparent !important;
              border-bottom: 1px solid var(--glassBorder) !important;
              padding-top: 12px !important;
            }
            .react-datepicker__current-month {
              color: var(--glassText) !important;
              font-weight: 600 !important;
              margin-bottom: 8px !important;
            }
            .react-datepicker__day-name {
              color: var(--muted) !important;
              font-size: 12px !important;
            }
            .react-datepicker__day {
              color: var(--glassText) !important;
              border-radius: 6px !important;
              transition: all 0.2s ease !important;
            }
            .react-datepicker__day:hover {
              background: var(--buttonBg) !important;
            }
            .react-datepicker__day--selected {
              background: #3B82F6 !important;
              color: white !important;
              font-weight: 600 !important;
            }
            .react-datepicker__day--today {
              background: var(--buttonBg) !important;
              font-weight: 600 !important;
            }
            .react-datepicker__day--outside-month {
              color: var(--muted) !important;
              opacity: 0.5 !important;
            }
            .react-datepicker__navigation {
              top: 16px !important;
            }
            .react-datepicker__navigation-icon::before {
              border-color: var(--glassText) !important;
            }
            .react-datepicker__triangle {
              display: none !important;
            }
          `}</style>
          <DatePicker
            selected={parseLocalDate(timelineState.date)}
            onChange={(date: Date | null) => {
              if (date) {
                const newDate = formatLocalDate(date)
                handleDateChange(newDate)
                setShowPicker(false)
              }
            }}
            inline
            calendarStartDay={0}
            showMonthDropdown
            showYearDropdown
            dropdownMode="select"
            dateFormat="yyyy-MM-dd"
            minDate={parseLocalDate('2020-01-01')}
            maxDate={parseLocalDate(addDays(formatLocalDate(new Date()), 7))} // 7 days in future
          />
        </div>
      )}
    </div>
    </>
  )
})
Timeline.displayName = 'Timeline'

export default Timeline
