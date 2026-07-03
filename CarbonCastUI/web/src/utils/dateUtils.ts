/**
 * Utility functions for timezone-neutral date handling
 * 
 * The core issue: new Date("2024-09-14") interprets the string as midnight UTC,
 * which becomes the previous day in negative UTC offset timezones like America/New_York (UTC-4).
 * 
 * Solution: Parse dates as local time by appending 'T00:00:00' or using explicit date construction.
 */

/**
 * Parse a date string (YYYY-MM-DD) in a timezone-neutral way.
 * This ensures the date is interpreted as local time, not UTC.
 * 
 * @param dateString - Date string in YYYY-MM-DD format
 * @returns Date object representing the local date at midnight
 */
export function parseLocalDate(dateString: string): Date {
  // Method 1: Append 'T00:00:00' to force local time interpretation
  return new Date(dateString + 'T00:00:00')
}

/**
 * Alternative method: Parse date components explicitly to avoid timezone issues
 * 
 * @param dateString - Date string in YYYY-MM-DD format
 * @returns Date object representing the local date at midnight
 */
export function parseLocalDateExplicit(dateString: string): Date {
  const [year, month, day] = dateString.split('-').map(Number)
  return new Date(year, month - 1, day) // month is 0-based
}

/**
 * Format a Date object to YYYY-MM-DD string in local timezone
 * 
 * @param date - Date object
 * @returns Date string in YYYY-MM-DD format
 */
export function formatLocalDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/**
 * Get adjacent dates (previous and next day) for a given date string
 * 
 * @param dateString - Date string in YYYY-MM-DD format
 * @returns Array containing [previousDate, nextDate] as YYYY-MM-DD strings
 */
export function getAdjacentDates(dateString: string): string[] {
  const date = parseLocalDate(dateString)
  
  const prevDate = new Date(date)
  prevDate.setDate(date.getDate() - 1)
  
  const nextDate = new Date(date)
  nextDate.setDate(date.getDate() + 1)
  
  return [
    formatLocalDate(prevDate),
    formatLocalDate(nextDate)
  ]
}

/**
 * Get current date as YYYY-MM-DD string in local timezone
 *
 * @returns Current date string in YYYY-MM-DD format
 */
export function getCurrentLocalDate(): string {
  return formatLocalDate(new Date())
}

/**
 * Current UTC date as YYYY-MM-DD.
 *
 * The CarbonCast API stores and filters all timestamps in UTC (Django
 * TIME_ZONE='UTC'; ?hour= filters ts__hour in UTC). Any date+hour pair sent
 * to the API must therefore come from the UTC clock — mixing a UTC date
 * with a local hour (or vice versa) queries the wrong rows.
 */
export function getCurrentUtcDate(): string {
  return new Date().toISOString().split('T')[0]
}

/**
 * Current UTC hour (0-23), matching the API's ts__hour filtering.
 */
export function getCurrentUtcHour(): number {
  return new Date().getUTCHours()
}

/**
 * Check if a date string represents today in local timezone
 * 
 * @param dateString - Date string in YYYY-MM-DD format
 * @returns true if the date is today
 */
export function isToday(dateString: string): boolean {
  return dateString === getCurrentLocalDate()
}

/**
 * Add days to a date string and return the result as a date string
 * 
 * @param dateString - Date string in YYYY-MM-DD format
 * @param days - Number of days to add (can be negative)
 * @returns New date string in YYYY-MM-DD format
 */
export function addDays(dateString: string, days: number): string {
  const date = parseLocalDate(dateString)
  date.setDate(date.getDate() + days)
  return formatLocalDate(date)
}