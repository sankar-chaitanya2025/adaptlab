import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { getStudentProfile } from '../api/client'
import styles from './Home.module.css'

export default function Home() {
  const { loginStudent, loginFaculty, userRole, currentUser } = useApp()
  const navigate = useNavigate()

  const [studentId, setStudentId] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Already logged in → redirect
  if (userRole === 'student' && currentUser) {
    navigate('/dashboard')
    return null
  }
  if (userRole === 'faculty') {
    navigate('/faculty')
    return null
  }

  const handleStudentLogin = async (e) => {
    e.preventDefault()
    if (!studentId.trim()) return
    setLoading(true)
    setError('')
    try {
      const profile = await getStudentProfile(studentId.trim())
      loginStudent({ student_id: profile.student_id, name: profile.student_name })
      navigate('/dashboard')
    } catch (err) {
      if (err.response?.status === 404) {
        setError('Student ID not found. Please register first.')
      } else {
        setError('Could not connect to AdaptLab server. Make sure the backend is running.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      {/* Hero */}
      <div className={styles.hero}>
        <div className={styles.logoMark}>⬡</div>
        <h1 className={styles.heroTitle}>AdaptLab</h1>
        <p className={styles.heroSub}>
          An adaptive coding lab that learns how you think — and challenges you at exactly the right level.
        </p>
      </div>

      {/* Cards */}
      <div className={styles.cards}>
        {/* Student card */}
        <div className="card">
          <div className={styles.cardIcon}>🎓</div>
          <h2 className={styles.cardTitle}>I'm a Student</h2>
          <p className={styles.cardDesc}>Enter your student ID to pick up where you left off.</p>
          <form onSubmit={handleStudentLogin} className={styles.form}>
            <div className="form-group">
              <label className="form-label">Student ID</label>
              <input
                className="form-input"
                type="text"
                placeholder="e.g. IISC2024_priya"
                value={studentId}
                onChange={(e) => setStudentId(e.target.value)}
                autoFocus
              />
            </div>
            {error && <div className="alert alert-error">{error}</div>}
            <button type="submit" className="btn btn-primary" disabled={loading || !studentId.trim()}>
              {loading ? <span className="spinner" /> : null}
              {loading ? 'Looking up…' : 'Continue →'}
            </button>
          </form>
          <p className={styles.registerHint}>
            New here? <Link to="/register">Register an account</Link>
          </p>
        </div>

        {/* Faculty card */}
        <div className="card">
          <div className={styles.cardIcon}>👩‍🏫</div>
          <h2 className={styles.cardTitle}>I'm Faculty</h2>
          <p className={styles.cardDesc}>
            View class-wide analytics, student progress, and manage escalations.
          </p>
          <button
            className="btn btn-secondary"
            style={{ marginTop: 'auto' }}
            onClick={() => { loginFaculty(); navigate('/faculty') }}
          >
            Open Faculty Dashboard →
          </button>
        </div>
      </div>

      {/* Footer note */}
      <p className={styles.footer}>
        AdaptLab · Powered by Qwen 1.5B & 7B · Runs on a single college server
      </p>
    </div>
  )
}
