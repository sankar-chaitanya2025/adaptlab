import { useEffect, useState } from 'react'
import { useApp } from '../context/AppContext'
import { getStudentHistory } from '../api/client'
import Layout from '../components/Layout'
import LoadingSpinner from '../components/LoadingSpinner'

const PAGE_SIZE = 25

export default function StudentHistory() {
  const { currentUser } = useApp()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [offset, setOffset] = useState(0)

  useEffect(() => {
    setLoading(true)
    getStudentHistory(currentUser.student_id, PAGE_SIZE, offset)
      .then(setData)
      .catch(() => setError('Failed to load history.'))
      .finally(() => setLoading(false))
  }, [currentUser.student_id, offset])

  return (
    <Layout>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <h1 className="page-title" style={{ margin: 0 }}>Submission History</h1>
        {data && <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{data.total} total submissions</span>}
      </div>

      {loading && <LoadingSpinner text="Loading history…" />}
      {error && <div className="alert alert-error">{error}</div>}

      {!loading && data && (
        <>
          {data.submissions.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-icon">📭</div>
              <p className="empty-state-text">No submissions yet. Start practicing!</p>
            </div>
          ) : (
            <div className="card" style={{ padding: 0 }}>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Problem</th>
                      <th>Pass Rate</th>
                      <th>Error Type</th>
                      <th>Status</th>
                      <th>Submitted</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.submissions.map((s) => (
                      <tr key={s.submission_id}>
                        <td style={{ fontWeight: 500 }}>
                          {s.problem_title || s.problem_id}
                        </td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div style={{
                              width: 60, height: 6, borderRadius: 99,
                              background: 'var(--bg-tertiary)', overflow: 'hidden'
                            }}>
                              <div style={{
                                height: '100%', borderRadius: 99,
                                width: `${Math.round(s.pass_rate * 100)}%`,
                                background: s.pass_rate === 1 ? 'var(--success)' : s.pass_rate > 0 ? 'var(--warning)' : 'var(--danger)',
                              }} />
                            </div>
                            <span style={{ fontSize: 13, fontWeight: 600 }}>{Math.round(s.pass_rate * 100)}%</span>
                          </div>
                        </td>
                        <td>
                          {s.error_type && s.error_type !== 'none' ? (
                            <span className="badge badge-concept" style={{ fontSize: 11 }}>{s.error_type}</span>
                          ) : (
                            <span style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>—</span>
                          )}
                        </td>
                        <td>
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                            {!s.compiled && <span className="badge" style={{ background: 'var(--danger-light)', color: '#b91c1c', fontSize: 11 }}>Syntax Error</span>}
                            {s.escalated && <span className="badge" style={{ background: 'var(--accent-light)', color: 'var(--accent)', fontSize: 11 }}>Escalated</span>}
                            {s.gaming_flagged && <span className="badge" style={{ background: 'var(--warning-light)', color: '#b45309', fontSize: 11 }}>Gaming Flag</span>}
                            {s.compiled && !s.escalated && !s.gaming_flagged && (
                              <span style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>—</span>
                            )}
                          </div>
                        </td>
                        <td style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                          {new Date(s.submitted_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Pagination */}
          {data.total > PAGE_SIZE && (
            <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 20 }}>
              <button
                className="btn btn-secondary btn-sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                ← Previous
              </button>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)', alignSelf: 'center' }}>
                {offset + 1}–{Math.min(offset + PAGE_SIZE, data.total)} of {data.total}
              </span>
              <button
                className="btn btn-secondary btn-sm"
                disabled={offset + PAGE_SIZE >= data.total}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}
    </Layout>
  )
}
