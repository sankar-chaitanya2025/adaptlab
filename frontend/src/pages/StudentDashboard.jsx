import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { getStudentProfile } from '../api/client'
import Layout from '../components/Layout'
import CapabilityBar from '../components/CapabilityBar'
import ZoneBadge from '../components/ZoneBadge'
import LoadingSpinner from '../components/LoadingSpinner'

const CONCEPT_ICONS = {
  loops: '🔄', arrays: '📋', strings: '📝', recursion: '♻️',
  functions: 'λ', dictionaries: '📚', sorting: '⚙️',
  dynamic_prog: '🧩', graphs: '🕸️', trees: '🌳', variables: '📌',
}

export default function StudentDashboard() {
  const { currentUser } = useApp()
  const navigate = useNavigate()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getStudentProfile(currentUser.student_id)
      .then(setProfile)
      .catch(() => setError('Failed to load your profile.'))
      .finally(() => setLoading(false))
  }, [currentUser.student_id])

  if (loading) return <Layout><LoadingSpinner size="lg" text="Loading your dashboard…" /></Layout>
  if (error)   return <Layout><div className="alert alert-error">{error}</div></Layout>

  const { scores = [], zones = [], weakest_concept, strongest_concept, mean_score, total_submissions, total_escalations } = profile

  // Build zone map for easy lookup
  const zoneMap = {}
  zones.forEach((z) => { zoneMap[z.concept] = z.zone })

  return (
    <Layout>
      {/* Greeting */}
      <div style={{ marginBottom: 32 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: '-0.02em' }}>
          Welcome back, {currentUser.name || currentUser.student_id} 👋
        </h1>
        <p style={{ color: 'var(--text-secondary)', marginTop: 6, fontSize: 15 }}>
          Here's your current capability profile across all concepts.
        </p>
      </div>

      {/* Stats row */}
      <div className="grid-4" style={{ marginBottom: 32 }}>
        <StatCard label="Overall Score" value={mean_score != null ? `${Math.round(mean_score * 100)}%` : 'N/A'} accent />
        <StatCard label="Submissions" value={total_submissions} />
        <StatCard label="Escalations" value={total_escalations} />
        <StatCard label="Concepts" value={scores.length} />
      </div>

      {/* Weak / Strong callouts */}
      {(weakest_concept || strongest_concept) && (
        <div className="grid-2" style={{ marginBottom: 32 }}>
          {weakest_concept && (
            <div className="alert alert-warning" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 20 }}>⚠️</span>
              <div>
                <strong>Needs attention:</strong>{' '}
                <button className="btn btn-sm" style={{ marginLeft: 8 }} onClick={() => navigate(`/practice/${weakest_concept}`)}>
                  Practice {weakest_concept} →
                </button>
              </div>
            </div>
          )}
          {strongest_concept && (
            <div className="alert alert-success" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 20 }}>🏆</span>
              <div><strong>Strongest concept:</strong> {strongest_concept}</div>
            </div>
          )}
        </div>
      )}

      {/* Concept cards grid */}
      <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16 }}>Concepts</h2>

      {scores.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📚</div>
          <p className="empty-state-text">No concept data yet. Start practicing to build your profile!</p>
          <button className="btn btn-primary" style={{ marginTop: 20 }} onClick={() => navigate('/practice/loops')}>
            Start with Loops →
          </button>
        </div>
      ) : (
        <div className="grid-3">
          {scores.map((s) => (
            <ConceptCard
              key={s.concept}
              concept={s.concept}
              score={s.score}
              zone={zoneMap[s.concept] ?? 2}
              onPractice={() => navigate(`/practice/${s.concept}`)}
            />
          ))}
        </div>
      )}

      {/* Quick start if no concepts yet */}
      {scores.length === 0 && null}

      {/* Start practising banner for known concepts */}
      <div className="card" style={{ marginTop: 32, display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <p style={{ fontWeight: 600 }}>Ready to practice?</p>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
            AdaptLab picks the right problem at the right difficulty for you.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          {['loops', 'arrays', 'recursion', 'sorting'].map((c) => (
            <button key={c} className="btn btn-secondary btn-sm" onClick={() => navigate(`/practice/${c}`)}>
              {CONCEPT_ICONS[c]} {c}
            </button>
          ))}
        </div>
      </div>
    </Layout>
  )
}

function StatCard({ label, value, accent }) {
  return (
    <div className="card" style={{ padding: 20 }}>
      <p style={{ fontSize: 12, color: 'var(--text-tertiary)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</p>
      <p style={{ fontSize: 28, fontWeight: 700, marginTop: 6, color: accent ? 'var(--accent)' : 'var(--text-primary)' }}>
        {value}
      </p>
    </div>
  )
}

function ConceptCard({ concept, score, zone, onPractice }) {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 14, padding: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 18 }}>{CONCEPT_ICONS[concept] || '📌'}</span>
          <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{concept.replace('_', ' ')}</span>
        </div>
        <ZoneBadge zone={zone} />
      </div>
      <CapabilityBar score={score} />
      <button className="btn btn-secondary btn-sm" onClick={onPractice}>
        Practice →
      </button>
    </div>
  )
}
