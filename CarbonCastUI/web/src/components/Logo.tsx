import React from 'react'

type Props = {
  className?: string
  color?: string
  style?: React.CSSProperties
}

export default function Logo({ className, color = 'currentColor', style }: Props) {
  return (
    <div className={className} style={{ display:'flex', alignItems:'center', gap:8, color, ...style }}>
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.6" />
        <path d="M6 14c2.5-4.5 9.5-4.5 12 0" stroke="currentColor" strokeWidth="2" strokeLinecap="round" opacity="0.9" />
        <circle cx="9" cy="10" r="1.5" fill="currentColor" />
        <circle cx="15" cy="10" r="1.5" fill="currentColor" />
      </svg>
      <span style={{ fontWeight:700, letterSpacing:0.2 }}>CarbonCast</span>
    </div>
  )
}


