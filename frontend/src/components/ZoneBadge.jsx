const ZONE_CONFIG = {
  0: { label: 'Too Difficult', color: '#b91c1c', bg: '#fee2e2' },
  1: { label: 'Easy',          color: '#b45309', bg: '#fef3c7' },
  2: { label: 'Learning Zone', color: '#065f46', bg: '#d1fae5' },
  3: { label: 'Mastery',       color: '#1d4ed8', bg: '#dbeafe' },
}

export default function ZoneBadge({ zone }) {
  const cfg = ZONE_CONFIG[zone] ?? ZONE_CONFIG[2]
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '2px 10px',
        borderRadius: 99,
        fontSize: 12,
        fontWeight: 500,
        background: cfg.bg,
        color: cfg.color,
      }}
    >
      {cfg.label}
    </span>
  )
}
