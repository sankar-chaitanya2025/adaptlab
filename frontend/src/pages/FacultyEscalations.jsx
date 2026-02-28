import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getEscalations, resolveEscalation } from '../api/client'
import Layout from '../components/Layout'
import LoadingSpinner from '../components/LoadingSpinner'

const REASON_LABELS = {
  student_request: { label: 'Student Request', color: '#3b82f6', bg: '#dbeafe' },
  streak:          { label: 'Failure Streak',  color: '#b45309', bg: '#fef3c7' },
  low_capability:  { label: 'Low Capability',  color: '#b91c1c', bg: '#fee2e2' },
  conceptual_gap:  { label: 'Conceptual Gap',  color: '#7c3aed', bg: '#ede9fe' },
}

export default function FacultyEscalations() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [resolving, setResolving] = useState(null)

  const fetchData = () => {
    setLoading(true)
    getEscalations()
      .then(setData)
      .catch(() => setError('Failed to load escalations.'))
      .finally(() => setLoading(false))
  }

  useEffect(fetchData, [])

  const handleResolve = async (logId) => {
    setResolving(logId)
    try {
      await resolveEscalation(logId)
      // Optimistic update
      setData((d) => ({
        ...d,
        total: d.total - 1,
        escalations: d.escalations.filter((e) => e.log_id !== logId),
      }))
    } catch {
      setError('Failed to resolve escalation.')
    } finally {
      setResolving(null)
    }
  }

  if (loading) return <Layout><LoadingSpinner size="lg" text="Loading escalations…" /></Layout>
  if (error && !data) return <Layout><div className="alert alert-error">{error}</div></Layout>

  const escalations = data?.escalations ?? []

  return (
    <Layout>
      <div className="flex-between" style={{ marginBottom: 24 }}>
        <div>
          <button className="btn btn-ghost btn-sm" style={{ marginBottom: 8 }} onClick={() => navigate('/faculty')}>← Dashboard</button>
          <h1 className="page-title" style={{ margin: 0 }}>Escalation Queue</h1>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            {data?.total ?? 0} unresolved
          </span>
          <button className="btn btn-secondary btn-sm" onClick={fetchData}>🔄 Refresh</button>
        </div>
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {escalations.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">✅</div>
          <p className="empty-state-text">No unresolved escalations. The class is doing well!</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {escalations.map((e) => {
            const cfg = REASON_LABELS[e.reason] ?? { label: e.reason, color: '#6e6e80', bg: '#ececf1' }
            return (
              <div key={e.log_id} className="card" style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 20px', flexWrap: 'wrap' }}>
                {/* Reason badge */}
                <span style={{
                  display: 'inline-flex', alignItems: 'center',
                  padding: '4px 12px', borderRadius: 99, fontSize: 12,
                  fontWeight: 600, background: cfg.bg, color: cfg.color,
                  flexShrink: 0,
                }}>
                  {cfg.label}
                </span>

                {/* Info */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontWeight: 500, fontSize: 14 }}>
                    Student: <code style={{ fontSize: 13, background: 'var(--bg-secondary)', padding: '1px 6px', borderRadius: 4 }}>{e.student_id}</code>
                  </p>
                  <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                    Problem: {e.problem_id}
                    {' · '}
                    <span>{new Date(e.logged_at).toLocaleString()}</span>
                  </p>
                </div>

                {/* Resolve button */}
                <button
                  className="btn btn-primary btn-sm"
                  style={{ flexShrink: 0 }}
                  disabled={resolving === e.log_id}
                  onClick={() => handleResolve(e.log_id)}
                >
                  {resolving === e.log_id ? <span className="spinner" /> : null}
                  {resolving === e.log_id ? 'Resolving…' : '✓ Resolve'}
                </button>
              </div>
            )
          })}
        </div>
      )}

      {/* Legend */}
      <div className="card" style={{ marginTop: 32, padding: 20 }}>
        <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 12 }}>Escalation Reason Guide</p>
        <div className="grid-2">
          {Object.entries(REASON_LABELS).map(([key, cfg]) => (
            <div key={key} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <span style={{ background: cfg.bg, color: cfg.color, padding: '2px 10px', borderRadius: 99, fontSize: 11, fontWeight: 600, flexShrink: 0 }}>{cfg.label}</span>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                {key === 'student_request' && 'Student clicked "Deep explanation"'}
                {key === 'streak' && '3+ consecutive failures on same concept'}
                {key === 'low_capability' && 'Capability score dropped below 0.40'}
                {key === 'conceptual_gap' && 'Code compiles but passes <50% tests (non-surface error)'}
              </span>
            </div>
          ))}
        </div>
      </div>
    </Layout>
  )
}
