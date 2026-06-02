import { useEffect, useRef } from 'react'
import maplibregl, { Map as MlMap } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'

type Props = {
  onMapReady?: (map: MlMap) => void
}

export default function MapLibreMap({ onMapReady }: Props){
  const ref = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<MlMap | null>(null)

  useEffect(() => {
    if (!ref.current || mapRef.current) return
    const dark = document.documentElement.classList.contains('theme-dark')
    // Primary: MapLibre public demo style (vector tiles). Fallback to simple OSM raster if it fails.
    const primaryStyle = 'https://demotiles.maplibre.org/style.json'
    const fallbackStyle: any = {
      version: 8,
      sources: {
        osm: {
          type: 'raster',
          tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '&copy; OpenStreetMap contributors'
        }
      },
      layers: [
        { id:'background', type:'background', paint: { 'background-color': dark ? '#000000' : '#E6E8EB' } },
        { id:'osm', type:'raster', source:'osm' }
      ]
    }

    const map = new maplibregl.Map({
      container: ref.current,
      style: primaryStyle,
      center: [-98.5795, 39.8283],
      zoom: 4,
      attributionControl: true,
      dragRotate: false,
      touchPitch: false,
    })
    mapRef.current = map

    // remove labels and POIs for a clean look
    // No labels to hide; style is raster-only

    map.on('error', (e) => {
      try {
        // If style load failed, switch to fallback raster style
        const msg = (e as any)?.error?.message || ''
        if (msg.includes('Failed to load') || msg.includes('style')) {
          map.setStyle(fallbackStyle as any)
        }
      } catch {}
    })

    map.on('load', () => {
      try {
        // No-op for primary style; ensure at least one layer exists in fallback
      } catch {}
      onMapReady?.(map)
    })

    const onThemeChange = (e: any) => {
      const isDark = !!e?.detail?.dark
      try {
        map.setPaintProperty('background', 'background-color', isDark ? '#000000' : '#E6E8EB')
      } catch {}
    }
    window.addEventListener('theme-changed' as any, onThemeChange)

    return () => {
      window.removeEventListener('theme-changed' as any, onThemeChange)
      try { map.remove() } catch {}
    }
  }, [onMapReady])

  return <div ref={ref} style={{ position:'absolute', inset:0 }} />
}


