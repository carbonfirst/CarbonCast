// Centralized region mapping utilities

// Map region codes to display names
export const regionNames: Record<string, string> = {
  'US-NE-ISNE': 'New England',
  'US-NY-NYIS': 'New York',
  'US-MIDA-PJM': 'Mid-Atlantic',
  'US-SE-SOCO': 'Southeast',
  'US-FLA-FPL': 'Florida',
  'US-MIDW-MISO': 'Midwest',
  'US-TEX-ERCO': 'Texas',
  'US-CAL-CISO': 'California',
  'US-NW-BPAT': 'Northwest',
  'FR': 'France',
  'DE': 'Germany',
  'GB': 'Great Britain',
  'ES': 'Spain',
  'IT': 'Italy',
  'PL': 'Poland',
  // Sweden display names
  'SE': 'Sweden',
  'SE-SE1': 'Sweden',
  'SE-SE2': 'Sweden',
  'SE-SE3': 'Sweden',
  'SE-SE4': 'Sweden',
  // Denmark display names
  'DK': 'Denmark',
  'DK-DK1': 'Denmark',
  'DK-DK2': 'Denmark',
  // Italy display names
  'IT-CNO': 'Italy',
  'IT-CSO': 'Italy',
  'IT-NO': 'Italy',
  'IT-SAR': 'Italy',
  'IT-SIC': 'Italy',
  'IT-SO': 'Italy',
  // Norway display names
  'NO': 'Norway',
  'NO-NO1': 'Norway',
  'NO-NO2': 'Norway',
  'NO-NO3': 'Norway',
  'NO-NO4': 'Norway',
  'NO-NO5': 'Norway',
  // Great Britain display names (for sub-zones)
  'GB-NIR': 'Great Britain',
  'GB-ORK': 'Great Britain',
  'GB-ZET': 'Great Britain',
  // Denmark additional sub-zone
  'DK-BHM': 'Denmark',
  // France sub-zone
  'FR-COR': 'France',
  // Spain sub-zones
  'ES-CE': 'Spain',
  'ES-ML': 'Spain',
  // Greece sub-zone
  'GR-IS': 'Greece',
  // Portugal sub-zones
  'PT-MA': 'Portugal',
  'PT-AC': 'Portugal'
}

// Region groups - maps parent region to all its sub-regions on the map
// Used for: 1) Coloring all sub-regions the same, 2) Selecting all sub-regions together
export const regionGroups: Record<string, string[]> = {
  'SE': ['SE-SE1', 'SE-SE2', 'SE-SE3', 'SE-SE4'],
  'DK': ['DK-DK1', 'DK-DK2', 'DK-BHM'],
  'IT': ['IT-CNO', 'IT-CSO', 'IT-NO', 'IT-SAR', 'IT-SIC', 'IT-SO'],
  'NO': ['NO-NO1', 'NO-NO2', 'NO-NO3', 'NO-NO4', 'NO-NO5'],
  'GB': ['GB', 'GB-NIR', 'GB-ORK', 'GB-ZET'],
  'FR': ['FR', 'FR-COR'],
  'ES': ['ES', 'ES-CE', 'ES-ML'],
  'GR': ['GR', 'GR-IS'],
  'PT': ['PT', 'PT-MA', 'PT-AC']
}

// Reverse mapping: sub-region to parent region code
export const subRegionToParent: Record<string, string> = {
  'SE-SE1': 'SE',
  'SE-SE2': 'SE',
  'SE-SE3': 'SE',
  'SE-SE4': 'SE',
  'DK-DK1': 'DK',
  'DK-DK2': 'DK',
  'DK-BHM': 'DK',
  'IT-CNO': 'IT',
  'IT-CSO': 'IT',
  'IT-NO': 'IT',
  'IT-SAR': 'IT',
  'IT-SIC': 'IT',
  'IT-SO': 'IT',
  'NO-NO1': 'NO',
  'NO-NO2': 'NO',
  'NO-NO3': 'NO',
  'NO-NO4': 'NO',
  'NO-NO5': 'NO',
  'GB-NIR': 'GB',
  'GB-ORK': 'GB',
  'GB-ZET': 'GB',
  'FR-COR': 'FR',
  'ES-CE': 'ES',
  'ES-ML': 'ES',
  'GR-IS': 'GR',
  'PT-MA': 'PT',
  'PT-AC': 'PT'
}

// Get the parent region code for a zone (e.g., 'SE-SE1' -> 'SE')
export function getParentRegion(zoneName: string): string {
  return subRegionToParent[zoneName] || zoneName
}

