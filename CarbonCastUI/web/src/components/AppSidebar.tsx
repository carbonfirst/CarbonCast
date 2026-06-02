import React, { memo } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import './AppSidebar.css'
import { setHoveredZone } from './InfoPopover'

interface SidebarItem {
  id: string
  icon: React.ReactNode
  label: string
  path?: string
  onClick?: () => void
}

const AppSidebar = memo(() => {
  const navigate = useNavigate()
  const location = useLocation()

  const navigationItems: SidebarItem[] = [
    {
      id: 'map',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <rect x="2" y="2" width="20" height="20" rx="2" />
          <path d="M9 2v20M15 2v20M2 9h20M2 15h20" />
        </svg>
      ),
      label: 'Map',
      path: '/map'
    },
    {
      id: 'rankings',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M3 3v18h18" />
          <path d="M7 16V12M11 16V8M15 16V10M19 16V6" />
        </svg>
      ),
      label: 'Rankings',
      path: '/rankings'
    },
    {
      id: 'insights',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 6v6l4 2" />
        </svg>
      ),
      label: 'Insights',
      path: '/insights'
    }
  ]

  const bottomItems: SidebarItem[] = [
    {
      id: 'api-docs',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <path d="M14 2v6h6" />
          <path d="M16 13H8M16 17H8M10 9H8" />
        </svg>
      ),
      label: 'API Documentation',
      path: 'https://github.com/carbonfirst/CarbonCast/blob/django_apis_sqlite/README.md'
    },
    {
      id: 'help',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3M12 17h.01" />
        </svg>
      ),
      label: 'Help',
      onClick: () => { /* Help clicked - no-op for now */ }
    },
    {
      id: 'settings',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="3" />
          <path d="M12 1v6M12 17v6M4.22 4.22l4.24 4.24M15.54 15.54l4.24 4.24M1 12h6M17 12h6M4.22 19.78l4.24-4.24M15.54 8.46l4.24-4.24" />
        </svg>
      ),
      label: 'Settings',
      onClick: () => { /* Settings clicked - no-op for now */ }
    }
  ]

  const handleItemClick = (item: SidebarItem) => {
    if (item.path) {
      // Check if it's an external URL
      if (item.path.startsWith('http://') || item.path.startsWith('https://')) {
        window.open(item.path, '_blank', 'noopener,noreferrer')
      } else {
        navigate(item.path)
      }
    } else if (item.onClick) {
      item.onClick()
    }
  }

  const isActive = (path?: string) => {
    if (!path) return false
    return location.pathname.startsWith(path)
  }

  return (
    <div className="app-sidebar" onMouseEnter={() => setHoveredZone(null)}>
      {/* Logo */}
      <div className="sidebar-logo">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.7" />
          <path d="M8 14c2-3 6-3 8 0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          <circle cx="10" cy="10" r="1" fill="currentColor" />
          <circle cx="14" cy="10" r="1" fill="currentColor" />
        </svg>
      </div>

      {/* Navigation Items */}
      <nav className="sidebar-nav">
        {navigationItems.map((item) => (
          <button
            key={item.id}
            className={`sidebar-item ${isActive(item.path) ? 'active' : ''}`}
            onClick={() => handleItemClick(item)}
            aria-label={item.label}
            title={item.label}
          >
            {item.icon}
          </button>
        ))}
      </nav>

      {/* Bottom Items */}
      <div className="sidebar-bottom">
        {bottomItems.map((item) => (
          <button
            key={item.id}
            className="sidebar-item"
            onClick={() => handleItemClick(item)}
            aria-label={item.label}
            title={item.label}
          >
            {item.icon}
          </button>
        ))}
      </div>
    </div>
  )
})

AppSidebar.displayName = 'AppSidebar'

export default AppSidebar