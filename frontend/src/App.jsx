import { Routes, Route, Navigate } from 'react-router-dom'
import { useApp } from './context/AppContext'
import Home from './pages/Home'
import StudentRegister from './pages/StudentRegister'
import StudentDashboard from './pages/StudentDashboard'
import ProblemPage from './pages/ProblemPage'
import StudentHistory from './pages/StudentHistory'
import FacultyDashboard from './pages/FacultyDashboard'
import FacultyClassOverview from './pages/FacultyClassOverview'
import FacultyEscalations from './pages/FacultyEscalations'

function RequireStudent({ children }) {
  const { userRole, currentUser } = useApp()
  if (userRole !== 'student' || !currentUser) return <Navigate to="/" replace />
  return children
}

function RequireFaculty({ children }) {
  const { userRole } = useApp()
  if (userRole !== 'faculty') return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/register" element={<StudentRegister />} />

      {/* Student routes */}
      <Route path="/dashboard" element={<RequireStudent><StudentDashboard /></RequireStudent>} />
      <Route path="/practice/:concept" element={<RequireStudent><ProblemPage /></RequireStudent>} />
      <Route path="/problem/:problemId" element={<RequireStudent><ProblemPage /></RequireStudent>} />
      <Route path="/history" element={<RequireStudent><StudentHistory /></RequireStudent>} />

      {/* Faculty routes */}
      <Route path="/faculty" element={<RequireFaculty><FacultyDashboard /></RequireFaculty>} />
      <Route path="/faculty/class" element={<RequireFaculty><FacultyClassOverview /></RequireFaculty>} />
      <Route path="/faculty/escalations" element={<RequireFaculty><FacultyEscalations /></RequireFaculty>} />

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
