import { useEffect, useState } from 'react'
import { GeoJSON, useMap } from 'react-leaflet'
import type { GeoJSON as GeoJSONType } from 'geojson'
import L from 'leaflet'
import type { LeafletMouseEvent } from 'leaflet'
import { useRef } from 'react'
import type { TimelineState } from '../hooks/cache'

type ApiEntry = {
  region_code: string
  carbon_intensity_avg_direct: number
}

declare global {
  interface Window {
    statesData: GeoJSONType
  }
}

// Removed unused getColor function

interface ChoroplethProps {
  onRegionClick: (regionName: string) => void
  onRegionHover?: (regionName: string | null, screen?: { x: number, y: number } | null) => void
  onClearSelection?: () => void
  selectedRegion?: string | null
  timelineState?: TimelineState
  carbonIntensityData?: any
  loading?: boolean
  error?: string | null
}

export const Choropleth: React.FC<ChoroplethProps> = ({
  onRegionClick,
  onRegionHover,
  onClearSelection,
  selectedRegion
}) => {
  const map = useMap()
  const [, setZoneToValue] = useState<Record<string, number>>({})
  const layerSetRef = useRef<Set<L.Layer>>(new Set())

  const baseURL = `${window.location.protocol}//${window.location.hostname}:8000`

  useEffect(() => {
    fetch(`${baseURL}/v1/CarbonIntensity?region_code=all`)
      .then(r => r.json())
      .then((data) => {
        const out: Record<string, number> = {}
        ;(data?.data as ApiEntry[]).forEach((row) => {
          out[row.region_code] = row.carbon_intensity_avg_direct
        })
        setZoneToValue(out)
      })
      .catch(() => {})
  }, [baseURL])

  // remove Leaflet info/legend controls; handled by React UI

  const geojsonData = ((window as any).statesData || (window as any).statesData1) as GeoJSONType | undefined
  if (!geojsonData) return null

  // Apply styling based on selection; outlines only (darker), transparent fill
  const style = (feature: any) => {
    const name = feature?.properties?.zoneName || feature?.properties?.name
    const isSelected = !!selectedRegion && name === selectedRegion

    // Default: transparent fills, subtle borders
    const base: L.PathOptions = {
      fillOpacity: 0,
      weight: isSelected ? 3 : 1.5,
      // Theme-driven strokes from CSS vars
      color: getComputedStyle(document.documentElement).getPropertyValue(isSelected ? '--regionSelected' : '--regionStroke').trim() || (isSelected ? '#333' : '#A3A3A3'),
      opacity: 1,
    }
    return base
  }

  const onEachFeature = (feature: any, layer: L.Layer) => {
    const l = layer as L.Path
    ;(l as any).feature = feature
    // Track layers to refresh labels on zoom
    layerSetRef.current.add(layer)

    l.on({
      mouseover: (e: LeafletMouseEvent) => {
        const target = e.target as L.Path
        // Glassy hover with theme variables
        const cs = getComputedStyle(document.documentElement)
        const stroke = cs.getPropertyValue('--regionHoverStroke').trim() || '#666'
        const fill = cs.getPropertyValue('--regionHoverFill').trim() || 'rgba(255,255,255,0.25)'
        target.setStyle({ weight: 3, color: stroke, dashArray: '',
          fillColor: fill, fillOpacity: 0.5 })
        const name = (target as any).feature?.properties?.zoneName || (target as any).feature?.properties?.name
        if (onRegionHover) {
          const container = map.getContainer().getBoundingClientRect()
          const p = map.latLngToContainerPoint(e.latlng)
          onRegionHover(name, { x: container.left + p.x, y: container.top + p.y })
        }
      },
      mouseout: (e: LeafletMouseEvent) => {
        const target = e.target as any
        target.setStyle(style(target.feature))
        if (onRegionHover) onRegionHover(null, null)
      },
      click: (e: LeafletMouseEvent) => {
        // prevent map-level click handler from clearing selection immediately
        try { L.DomEvent.stopPropagation(e as any) } catch {}
        const layerAny = e.target as any
        if (typeof layerAny.getBounds === 'function') {
          const b = layerAny.getBounds()
          try { map.fitBounds(b, { padding: [20, 20] as unknown as L.PointExpression, maxZoom: 6 }) } catch {}
        }
        const name = layerAny.feature?.properties?.zoneName || layerAny.feature?.properties?.name
        if (name && onRegionClick) onRegionClick(name)
      }
    })
  }

  // No labels now (simplified per request)

  // Clear selection when clicking on empty map background
  useEffect(() => {
    if (!onClearSelection) return
    const handler = () => onClearSelection()
    map.on('click', handler)
    return () => {
      map.off('click', handler)
    }
  }, [map, onClearSelection])

  return (
    <GeoJSON data={geojsonData} style={style} onEachFeature={onEachFeature as any}>
      {/* State label tooltips on hover (simple, performant) */}
    </GeoJSON>
  )
}


