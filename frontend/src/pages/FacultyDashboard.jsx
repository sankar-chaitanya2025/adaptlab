import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getFacultyDashboard } from '../api/client'
import Layout from '../components/Layout'
import LoadingSpinner from '../components/LoadingSpinner'

function StatCard({ label, value, sub, accent, danger }) {
  const color = accent ? 'var(--accent)' : danger ? 'var(--danger)' : 'var(--text-primary)'
  return (
    <div className="card" style={{ padding: 20 }}>
      <p style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</p>
      <p style={{ fontSize: 30, fontWeight: 800, marginTop: 6, color, letterSpacing: '-0.02em' }}>{value}</p>
      {sub && <p style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 4 }}>{sub}</p>}
    </div>
  )
}

function MiniBar({ value, max, color }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
      <div style={{ flex: 1, height: 8, background: 'var(--bg-tertiary)', borderRadius: 99, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 99, transition: 'width 0.4s' }} />
      </div>
      <span style={{ fontSize: 12, fontWeight: 600, color, minWidth: 36, textAlign: 'right' }}>
        {Math.round(value * 100)}%
      </span>
    </div>
  )
}

function zoneColor(zone) {
  return ['#ef4444', '#f59e0b', '#10a37f', '#3b82f6'][zone] ?? '#6e6e80'
}

export default function FacultyDashboard() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getFacultyDashboard()
      .then(setData)
      .catch(() => setError('Failed to load faculty dashboard. Make sure the backend is running.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Layout><LoadingSpinner size="lg" text="Loading dashboard…" /></Layout>
  if (error)   return <Layout><div className="alert alert-error">{error}</div></Layout>

  const {
    total_students, active_students, total_submissions,
    escalation_rate, gaming_flag_rate,
    concept_stats, students_in_zone_0, students_in_learning_zone,
  } = data

  return (
    <Layout>
      <div className="flex-between" style={{ marginBottom: 28 }}>
        <div>
          <h1 className="page-title" style={{ margin: 0 }}>Faculty Dashboard</h1>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 4 }}>
            Class-wide performance analytics
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn btn-secondary" onClick={() => navigate('/faculty/class')}>Students →</button>
          <button className="btn btn-secondary" onClick={() => navigate('/faculty/escalations')}>Escalations →</button>
        </div>
      </div>

      {/* Top stats */}
      <div className="grid-4" style={{ marginBottom: 28 }}>
        <StatCard label="Total Students" value={total_students} sub={`${active_students} active`} />
        <StatCard label="Submissions" value={total_submissions.toLocaleString()} />
        <StatCard
          label="Escalation Rate"
          value={`${Math.round(escalation_rate * 100)}%`}
          sub="students who needed help"
          accent={escalation_rate > 0.3}
        />
        <StatCard
          label="Gaming Flag Rate"
          value={`${Math.round(gaming_flag_rate * 100)}%`}
          sub="suspicious submissions"
          danger={gaming_flag_rate > 0.05}
        />
      </div>

      {/* Zone health */}
      <div className="grid-2" style={{ marginBottom: 28 }}>
        <div className="card" style={{ padding: 20 }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 14 }}>Student Zone Health</p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[
              { label: 'Zone 0 — Too Difficult', count: students_in_zone_0, color: '#ef4444', total: active_students },
              { label: 'Zone 1–2 — Learning Zone', count: students_in_learning_zone, color: '#10a37f', total: active_students },
            ].map(({ label, count, color, total }) => (
              <div key={label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{label}</span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{count}</span>
                </div>
                <div style={{ height: 6, background: 'var(--bg-tertiary)', borderRadius: 99, overflow: 'hidden' }}>
                  <div style={{ width: `${total > 0 ? (count / total) * 100 : 0}%`, height: '100%', background: color, borderRadius: 99 }} />
                </div>
              </div>
            ))}
          </div>
          {students_in_zone_0 > 0 && (
            <div className="alert alert-warning" style={{ marginTop: 14, fontSize: 13 }}>
              {students_in_zone_0} student{students_in_zone_0 > 1 ? 's' : ''} in Zone 0 — consider intervention.
            </div>
          )}
        </div>

        <div className="card" style={{ padding: 20 }}>
          <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 14 }}>
            Quick Actions
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <button className="btn btn-secondary" onClick={() => navigate('/faculty/class')}>
              📋 View All Students
            </button>
            <button className="btn btn-secondary" onClick={() => navigate('/faculty/escalations')}>
              🚨 Review Escalations
            </button>
            <button className="btn btn-secondary" onClick={() => window.location.reload()}>
              🔄 Refresh Data
            </button>
          </div>
        </div>
      </div>

      {/* Concept weakness table */}
      <div className="card" style={{ padding: 0 }}>
        <div className="card-header" style={{ padding: '16px 20px', marginBottom: 0 }}>
          <div className="flex-between">
            <p className="card-title">Concept Performance — Class Wide</p>
            <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Sorted by weakness (lowest first)</span>
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Concept</th>
                <th>Mean Score</th>
                <th>Min / Max</th>
                <th>Zone Distribution</th>
                <th>Students</th>
              </tr>
            </thead>
            <tbody>
              {concept_stats.map((cs) => {
                const barColor = cs.mean_score < 0.4 ? '#ef4444' : cs.mean_score < 0.75 ? '#10a37f' : '#3b82f6'
                return (
                  <tr key={cs.concept}>
                    <td style={{ fontWeight: 500, textTransform: 'capitalize' }}>
                      {cs.concept.replace('_', ' ')}
                    </td>
                    <td style={{ width: 200 }}>
                      <MiniBar value={cs.mean_score} max={1} color={barColor} />
                    </td>
                    <td style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                      {Math.round(cs.min_score * 100)}% / {Math.round(cs.max_score * 100)}%
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: 4 }}>
                        {[cs.in_zone_0, cs.in_zone_1, cs.in_zone_2, cs.in_zone_3].map((n, z) =>
                          n > 0 ? (
                            <span key={z} style={{
                              background: zoneColor(z) + '22',
                              color: zoneColor(z),
                              padding: '1px 7px',
                              borderRadius: 99,
                              fontSize: 11,
                              fontWeight: 600,
                            }}>Z{z}:{n}</span>
                          ) : null
                        )}
                      </div>
                    </td>
                    <td style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{cs.students_seen}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  )
}
