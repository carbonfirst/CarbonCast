// Debug logger for tracking state update issues
// Console logging disabled for production
interface LogEntry {
  timestamp: string
  type: string
  message: string
  data?: string
}

class DebugLogger {
  private logs: LogEntry[] = []
  private maxLogs = 500
  private enabled = false // Disabled by default
  private filter: string[] = [
    'RENDER',
    'EFFECT',
    'STATE UPDATE',
    'REF UPDATE',
    'HOUR CHANGE',
    'MapEM',
    'CarbonIntensity',
    'ElectricityMix'
  ]

  log(type: string, message: string, data?: unknown) {
    if (!this.enabled) return
    
    // Check if this log type should be captured
    const shouldCapture = this.filter.some(f => type.includes(f))
    if (!shouldCapture) return

    const entry: LogEntry = {
      timestamp: new Date().toISOString(),
      type,
      message,
      data: data ? JSON.stringify(data) : undefined
    }

    this.logs.push(entry)
    
    // Keep only last N logs
    if (this.logs.length > this.maxLogs) {
      this.logs.shift()
    }
  }

  getLogs(): LogEntry[] {
    return this.logs
  }

  getLogsAsText(): string {
    return this.logs.map(l =>
      `${l.timestamp} [${l.type}] ${l.message}${l.data ? ' - ' + l.data : ''}`
    ).join('\n')
  }

  saveLogs() {
    const text = this.getLogsAsText()
    localStorage.setItem('debug_logs', text)
  }

  downloadLogs() {
    const text = this.getLogsAsText()
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `debug_logs_${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  clear() {
    this.logs = []
    localStorage.removeItem('debug_logs')
  }

  setEnabled(enabled: boolean) {
    this.enabled = enabled
  }

  setFilter(filter: string[]) {
    this.filter = filter
  }

  // Get summary of state updates
  getStateSummary() {
    const stateUpdates = this.logs.filter(l => l.type.includes('STATE UPDATE'))
    const renders = this.logs.filter(l => l.type.includes('RENDER'))
    const effects = this.logs.filter(l => l.type.includes('EFFECT'))
    
    return {
      totalLogs: this.logs.length,
      stateUpdates: stateUpdates.length,
      renders: renders.length,
      effects: effects.length,
      lastStateUpdate: stateUpdates[stateUpdates.length - 1],
      lastRender: renders[renders.length - 1],
      timeline: this.logs.slice(-20) // Last 20 events
    }
  }
}

// Create singleton instance
export const debugLogger = new DebugLogger()

// Expose to window for easy access in console (silently)
if (typeof window !== 'undefined') {
  (window as unknown as { debugLogger: DebugLogger }).debugLogger = debugLogger
}