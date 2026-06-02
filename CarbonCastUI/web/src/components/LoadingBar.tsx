import React from 'react'

interface LoadingBarProps {
  isLoading: boolean
  message?: string
}

export const LoadingBar: React.FC<LoadingBarProps> = ({ isLoading, message }) => {
  if (!isLoading) return null

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      height: '3px',
      backgroundColor: 'rgba(59, 130, 246, 0.1)',
      zIndex: 9999,
      overflow: 'hidden'
    }}>
      <div style={{
        height: '100%',
        backgroundColor: '#3B82F6',
        animation: 'loading-bar 1.5s ease-in-out infinite',
        transformOrigin: 'left center'
      }} />
      {message && (
        <div style={{
          position: 'absolute',
          top: '8px',
          left: '50%',
          transform: 'translateX(-50%)',
          backgroundColor: 'rgba(0, 0, 0, 0.8)',
          color: 'white',
          padding: '4px 12px',
          borderRadius: '12px',
          fontSize: '12px',
          fontWeight: 500,
          whiteSpace: 'nowrap'
        }}>
          {message}
        </div>
      )}
      <style>{`
        @keyframes loading-bar {
          0% {
            transform: translateX(-100%) scaleX(0.5);
          }
          50% {
            transform: translateX(0%) scaleX(0.7);
          }
          100% {
            transform: translateX(100%) scaleX(0.5);
          }
        }
      `}</style>
    </div>
  )
}

// Also export a context-aware loading indicator for panels
export const PanelLoadingIndicator: React.FC<{ isLoading: boolean; text?: string }> = ({ isLoading, text = 'Loading more data...' }) => {
  if (!isLoading) return null

  return (
    <div style={{
      position: 'absolute',
      top: '60px',
      left: '50%',
      transform: 'translateX(-50%)',
      backgroundColor: 'rgba(59, 130, 246, 0.95)',
      color: 'white',
      padding: '6px 16px',
      borderRadius: '16px',
      fontSize: '13px',
      fontWeight: 500,
      display: 'flex',
      alignItems: 'center',
      gap: '8px',
      zIndex: 100,
      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)'
    }}>
      <span style={{
        display: 'inline-block',
        animation: 'spin 1s linear infinite'
      }}>⟳</span>
      {text}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  )
}