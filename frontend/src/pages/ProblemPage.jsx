import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import Editor from '@monaco-editor/react'
import { useApp } from '../context/AppContext'
import { getNextProblem, getProblemById, submitCode } from '../api/client'
import Layout from '../components/Layout'
import ZoneBadge from '../components/ZoneBadge'
import LoadingSpinner from '../components/LoadingSpinner'
import styles from './ProblemPage.module.css'

const STARTER = `# Write your Python solution here\n`

export default function ProblemPage() {
  const { concept, problemId } = useParams()
  const { currentUser } = useApp()
  const navigate = useNavigate()

  const [problem, setProblem] = useState(null)
  const [selectionMeta, setSelectionMeta] = useState(null)
  const [code, setCode] = useState(STARTER)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [deepExplain, setDeepExplain] = useState(false)
  const [cooldown, setCooldown] = useState(0)

  // Load problem
  const loadProblem = useCallback(async () => {
    setLoading(true)
    setError('')
    setResult(null)
    setCode(STARTER)
    try {
      if (problemId) {
        const data = await getProblemById(problemId)
        setProblem(data.problem)
        setSelectionMeta(null)
      } else if (concept) {
        const data = await getNextProblem(currentUser.student_id, concept)
        setProblem(data.problem)
        setSelectionMeta({ band: data.band, zone: data.zone, fallback_used: data.fallback_used })
      }
    } catch (err) {
      if (err.response?.status === 404) {
        setError(`No more unseen problems for "${concept}". Try a different concept.`)
      } else {
        setError('Could not load a problem. Make sure the backend is running.')
      }
    } finally {
      setLoading(false)
    }
  }, [concept, problemId, currentUser.student_id])

  useEffect(() => { loadProblem() }, [loadProblem])

  // Cooldown timer
  useEffect(() => {
    if (cooldown <= 0) return
    const t = setInterval(() => setCooldown((c) => Math.max(0, c - 1)), 1000)
    return () => clearInterval(t)
  }, [cooldown])

  const handleSubmit = async () => {
    if (!problem || submitting || cooldown > 0) return
    setSubmitting(true)
    setError('')
    try {
      const data = await submitCode({
        student_id: currentUser.student_id,
        problem_id: problem.problem_id,
        code,
        deep_explain: deepExplain,
      })
      setResult(data)
      setDeepExplain(false)
    } catch (err) {
      if (err.response?.status === 429) {
        const secs = err.response.data?.cooldown_seconds_remaining || 60
        setCooldown(secs)
        setError(`Too many submissions. Please wait ${secs} seconds.`)
      } else {
        setError(err.response?.data?.detail || 'Submission failed. Please try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const handleNextProblem = () => {
    if (result?.next_problem) {
      navigate(`/problem/${result.next_problem.problem_id}`)
    } else {
      loadProblem()
    }
  }

  if (loading) return (
    <Layout fullWidth>
      <div className={styles.page}>
        <LoadingSpinner size="lg" text="Finding the right problem for you…" />
      </div>
    </Layout>
  )

  if (error && !problem) return (
    <Layout>
      <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>
      <button className="btn btn-secondary" onClick={() => navigate('/dashboard')}>← Back to Dashboard</button>
    </Layout>
  )

  const passRate = result ? Math.round(result.pass_rate * 100) : null
  const passColor = passRate === 100 ? 'var(--success)' : passRate > 0 ? 'var(--warning)' : 'var(--danger)'

  return (
    <Layout fullWidth>
      <div className={styles.page}>
        {/* ── Left panel: Problem ─────────────────── */}
        <div className={styles.left}>
          {/* Header */}
          <div className={styles.problemHeader}>
            <button className="btn btn-ghost btn-sm" onClick={() => navigate('/dashboard')}>← Back</button>
            {selectionMeta && (
              <ZoneBadge zone={selectionMeta.zone} />
            )}
          </div>

          <h1 className={styles.problemTitle}>{problem?.title}</h1>

          <div className={styles.metaRow}>
            {problem?.difficulty && (
              <span className={`badge badge-${problem.difficulty}`}>{problem.difficulty}</span>
            )}
            {problem?.concept_tags?.map((t) => (
              <span key={t} className="badge badge-concept">{t}</span>
            ))}
            {problem?.expected_complexity && (
              <span style={{ fontSize: 12, color: 'var(--text-tertiary)', marginLeft: 'auto' }}>
                Expected: {problem.expected_complexity}
              </span>
            )}
          </div>

          <div className={styles.statement}>{problem?.statement}</div>

          {/* Example test cases */}
          {problem?.example_cases?.length > 0 && (
            <div>
              <p style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Examples
              </p>
              {problem.example_cases.map((tc, i) => (
                <div key={i} className={styles.exampleCase}>
                  <div><span className={styles.exLabel}>Input:</span> <code>{tc.input}</code></div>
                  <div><span className={styles.exLabel}>Output:</span> <code>{tc.output}</code></div>
                </div>
              ))}
            </div>
          )}

          <div style={{ marginTop: 'auto', paddingTop: 16 }}>
            <p style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
              {problem?.total_test_cases} test cases · {problem?.hidden_test_count} hidden
            </p>
          </div>
        </div>

        {/* ── Right panel: Editor + Results ────────── */}
        <div className={styles.right}>
          {/* Editor toolbar */}
          <div className={styles.editorToolbar}>
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>Python 3</span>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text-secondary)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={deepExplain}
                  onChange={(e) => setDeepExplain(e.target.checked)}
                  style={{ accentColor: 'var(--accent)' }}
                />
                Deep explanation
              </label>
              {cooldown > 0 ? (
                <button className="btn btn-primary" disabled>
                  Wait {cooldown}s
                </button>
              ) : (
                <button
                  className="btn btn-primary"
                  onClick={handleSubmit}
                  disabled={submitting}
                >
                  {submitting ? <span className="spinner" /> : '▶'}
                  {submitting ? 'Running…' : 'Run & Submit'}
                </button>
              )}
            </div>
          </div>

          {/* Monaco editor */}
          <div className={styles.editorWrap}>
            <Editor
              height="100%"
              defaultLanguage="python"
              value={code}
              onChange={(val) => setCode(val || '')}
              theme="vs"
              options={{
                fontSize: 14,
                fontFamily: "'Fira Code', 'Cascadia Code', Consolas, monospace",
                fontLigatures: true,
                minimap: { enabled: false },
                scrollBeyondLastLine: false,
                lineNumbers: 'on',
                renderLineHighlight: 'line',
                padding: { top: 12, bottom: 12 },
                wordWrap: 'on',
              }}
            />
          </div>

          {/* Submission error */}
          {error && <div className="alert alert-error" style={{ margin: '0 16px 8px' }}>{error}</div>}

          {/* ── Results panel ──────────────────────── */}
          {result && (
            <div className={styles.results}>
              {/* Pass rate header */}
              <div className={styles.resultHeader}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <span style={{ fontSize: 28, fontWeight: 800, color: passColor }}>{passRate}%</span>
                  <div>
                    <p style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      {passRate === 100 ? '✅ All tests passed!' : passRate > 0 ? '⚠️ Partial pass' : '❌ All tests failed'}
                    </p>
                    <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                      {result.gaming_flagged && '🚨 Gaming flag detected — score capped · '}
                      {result.escalated && `🧠 Deep explanation triggered (${result.feedback?.mistake_category})`}
                    </p>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn btn-secondary btn-sm" onClick={loadProblem}>
                    Try another
                  </button>
                  {result.next_problem && (
                    <button className="btn btn-primary btn-sm" onClick={handleNextProblem}>
                      Next problem →
                    </button>
                  )}
                </div>
              </div>

              {/* Capability update */}
              {result.capability_update && (
                <div className={styles.capUpdate}>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                    {result.capability_update.concept} score:
                  </span>
                  <span style={{ fontWeight: 600 }}>
                    {Math.round(result.capability_update.old_score * 100)}%
                  </span>
                  <span style={{ color: 'var(--text-tertiary)' }}>→</span>
                  <span style={{ fontWeight: 700, color: result.capability_update.new_score > result.capability_update.old_score ? 'var(--success)' : 'var(--danger)' }}>
                    {Math.round(result.capability_update.new_score * 100)}%
                  </span>
                </div>
              )}

              {/* AI Feedback */}
              {result.feedback && (
                <div className={styles.section}>
                  <p className={styles.sectionTitle}>💬 Feedback</p>
                  <p style={{ fontSize: 14, lineHeight: 1.6, color: 'var(--text-primary)' }}>
                    {result.feedback.text}
                  </p>
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    {result.feedback.mistake_category !== 'unknown' && (
                      <span className="badge badge-concept">{result.feedback.mistake_category}</span>
                    )}
                    <span className={`badge ${result.feedback.difficulty_signal === 'harder' ? 'badge-hard' : result.feedback.difficulty_signal === 'easier' ? 'badge-easy' : 'badge-medium'}`}>
                      Next: {result.feedback.difficulty_signal}
                    </span>
                  </div>
                </div>
              )}

              {/* Visible test cases */}
              {result.visible_results?.length > 0 && (
                <div className={styles.section}>
                  <p className={styles.sectionTitle}>🧪 Test Cases</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {result.visible_results.map((tc, i) => (
                      <div key={i} className={`${styles.testCase} ${tc.passed ? styles.testPass : styles.testFail}`}>
                        <span className={styles.testIcon}>{tc.passed ? '✅' : '❌'}</span>
                        <div style={{ flex: 1, fontSize: 13 }}>
                          <span style={{ color: 'var(--text-secondary)' }}>In:</span> <code>{tc.input}</code>
                          {' · '}
                          <span style={{ color: 'var(--text-secondary)' }}>Expected:</span> <code>{tc.expected}</code>
                          {!tc.passed && <> {' · '}<span style={{ color: 'var(--text-secondary)' }}>Got:</span> <code style={{ color: 'var(--danger)' }}>{tc.got}</code></>}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Deep explanation (Brain B) */}
              {result.deep_explanation && (
                <div className={`${styles.section} ${styles.deepSection}`}>
                  <p className={styles.sectionTitle}>🧠 Deep Explanation</p>
                  <p style={{ fontSize: 14, lineHeight: 1.7, marginBottom: 12 }}>{result.deep_explanation.explanation}</p>

                  {result.deep_explanation.step_by_step?.length > 0 && (
                    <div style={{ marginBottom: 12 }}>
                      <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>Steps</p>
                      <ol style={{ paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 4 }}>
                        {result.deep_explanation.step_by_step.map((s, i) => (
                          <li key={i} style={{ fontSize: 13, lineHeight: 1.6 }}>{s}</li>
                        ))}
                      </ol>
                    </div>
                  )}

                  {result.deep_explanation.alternative_approach && (
                    <div style={{ marginBottom: 12 }}>
                      <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>Alternative Approach</p>
                      <p style={{ fontSize: 13, lineHeight: 1.6 }}>{result.deep_explanation.alternative_approach}</p>
                    </div>
                  )}

                  {result.deep_explanation.mini_problem && (
                    <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: 14, marginTop: 8 }}>
                      <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>🧩 Practice Problem</p>
                      <p style={{ fontSize: 13, lineHeight: 1.6 }}>{result.deep_explanation.mini_problem.statement}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Next problem preview */}
              {result.next_problem && (
                <div className={styles.section} style={{ background: 'var(--accent-light)', borderRadius: 'var(--radius-sm)', padding: 14 }}>
                  <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: 6 }}>
                    🎯 Up Next
                  </p>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                    <div>
                      <p style={{ fontWeight: 600, fontSize: 14 }}>{result.next_problem.title}</p>
                      <span className={`badge badge-${result.next_problem.difficulty}`} style={{ marginTop: 4 }}>{result.next_problem.difficulty}</span>
                    </div>
                    <button className="btn btn-primary btn-sm" onClick={handleNextProblem}>Start →</button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  )
}
