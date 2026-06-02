// Theme options matching ElectricityMaps
export const ThemeOptions = {
  LIGHT: 'light',
  DARK: 'dark',
  SYSTEM: 'system'
} as const

export type ThemeOptions = typeof ThemeOptions[keyof typeof ThemeOptions]
