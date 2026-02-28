import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getClassOverview } from '../api/client'
import Layout from '../components/Layout'
import LoadingSpinner from '../components/LoadingSpinner'
import ZoneBadge from '../components/ZoneBadge'

function getZone(score) {
  if (score < 0.40) return 0
  if (score < 0.55) return 1
  if (score < 0.75) return 2
  return 3
}

export default function FacultyClassOverview() {
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')

  useEffect(() => {
    getClassOverview()
      .then(setData)
      .catch(() => setError('Failed to load class overview.'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <Layout><LoadingSpinner size="lg" text="Loading class overview…" /></Layout>
  if (error)   return <Layout><div className="alert alert-error">{error}</div></Layout>

  const students = data.students.filter((s) =>
    s.student_name?.toLowerCase().includes(search.toLowerCase()) ||
    s.student_id.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <Layout>
      <div className="flex-between" style={{ marginBottom: 24 }}>
        <div>
          <button className="btn btn-ghost btn-sm" style={{ marginBottom: 8 }} onClick={() => navigate('/faculty')}>← Dashboard</button>
          <h1 className="page-title" style={{ margin: 0 }}>Class Overview</h1>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{data.total_students} students</span>
          <input
            className="form-input"
            style={{ width: 220 }}
            placeholder="Search by name or ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Student</th>
                <th>Mean Score</th>
                <th>Zone</th>
                <th>Weakest</th>
                <th>Strongest</th>
                <th>Submissions</th>
                <th>Escalations</th>
                <th>Flags</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s, i) => (
                <tr key={s.student_id}>
                  <td style={{ color: 'var(--text-tertiary)', fontSize: 12 }}>{i + 1}</td>
                  <td>
                    <div>
                      <p style={{ fontWeight: 500, fontSize: 14 }}>{s.student_name || s.student_id}</p>
                      {s.student_name && <p style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{s.student_id}</p>}
                    </div>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ width: 60, height: 6, background: 'var(--bg-tertiary)', borderRadius: 99, overflow: 'hidden' }}>
                        <div style={{
                          width: `${Math.round(s.mean_score * 100)}%`,
                          height: '100%',
                          borderRadius: 99,
                          background: s.mean_score < 0.4 ? '#ef4444' : s.mean_score < 0.75 ? '#10a37f' : '#3b82f6',
                        }} />
                      </div>
                      <span style={{ fontWeight: 600, fontSize: 13 }}>{Math.round(s.mean_score * 100)}%</span>
                    </div>
                  </td>
                  <td><ZoneBadge zone={getZone(s.mean_score)} /></td>
                  <td style={{ fontSize: 13, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                    {s.weakest_concept?.replace('_', ' ') || '—'}
                  </td>
                  <td style={{ fontSize: 13, color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                    {s.strongest_concept?.replace('_', ' ') || '—'}
                  </td>
                  <td style={{ fontSize: 13 }}>{s.total_submissions}</td>
                  <td>
                    {s.total_escalations > 0 ? (
                      <span style={{ fontSize: 13, color: 'var(--accent)', fontWeight: 600 }}>{s.total_escalations}</span>
                    ) : <span style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>0</span>}
                  </td>
                  <td>
                    {s.gaming_flag_count > 0 ? (
                      <span className="badge" style={{ background: 'var(--warning-light)', color: '#b45309', fontSize: 11 }}>
                        {s.gaming_flag_count} flags
                      </span>
                    ) : <span style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {students.length === 0 && (
          <div className="empty-state">
            <div className="empty-state-icon">🔍</div>
            <p className="empty-state-text">No students match your search.</p>
          </div>
        )}
      </div>
    </Layout>
  )
}
