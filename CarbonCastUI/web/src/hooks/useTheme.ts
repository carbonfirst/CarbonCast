import { useEffect, useLayoutEffect, useState, useCallback } from 'react'
import { ThemeOptions } from '../utils/constants'

// Global theme state - shared across all useTheme instances
let globalSelectedTheme: ThemeOptions = (() => {
  if (typeof window !== 'undefined') {
    const saved = localStorage.getItem('theme')
    if (saved && Object.values(ThemeOptions).includes(saved as ThemeOptions)) {
      return saved as ThemeOptions
    }
  }
  return ThemeOptions.SYSTEM
})()

// Listeners for theme state changes
const themeListeners: Set<() => void> = new Set()

// Helper to notify all listeners
function notifyThemeListeners() {
  themeListeners.forEach(fn => fn())
}

// Helper to apply theme to DOM
function applyThemeToDOM(isDark: boolean) {
  document.documentElement.classList.toggle('dark', isDark)
  // Force browser repaint
  void document.documentElement.offsetHeight
}

// Initialize theme on module load
if (typeof window !== 'undefined') {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
  const isDark = globalSelectedTheme === ThemeOptions.DARK ||
    (globalSelectedTheme === ThemeOptions.SYSTEM && prefersDark)
  applyThemeToDOM(isDark)
  
  // Listen for system preference changes
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (globalSelectedTheme === ThemeOptions.SYSTEM) {
      applyThemeToDOM(e.matches)
    }
    notifyThemeListeners()
  })
}

/**
 * Simple media query hook for detecting system dark mode preference
 */
function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.matchMedia(query).matches
    }
    return false
  })

  useEffect(() => {
    const mediaQuery = window.matchMedia(query)
    const handleChange = (event: MediaQueryListEvent) => {
      setMatches(event.matches)
    }

    setMatches(mediaQuery.matches)
    mediaQuery.addEventListener('change', handleChange)
    
    return () => {
      mediaQuery.removeEventListener('change', handleChange)
    }
  }, [query])

  return matches
}

/**
 * Hook that manages theme state and persistence - uses global state for consistency
 */
export function useTheme() {
  // Local state that syncs with global state
  const [selectedTheme, setSelectedThemeLocal] = useState<ThemeOptions>(globalSelectedTheme)

  const prefersDarkMode = useMediaQuery('(prefers-color-scheme: dark)')
  
  const isDarkMode =
    selectedTheme === ThemeOptions.DARK ||
    (selectedTheme === ThemeOptions.SYSTEM && prefersDarkMode)

  // Subscribe to global theme changes
  useEffect(() => {
    const listener = () => {
      setSelectedThemeLocal(globalSelectedTheme)
    }
    themeListeners.add(listener)
    return () => { themeListeners.delete(listener) }
  }, [])

  // Global setter that updates all instances
  const setSelectedTheme = useCallback((theme: ThemeOptions) => {
    globalSelectedTheme = theme
    localStorage.setItem('theme', theme)
    
    // Calculate and apply dark mode
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    const isDark = theme === ThemeOptions.DARK ||
      (theme === ThemeOptions.SYSTEM && prefersDark)
    applyThemeToDOM(isDark)
    
    notifyThemeListeners()
  }, [])

  // Apply theme to document when isDarkMode changes (initial load)
  useLayoutEffect(() => {
    applyThemeToDOM(isDarkMode)
  }, [isDarkMode])

  return {
    selectedTheme,
    setSelectedTheme,
    isDarkMode
  }
}

/**
 * Simple hook like ElectricityMaps useDarkMode
 */
export function useDarkMode() {
  const { isDarkMode } = useTheme()
  return isDarkMode
}
