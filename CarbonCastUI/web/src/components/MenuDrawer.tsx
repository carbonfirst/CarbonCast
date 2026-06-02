import { useEffect } from 'react'

type Props = {
  open: boolean
  onClose: () => void
}

export default function MenuDrawer({ open, onClose }: Props) {
  useEffect(() => {
    const onEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onEsc as any)
    return () => window.removeEventListener('keydown', onEsc as any)
  }, [onClose])

  if (!open) return null

  return (
    <div style={{ position:'fixed', inset:0, zIndex:1400 }}>
      <div
        onClick={onClose}
        style={{ position:'absolute', inset:0, background:'rgba(0,0,0,0.35)' }}
      />

      <div
        role="dialog"
        aria-modal="true"
        style={{ position:'absolute', top:0, left:0, height:'100%', width:360,
          WebkitBackdropFilter:'blur(12px)', backdropFilter:'blur(12px)',
          background:'var(--glassBg)', color:'var(--glassText)', borderRight:'1px solid var(--glassBorder)',
          boxShadow:'0 10px 15px -3px rgba(0,0,0,0.5), 0 4px 6px -4px rgba(0,0,0,0.4)'
        }}
      >
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'14px 16px', borderBottom:'1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ display:'flex', gap:8, alignItems:'center' }}>
            <button onClick={onClose} aria-label="Close" title="Close"
              style={{ background:'transparent', border:'none', color:'var(--glassText)', fontSize:20, cursor:'pointer' }}>←</button>
            <div style={{ fontWeight:600 }}>Menu</div>
          </div>
          <div style={{ opacity:0.8, fontSize:20 }}>⋯</div>
        </div>

        <div style={{ padding:16, display:'grid', gap:16 }}>
          <div>
            <div style={{ fontSize:12, letterSpacing:0.4, color:'#9CA3AF', marginBottom:8 }}>MODE</div>
            <div style={{ display:'flex', gap:8, background:'rgba(255,255,255,0.08)', border:'1px solid var(--glassBorder)', padding:6, borderRadius:999 }}>
              <button style={{ background:'#10B981', color:'#fff', border:'none', borderRadius:999, padding:'6px 10px', cursor:'pointer' }}>Electricity</button>
              <button style={{ background:'transparent', color:'var(--glassText)', opacity:0.85, border:'none', borderRadius:999, padding:'6px 10px', cursor:'pointer' }}>Emissions</button>
            </div>
          </div>

          <div>
            <div style={{ fontSize:12, letterSpacing:0.4, color:'#9CA3AF', marginBottom:8 }}>LAYERS</div>
            <div style={{ display:'grid', gap:10 }}>
              <label style={{ display:'flex', alignItems:'center', justifyContent:'space-between', background:'rgba(255,255,255,0.08)', border:'1px solid var(--glassBorder)', padding:'10px 12px', borderRadius:12 }}>
                <span>Region borders</span>
                <input type="checkbox" defaultChecked readOnly />
              </label>
              <label style={{ display:'flex', alignItems:'center', justifyContent:'space-between', background:'rgba(255,255,255,0.08)', border:'1px solid var(--glassBorder)', padding:'10px 12px', borderRadius:12 }}>
                <span>Labels</span>
                <input type="checkbox" defaultChecked readOnly />
              </label>
            </div>
          </div>

          <div>
            <div style={{ fontSize:12, letterSpacing:0.4, color:'#9CA3AF', marginBottom:8 }}>APPEARANCE</div>
            <label style={{ display:'flex', alignItems:'center', justifyContent:'space-between', background:'rgba(255,255,255,0.08)', border:'1px solid var(--glassBorder)', padding:'10px 12px', borderRadius:12 }}>
              <span>Glass shadows</span>
              <input type="checkbox" defaultChecked readOnly />
            </label>
          </div>
        </div>
      </div>
    </div>
  )
}


