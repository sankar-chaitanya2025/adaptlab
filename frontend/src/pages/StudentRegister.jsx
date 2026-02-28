import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { registerStudent } from '../api/client'
import { useApp } from '../context/AppContext'

export default function StudentRegister() {
  const { loginStudent } = useApp()
  const navigate = useNavigate()
  const [form, setForm] = useState({ student_id: '', name: '', email: '' })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handle = (field) => (e) => setForm((f) => ({ ...f, [field]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      await registerStudent(form)
      loginStudent({ student_id: form.student_id, name: form.name })
      navigate('/dashboard')
    } catch (err) {
      if (err.response?.status === 409) {
        setError('A student with this ID already exists. Try logging in instead.')
      } else if (err.response?.data?.detail) {
        setError(err.response.data.detail)
      } else {
        setError('Registration failed. Make sure the backend server is running.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24, background: 'var(--bg-secondary)' }}>
      <div className="card" style={{ width: '100%', maxWidth: 420, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {/* Header */}
        <div>
          <Link to="/" style={{ fontSize: 13, color: 'var(--text-secondary)', display: 'inline-flex', alignItems: 'center', gap: 4, marginBottom: 20 }}>
            ← Back
          </Link>
          <h1 style={{ fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' }}>Create an account</h1>
          <p style={{ fontSize: 14, color: 'var(--text-secondary)', marginTop: 6 }}>
            Join AdaptLab and start your adaptive coding journey.
          </p>
        </div>

        <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="form-group">
            <label className="form-label">Student ID</label>
            <input
              className="form-input"
              placeholder="e.g. IISC2024_priya"
              value={form.student_id}
              onChange={handle('student_id')}
              required
              autoFocus
            />
            <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Use your college enrollment ID</span>
          </div>

          <div className="form-group">
            <label className="form-label">Full Name</label>
            <input
              className="form-input"
              placeholder="e.g. Priya Sharma"
              value={form.name}
              onChange={handle('name')}
              required
            />
          </div>

          <div className="form-group">
            <label className="form-label">Email</label>
            <input
              className="form-input"
              type="email"
              placeholder="e.g. priya@iisc.ac.in"
              value={form.email}
              onChange={handle('email')}
              required
            />
          </div>

          {error && <div className="alert alert-error">{error}</div>}

          <button type="submit" className="btn btn-primary btn-lg" disabled={loading}>
            {loading ? <span className="spinner" /> : null}
            {loading ? 'Registering…' : 'Create Account'}
          </button>
        </form>

        <p style={{ textAlign: 'center', fontSize: 13, color: 'var(--text-tertiary)' }}>
          Already have an account? <Link to="/">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
