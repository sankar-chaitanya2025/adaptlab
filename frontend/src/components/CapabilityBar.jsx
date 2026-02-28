function getColor(score) {
  if (score < 0.40) return '#ef4444'
  if (score < 0.55) return '#f59e0b'
  if (score < 0.75) return '#10a37f'
  return '#3b82f6'
}

export default function CapabilityBar({ score = 0.5, showLabel = true }) {
  const pct = Math.round(score * 100)
  const color = getColor(score)
  return (
    <div style={{ width: '100%' }}>
      <div className="progress-bar-track">
        <div
          className="progress-bar-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      {showLabel && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 3 }}>
          <span style={{ fontSize: 11, fontWeight: 600, color }}>{pct}%</span>
        </div>
      )}
    </div>
  )
}
