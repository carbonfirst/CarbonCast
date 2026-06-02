import { useEffect, useMemo, useState } from 'react'
import { TileLayer } from 'react-leaflet'

export default function DynamicTileLayer(){
  const [dark, setDark] = useState<boolean>(() => {
    try { return localStorage.getItem('theme') === 'dark' } catch { return true }
  })

  useEffect(() => {
    const onTheme = (e: any) => setDark(!!e?.detail?.dark)
    window.addEventListener('theme-changed' as any, onTheme)
    return () => window.removeEventListener('theme-changed' as any, onTheme)
  }, [])

  const config = useMemo(() => {
    // Use clean, label-free basemaps
    if (dark) {
      return {
        url: 'https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png',
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
      }
    }
    return {
      url: 'https://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}{r}.png',
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
    }
  }, [dark])

  return (
    <TileLayer url={config.url} attribution={config.attribution} />
  )
}


