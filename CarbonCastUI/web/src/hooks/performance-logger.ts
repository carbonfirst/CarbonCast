// Performance logging utility to diagnose loading bottlenecks
// All console logging removed for production
export class PerformanceLogger {
  private static timers = new Map<string, number>();
  private static counters = new Map<string, number>();

  static startTimer(label: string): void {
    this.timers.set(label, performance.now());
  }

  static endTimer(label: string): number {
    const start = this.timers.get(label);
    if (!start) {
      return 0;
    }
    
    const duration = performance.now() - start;
    this.timers.delete(label);
    
    return duration;
  }

  static increment(label: string, value: number = 1): void {
    const current = this.counters.get(label) || 0;
    this.counters.set(label, current + value);
  }

  static logDataSize(_label: string, _data: unknown): void {
    // No-op - logging disabled
  }

  static logNetworkRequest(_url: string): void {
    // No-op - logging disabled
  }

  static getStats(): Record<string, number> {
    return Object.fromEntries(this.counters);
  }

  static reset(): void {
    this.timers.clear();
    this.counters.clear();
  }
}