import React, { useState, useRef, useEffect } from 'react'
import { useTheme } from '../hooks/useTheme'
import { ThemeOptions } from '../utils/constants'
import { useSettingsModalState } from '../hooks/useSettingsState'
import { setHoveredZone } from './InfoPopover'

// Horizontal Divider
function HorizontalDivider() {
  return (
    <div style={{
      height: '1px',
      backgroundColor: 'rgba(255,255,255,0.1)',
      margin: '4px 0'
    }} />
  )
}

// Theme Toggle Button
function ThemeToggleButton({
  theme,
  icon,
  selectedTheme,
  setSelectedTheme
}: {
  theme: ThemeOptions
  icon: React.ReactNode
  selectedTheme: ThemeOptions
  setSelectedTheme: (theme: ThemeOptions) => void
}) {
  return (
    <button
      onClick={() => setSelectedTheme(theme)}
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '8px',
        backgroundColor: selectedTheme === theme ? 'rgba(255,255,255,0.2)' : 'transparent',
        border: 'none',
        borderRadius: '8px',
        cursor: 'pointer',
        color: 'inherit',
        transition: 'background-color 0.2s ease'
      }}
    >
      {icon}
    </button>
  )
}

// Theme Toggle Group
function ThemeToggleGroup() {
  const { selectedTheme, setSelectedTheme } = useTheme()
  
  return (
    <div style={{
      display: 'flex',
      width: '100%',
      alignItems: 'center',
      justifyContent: 'space-between',
      padding: '8px'
    }}>
      <span style={{ fontSize: '14px', fontWeight: 500 }}>
        Change theme
      </span>
      <div style={{ display: 'flex', gap: '4px' }}>
        <ThemeToggleButton
          theme={ThemeOptions.LIGHT}
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          }
          selectedTheme={selectedTheme}
          setSelectedTheme={setSelectedTheme}
        />
        <ThemeToggleButton
          theme={ThemeOptions.DARK}
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          }
          selectedTheme={selectedTheme}
          setSelectedTheme={setSelectedTheme}
        />
        <ThemeToggleButton
          theme={ThemeOptions.SYSTEM}
          icon={
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
              <line x1="8" y1="21" x2="16" y2="21" />
              <line x1="12" y1="17" x2="12" y2="21" />
            </svg>
          }
          selectedTheme={selectedTheme}
          setSelectedTheme={setSelectedTheme}
        />
      </div>
    </div>
  )
}

// About Section with Accordion
function AboutCarbonCast() {
  const [isExpanded, setIsExpanded] = useState(false)
  
  return (
    <div style={{ width: '100%', padding: '8px 8px 4px 8px' }}>
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        style={{
          display: 'flex',
          width: '100%',
          alignItems: 'center',
          justifyContent: 'space-between',
          background: 'none',
          border: 'none',
          color: 'inherit',
          cursor: 'pointer',
          padding: 0
        }}
      >
        <span style={{ fontSize: '14px', fontWeight: 500 }}>
          About CarbonCast
        </span>
        <svg 
          width="20" 
          height="20" 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2"
          style={{
            transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s ease'
          }}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      
      {isExpanded && (
        <div style={{
          marginTop: '12px',
          fontSize: '12px',
          opacity: 0.8,
          lineHeight: 1.5
        }}>
          <p style={{ marginBottom: '12px' }}>
            <a 
              href="https://carboncast.io" 
              target="_blank" 
              rel="noopener noreferrer"
              style={{ color: '#4ade80', textDecoration: 'none' }}
            >
              CarbonCast
            </a>
            {' '}provides real-time carbon intensity data for electricity grids across different regions.
          </p>
          
          <div style={{ marginBottom: '8px' }}>
            <a 
              href="https://github.com/carbonfirst/CarbonCast" 
              target="_blank" 
              rel="noopener noreferrer"
              style={{ color: '#4ade80', textDecoration: 'none' }}
            >
              GitHub Repository
            </a>
          </div>
          
          <div style={{ marginBottom: '8px' }}>
            <a 
              href="https://github.com/carbonfirst/CarbonCast/blob/django_apis_sqlite/README.md" 
              target="_blank" 
              rel="noopener noreferrer"
              style={{ color: '#4ade80', textDecoration: 'none' }}
            >
              API Documentation
            </a>
          </div>
          
          <p style={{ opacity: 0.6, marginTop: '12px' }}>
            Version 1.0.0
          </p>
        </div>
      )}
    </div>
  )
}

