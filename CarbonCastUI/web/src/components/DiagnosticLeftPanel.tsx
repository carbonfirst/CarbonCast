import React, { useEffect, useState } from 'react'
import { useCarbonIntensityData } from '../hooks/cache'
import { useEnergyMix } from '../hooks/useEnergyData'
import type { TimelineState } from '../hooks/cache'

interface DiagnosticProps {
  regionCode: string
  timelineState: TimelineState
}

export const DiagnosticPanel: React.FC<DiagnosticProps> = ({ regionCode, timelineState }) => {
  const [renderCount, setRenderCount] = useState(0)
  const { data: carbonData, loading, error, backgroundLoading } = useCarbonIntensityData(timelineState)
  const { data: energyData, total } = useEnergyMix(regionCode, timelineState)
  
  useEffect(() => {
    setRenderCount(prev => prev + 1)
  }, [])
  
  useEffect(() => {
    // Diagnostic logging disabled
  }, [carbonData, loading, backgroundLoading, error, regionCode, timelineState, renderCount])
  
  useEffect(() => {
    // Diagnostic logging disabled
  }, [energyData, total, regionCode, renderCount])
  
  // Try to compute carbon intensity the same way CarbonIntensityValue does
  useEffect(() => {
    if (!carbonData?.data || !Array.isArray(carbonData.data)) {
      return
    }
    
    // Diagnostic computation - no logging
  }, [carbonData, regionCode])
  
  return (
    <div style={{
      position: 'fixed',
      top: '10px',
      right: '10px',
      background: 'rgba(0,0,0,0.9)',
      color: 'white',
      padding: '10px',
      borderRadius: '5px',
      fontSize: '12px',
      maxWidth: '300px',
      zIndex: 9999
    }}>
      <h4 style={{ margin: '0 0 10px 0' }}>Diagnostic Info</h4>
      <div>Region: {regionCode}</div>
      <div>Mode: {timelineState.mode}</div>
      <div>Date: {timelineState.date}</div>
      <div>Hour: {timelineState.hour}</div>
      <hr style={{ margin: '5px 0' }} />
      <div>Carbon Data: {carbonData ? '✓' : '✗'}</div>
      <div>Data Length: {Array.isArray(carbonData?.data) ? carbonData.data.length : 0}</div>
      <div>Loading: {loading ? 'YES' : 'NO'}</div>
      <div>BG Loading: {backgroundLoading ? 'YES' : 'NO'}</div>
      <div>Update ID: {(carbonData as any)?._updateId || 'none'}</div>
      <hr style={{ margin: '5px 0' }} />
      <div>Energy Sources: {energyData.length}</div>
      <div>Total: {total}</div>
      <div>Renders: {renderCount}</div>
    </div>
  )
}