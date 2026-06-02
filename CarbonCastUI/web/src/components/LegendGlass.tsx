import { setHoveredZone } from './InfoPopover'

export default function LegendGlass(){
  return (
    <div
      onMouseEnter={() => setHoveredZone(null)}
      style={{ position:'fixed', right:16, bottom:16, zIndex:1200 }}>
      <div style={{
        WebkitBackdropFilter:'blur(64px) saturate(200%)',
        backdropFilter:'blur(64px) saturate(200%)',
        background:'var(--legendBg)',
        border:'1px solid var(--legendBorder)',
        padding: 14,
        borderRadius: 16,
        width: 280,
        color:'var(--glassText)',
        boxShadow:'0 16px 32px -4px rgba(0,0,0,0.08), 0 8px 16px -2px rgba(0,0,0,0.04), inset 0 1px 0 rgba(255,255,255,0.3)'
      }}>
        <div style={{
          fontSize: 12,
          marginBottom: 8,
          color:'var(--glassText)',
          fontWeight: 500,
          letterSpacing: '-0.01em'
        }}>
          Carbon intensity (gCO₂eq/kWh)
        </div>
        
        {/* Color bar */}
        <div style={{
          position:'relative',
          height: 10,
          borderRadius: 5,
          overflow:'hidden',
          border:'1px solid var(--legendBarBorder, rgba(255, 255, 255, 0.2))',
          background:'rgba(0,0,0,0.15)',
          boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.1)'
        }}>
          <div style={{
            position:'absolute',
            inset:0,
            background:'linear-gradient(90deg, #2fca2c 0%, #28e40f 8%, #4cf036 16%, #F7F55F 28%, #F2D40C 36%, #FFCC00 44%, #feb204 56%, #D97914 68%, #C45F00 76%, #B4560D 84%, #904006 92%, #6C2D00 97%, #48190A 100%)',
            borderRadius: 5
          }} />
        </div>
        
        {/* Simple labels below */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: 6,
          fontSize: 10,
          color: 'var(--muted)',
          fontWeight: 500
        }}>
          <span>0</span>
          <span>300</span>
          <span>600</span>
          <span>1000</span>
          <span>1200+</span>
        </div>
      </div>
    </div>
  )
}