// Settings Modal Content
function SettingsModalContent() {
  return (
    <div style={{
      maxHeight: '80vh',
      overflowY: 'auto',
      padding: '12px' // Equal padding on all sides for balanced look
    }}>
      <ThemeToggleGroup />
      <HorizontalDivider />
      <AboutCarbonCast />
    </div>
  )
}

// Main Settings Modal Component
export default function SettingsModal() {
  const { isOpen, setIsOpen } = useSettingsModalState()
  const modalRef = useRef<HTMLDivElement>(null)
  
  const handleClose = () => {
    setIsOpen(false)
  }
  
  // Close modal when clicking outside
  useEffect(() => {
    if (!isOpen) return
    
    const handleClickOutside = (event: MouseEvent) => {
      if (modalRef.current && !modalRef.current.contains(event.target as Node)) {
        // Check if click was on the settings button itself
        const settingsButton = document.querySelector('[data-testid="settings-button"]')
        if (settingsButton && settingsButton.contains(event.target as Node)) {
          return
        }
        handleClose()
      }
    }
    
    // Add small delay to prevent immediate close on open click
    const timeoutId = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside)
    }, 100)
    
    return () => {
      clearTimeout(timeoutId)
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])
  
  // Close on escape key
  useEffect(() => {
    if (!isOpen) return
    
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        handleClose()
      }
    }
    
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [isOpen])
  
  if (!isOpen) return null
  
  // Calculate position: button is at top:16, right:16
  // Button is approximately 44px wide (20px icon + 24px padding)
  // Modal should be to the left: right = 16 + 44 + 8 (gap) = 68px
  return (
    <div
      ref={modalRef}
      onMouseEnter={() => setHoveredZone(null)}
      style={{
        position: 'fixed',
        top: 16, // Same as TopControls container - aligns top of modal with top of settings button
        right: 68, // Positioned to the left of the control buttons (16px margin + 44px button + 8px gap)
        zIndex: 1400,
        width: '280px',
        WebkitBackdropFilter: 'blur(64px) saturate(200%)',
        backdropFilter: 'blur(64px) saturate(200%)',
        background: 'var(--legendBg)',
        border: '1px solid var(--legendBorder)',
        color: 'var(--glassText)',
        borderRadius: '16px',
        boxShadow: '0 16px 32px -4px rgba(0,0,0,0.08), 0 8px 16px -2px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.3)',
        animation: 'fadeIn 0.15s ease-out'
      }}
    >
      <SettingsModalContent />
    </div>
  )
}

// Settings Button Component (to be used in TopControls)
export function SettingsButton() {
  const { toggleOpen } = useSettingsModalState()
  
  return (
    <button
      onClick={toggleOpen}
      data-testid="settings-button"
      aria-label="Settings"
      title="Settings"
      className="button-animation"
      style={{
        WebkitBackdropFilter: 'blur(8px)',
        backdropFilter: 'blur(8px)',
        background: 'var(--glassBg)',
        border: '1px solid var(--glassBorder)',
        color: 'var(--glassText)',
        padding: '10px 12px',
        borderRadius: '10px',
        cursor: 'pointer',
        boxShadow: '0 10px 15px -3px rgba(0,0,0,0.3), 0 4px 6px -4px rgba(0,0,0,0.3)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    </button>
  )
}