// Get all sub-regions for a zone (including itself if it's a parent)
export function getAllSubRegions(zoneName: string): string[] {
  // If it's a parent region, return all sub-regions
  if (regionGroups[zoneName]) {
    return regionGroups[zoneName]
  }
  // If it's a sub-region, get its parent and return all siblings
  const parent = subRegionToParent[zoneName]
  if (parent && regionGroups[parent]) {
    return regionGroups[parent]
  }
  // Return the zone itself if it's not part of a group
  return [zoneName]
}

// Get the display zone ID (parent region code for grouped regions)
export function getDisplayZoneId(zoneName: string): string {
  return subRegionToParent[zoneName] || zoneName
}

// Region mapping from API codes to map region names
export const apiToMapRegionMapping: Record<string, string> = {
  // US regions
  'AECI': 'US-MIDW-AECI',
  'AZPS': 'US-SW-AZPS',
  'BANC': 'US-CAL-BANC',
  'BPAT': 'US-NW-BPAT',
  'CHPD': 'US-NW-CHPD',
  'CISO': 'US-CAL-CISO',
  'CPLE': 'US-CAR-CPLE',
  'CPLW': 'US-CAR-CPLW',
  'DOPD': 'US-NW-DOPD',
  'DUK': 'US-CAR-DUK',
  'EPE': 'US-SW-EPE',
  'ERCO': 'US-TEX-ERCO',
  'FMPP': 'US-FLA-FMPP',
  'FPC': 'US-FLA-FPC',
  'FPL': 'US-FLA-FPL',
  'GCPD': 'US-NW-GCPD',
  'GRID': 'US-NW-GRID',
  'GVL': 'US-FLA-GVL',
  'IPCO': 'US-NW-IPCO',
  'ISNE': 'US-NE-ISNE',
  'JEA': 'US-FLA-JEA',
  'LDWP': 'US-CAL-LDWP',
  'LGEE': 'US-MIDW-LGEE',
  'MISO': 'US-MIDW-MISO',
  'NEVP': 'US-NW-NEVP',
  'NWMT': 'US-NW-NWMT',
  'NYIS': 'US-NY-NYIS',
  'PACE': 'US-NW-PACE',
  'PACW': 'US-NW-PACW',
  'PGE': 'US-NW-PGE',
  'PJM': 'US-MIDA-PJM',
  'PNM': 'US-SW-PNM',
  'PSCO': 'US-NW-PSCO',
  'PSEI': 'US-NW-PSEI',
  'SC': 'US-CAR-SC',
  'SCEG': 'US-CAR-SCEG',
  'SCL': 'US-NW-SCL',
  'SOCO': 'US-SE-SOCO',
  'SPA': 'US-CENT-SPA',
  'SRP': 'US-SW-SRP',
  'SWPP': 'US-CENT-SWPP',
  'TAL': 'US-FLA-TAL',
  'TEC': 'US-FLA-TEC',
  'TEPC': 'US-SW-TEPC',
  'TIDC': 'US-CAL-TIDC',
  'TPWR': 'US-NW-TPWR',
  'TVA': 'US-TEN-TVA',
  'WACM': 'US-NW-WACM',
  'WALC': 'US-SW-WALC',
  // Canadian regions
  'ON': 'CA-ON',
  'CA-ON': 'CA-ON',
  // European regions (already work with 2-letter codes but adding some mappings)
  'AT': 'AT',
  'BE': 'BE',
  'BG': 'BG',
  'CH': 'CH',
  'CZ': 'CZ',
  'DE': 'DE',
  'DK': 'DK-DK1',
  'EE': 'EE',
  'ES': 'ES',
  'FI': 'FI',
  'FR': 'FR',
  'GB': 'GB',
  'GR': 'GR',
  'HR': 'HR',
  'HU': 'HU',
  'IE': 'IE',
  'IT': 'IT-CNO',
  'LT': 'LT',
  'LV': 'LV',
  'NL': 'NL',
  'PL': 'PL',
  'PT': 'PT',
  'RO': 'RO',
  'RS': 'RS',
  'SE': 'SE-SE1',
  'SI': 'SI',
  'SK': 'SK'
}

// Helper function to convert map region codes to API region codes
export function convertToApiRegionCode(mapRegionCode: string): string {
  // US regions: extract the last part after the last hyphen
  if (mapRegionCode.startsWith('US-')) {
    const parts = mapRegionCode.split('-')
    return parts[parts.length - 1] // Get the last part (e.g., "NYIS" from "US-NY-NYIS")
  }
  // EU regions remain the same
  return mapRegionCode
}

// Helper function to get display name for a region
export function getRegionDisplayName(regionCode: string): string {
  return regionNames[regionCode] || regionCode
}

// Helper function to get map region name from API region code
export function getMapRegionFromApiCode(apiRegionCode: string): string {
  return apiToMapRegionMapping[apiRegionCode] || apiRegionCode
}