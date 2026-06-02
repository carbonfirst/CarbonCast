import { useEffect, useMemo, useRef } from 'react'
import type { Map as MlMap, Expression } from 'maplibre-gl'
// mapbox-choropleth expects a Mapbox GL JS compatible API. MapLibre matches it.
// We'll keep our own expression path for performance, but this keeps the door open
// to use mapbox-choropleth bins if/when needed.
import type { TimelineState } from '../hooks/cache'

type Props = {
  map: MlMap | null
  selectedRegion: string | null
  onRegionClick: (regionName: string) => void
  onRegionHover?: (regionName: string | null, screen?: { x: number, y: number } | null) => void
  carbonIntensityData: any
  loading: boolean
  error: string | null
  timelineState: TimelineState
}

function getColor(d: number | undefined) {
  const v = d ?? -1
  return v > 1200 ? '#48190A'
    : v > 1000 ? '#6C2D00'
    : v > 800 ? '#904006'
    : v > 600 ? '#B4560D'
    : v > 500 ? '#C45F00'
    : v > 400 ? '#D97914'
    : v > 300 ? '#feb204'
    : v > 250 ? '#FFCC00'
    : v > 200 ? '#F2D40C'
    : v > 125 ? '#F7F55F'
    : v > 100 ? '#4cf036'
    : v > 50 ? '#28e40f'
    : v > -1 ? '#2fca2c'
    : '#00000000'
}

export default function MapLibreChoropleth({ map, selectedRegion, onRegionClick, onRegionHover, carbonIntensityData, loading, error }: Props){
  const hoveredIdRef = useRef<string | number | null>(null)
  const hasData = !!carbonIntensityData && !loading && !error

  // Build a color expression matching region name to intensity color
  const fillColorExpr: Expression = useMemo(() => {
    const pairs: any[] = []
    if (hasData) {
      carbonIntensityData.forEach((item: any) => {
        const name = item.zoneName || item.region || item.name
        const color = getColor(item.carbonIntensity)
        if (name) {
          pairs.push(name, color)
        }
      })
    }
    // [ 'match', [ 'coalesce', ['get','zoneName'], ['get','name'] ], ...pairs, 'rgba(0,0,0,0)' ]
    return ['match', ['coalesce', ['get','zoneName'], ['get','name']], ...pairs, 'rgba(0,0,0,0)'] as unknown as Expression
  }, [carbonIntensityData, hasData])

  useEffect(() => {
    if (!map) return
    const sourceId = 'regions-src'
    const fillId = 'regions-fill'
    const outlineId = 'regions-outline'
    const selectedId = 'regions-selected-outline'

    // Load geojson from window
    const geo: any = (window as any).statesData || (window as any).statesData1
    if (!geo) return

    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, {
        type: 'geojson',
        data: geo,
        promoteId: 'zoneName' in (geo.features?.[0]?.properties || {}) ? 'zoneName' : 'name'
      } as any)

      map.addLayer({
        id: fillId,
        type: 'fill',
        source: sourceId,
        paint: {
          'fill-color': fillColorExpr as any,
          'fill-opacity': [
            'case',
            ['boolean', ['feature-state', 'hover'], false], 0.45,
            hasData ? 0.62 : 0
          ]
        }
      })

      map.addLayer({
        id: outlineId,
        type: 'line',
        source: sourceId,
        paint: {
          'line-color': ['coalesce', ['to-color', ['var', 'regionStroke']], '#A3A3A3'],
          'line-width': 1.5,
          'line-opacity': 1
        }
      })

      map.addLayer({
        id: selectedId,
        type: 'line',
        source: sourceId,
        filter: ['==', ['coalesce', ['get','zoneName'], ['get','name']], selectedRegion || ''],
        paint: {
          'line-color': ['coalesce', ['to-color', ['var', 'regionSelected']], '#333'],
          'line-width': 3
        }
      })

      // Hover handling
      const onMove = (e: any) => {
        const f = map.queryRenderedFeatures(e.point, { layers: [fillId] })?.[0]
        if (hoveredIdRef.current != null && f?.id !== hoveredIdRef.current) {
          try { map.setFeatureState({ source: sourceId, id: hoveredIdRef.current }, { hover: false }) } catch {}
          hoveredIdRef.current = null
        }
        if (f) {
          hoveredIdRef.current = f.id as any
          try { map.setFeatureState({ source: sourceId, id: f.id as any }, { hover: true }) } catch {}
          const name = f.properties?.zoneName || f.properties?.name
          onRegionHover?.(name || null, { x: e.point.x, y: e.point.y })
        } else {
          onRegionHover?.(null, null)
        }
      }
      const onLeave = () => {
        if (hoveredIdRef.current != null) {
          try { map.setFeatureState({ source: sourceId, id: hoveredIdRef.current }, { hover: false }) } catch {}
          hoveredIdRef.current = null
        }
        onRegionHover?.(null, null)
      }
      const onClick = (e: any) => {
        const f = map.queryRenderedFeatures(e.point, { layers: [fillId] })?.[0]
        if (!f) return
        const name = f.properties?.zoneName || f.properties?.name
        if (name) onRegionClick(name)
        const b = f.geometry && (f as any).geometry?.coordinates ? (f as any).bbox || null : null
        if (b) {
          try { (map as any).fitBounds(b, { padding: 20, maxZoom: 6 }) } catch {}
        }
        map.setFilter(selectedId, ['==', ['coalesce', ['get','zoneName'], ['get','name']], name || ''])
      }
      map.on('mousemove', fillId, onMove)
      map.on('mouseleave', fillId, onLeave)
      map.on('click', fillId, onClick)

      return () => {
        map.off('mousemove', fillId, onMove)
        map.off('mouseleave', fillId, onLeave)
        map.off('click', fillId, onClick)
        try { map.removeLayer(selectedId) } catch {}
        try { map.removeLayer(outlineId) } catch {}
        try { map.removeLayer(fillId) } catch {}
        try { (map.getSource(sourceId) as any)?.setData({ type:'FeatureCollection', features: [] }) } catch {}
        try { map.removeSource(sourceId) } catch {}
      }
    } else {
      // Update existing layers when props change
      try { map.setPaintProperty(fillId, 'fill-color', fillColorExpr as any) } catch {}
      try { map.setFilter(selectedId, ['==', ['coalesce', ['get','zoneName'], ['get','name']], selectedRegion || '']) } catch {}
      try { map.setPaintProperty(fillId, 'fill-opacity', ['case', ['boolean', ['feature-state','hover'], false], 0.45, hasData ? 0.62 : 0] as any) } catch {}
    }
  }, [map, fillColorExpr, selectedRegion, hasData, onRegionClick, onRegionHover])

  return null
}


