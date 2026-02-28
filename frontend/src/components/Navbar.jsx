import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import styles from './Navbar.module.css'

export default function Navbar() {
  const { currentUser, userRole, logout } = useApp()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const isActive = (path) => location.pathname === path

  return (
    <nav className={styles.navbar}>
      <div className={styles.inner}>
        {/* Logo */}
        <Link to={userRole === 'faculty' ? '/faculty' : userRole === 'student' ? '/dashboard' : '/'} className={styles.logo}>
          <span className={styles.logoIcon}>⬡</span>
          <span className={styles.logoText}>AdaptLab</span>
        </Link>

        {/* Nav links */}
        <div className={styles.links}>
          {userRole === 'student' && (
            <>
              <Link to="/dashboard" className={`${styles.link} ${isActive('/dashboard') ? styles.active : ''}`}>Dashboard</Link>
              <Link to="/history"   className={`${styles.link} ${isActive('/history')   ? styles.active : ''}`}>History</Link>
            </>
          )}
          {userRole === 'faculty' && (
            <>
              <Link to="/faculty"              className={`${styles.link} ${isActive('/faculty')              ? styles.active : ''}`}>Overview</Link>
              <Link to="/faculty/class"        className={`${styles.link} ${isActive('/faculty/class')        ? styles.active : ''}`}>Students</Link>
              <Link to="/faculty/escalations"  className={`${styles.link} ${isActive('/faculty/escalations')  ? styles.active : ''}`}>Escalations</Link>
            </>
          )}
        </div>

        {/* Right side */}
        <div className={styles.right}>
          {currentUser && (
            <span className={styles.userChip}>{currentUser.name || currentUser.student_id}</span>
          )}
          {(userRole === 'faculty') && (
            <span className={styles.userChip}>Faculty</span>
          )}
          {userRole && (
            <button className={`btn btn-ghost btn-sm`} onClick={handleLogout}>Sign out</button>
          )}
        </div>
      </div>
    </nav>
  )
}
