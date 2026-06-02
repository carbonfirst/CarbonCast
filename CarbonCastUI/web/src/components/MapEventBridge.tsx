import { useEffect } from 'react'
import { useMap } from 'react-leaflet'

export default function MapEventBridge(){
  const map = useMap()
  useEffect(() => {
    const onZoomIn = () => { try { map.zoomIn(); } catch {} }
    const onZoomOut = () => { try { map.zoomOut(); } catch {} }
    window.addEventListener('zoom-in' as any, onZoomIn)
    window.addEventListener('zoom-out' as any, onZoomOut)
    return () => {
      window.removeEventListener('zoom-in' as any, onZoomIn)
      window.removeEventListener('zoom-out' as any, onZoomOut)
    }
  }, [map])
  return null
}


