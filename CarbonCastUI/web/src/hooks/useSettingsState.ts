import { useState, useEffect, useCallback } from 'react'

// Settings Modal Atom State
let isSettingsModalOpen = false
const settingsModalListeners: Set<() => void> = new Set()

export function useSettingsModalState() {
  const [isOpen, setIsOpenState] = useState(isSettingsModalOpen)
  
  useEffect(() => {
    const listener = () => setIsOpenState(isSettingsModalOpen)
    settingsModalListeners.add(listener)
    return () => { settingsModalListeners.delete(listener) }
  }, [])
  
  const setIsOpen = useCallback((value: boolean | ((prev: boolean) => boolean)) => {
    isSettingsModalOpen = typeof value === 'function' ? value(isSettingsModalOpen) : value
    settingsModalListeners.forEach(fn => fn())
  }, [])
  
  const toggleOpen = useCallback(() => {
    isSettingsModalOpen = !isSettingsModalOpen
    settingsModalListeners.forEach(fn => fn())
  }, [])
  
  return { isOpen, setIsOpen, toggleOpen }
}

// Colorblind mode state
let colorblindModeEnabled = (() => {
  if (typeof window !== 'undefined') {
    return localStorage.getItem('colorblindMode') === 'true'
  }
  return false
})()
const colorblindListeners: Set<() => void> = new Set()

export function useColorblindMode() {
  const [isEnabled, setIsEnabledState] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('colorblindMode')
      return saved === 'true'
    }
    return false
  })
  
  useEffect(() => {
    const listener = () => setIsEnabledState(colorblindModeEnabled)
    colorblindListeners.add(listener)
    return () => { colorblindListeners.delete(listener) }
  }, [])
  
  const setEnabled = useCallback((value: boolean) => {
    colorblindModeEnabled = value
    localStorage.setItem('colorblindMode', String(value))
    colorblindListeners.forEach(fn => fn())
  }, [])
  
  return { isEnabled, setEnabled }
}