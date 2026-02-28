export default function LoadingSpinner({ size = 'md', text = '' }) {
  const cls = size === 'lg' ? 'spinner spinner-lg' : 'spinner'
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: 32 }}>
      <div className={cls} />
      {text && <span style={{ fontSize: 14, color: 'var(--text-secondary)' }}>{text}</span>}
    </div>
  )
}
