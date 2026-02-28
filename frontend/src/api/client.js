import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 60000, // 60s — Brain B can take up to 30s
})

// ── Student ──────────────────────────────────────────
export const registerStudent = (data) =>
  api.post('/student/register', data).then((r) => r.data)

export const getStudentProfile = (studentId) =>
  api.get(`/student/${studentId}/profile`).then((r) => r.data)

export const getStudentHistory = (studentId, limit = 50, offset = 0) =>
  api
    .get(`/student/${studentId}/history`, { params: { limit, offset } })
    .then((r) => r.data)

// ── Problems ─────────────────────────────────────────
export const getNextProblem = (studentId, concept) =>
  api
    .get('/problems/next', { params: { student_id: studentId, concept } })
    .then((r) => r.data)

export const getProblemById = (problemId) =>
  api.get(`/problems/${problemId}`).then((r) => r.data)

// ── Submit ────────────────────────────────────────────
export const submitCode = (payload) =>
  api.post('/submit', payload).then((r) => r.data)

// ── Faculty ───────────────────────────────────────────
export const getFacultyDashboard = () =>
  api.get('/faculty/dashboard').then((r) => r.data)

export const getClassOverview = () =>
  api.get('/faculty/class-overview').then((r) => r.data)

export const getEscalations = () =>
  api.get('/faculty/escalations').then((r) => r.data)

export const resolveEscalation = (logId) =>
  api.post(`/faculty/escalations/${logId}/resolve`).then((r) => r.data)

// ── Health ────────────────────────────────────────────
export const healthCheck = () =>
  api.get('/health').then((r) => r.data)

export default api
