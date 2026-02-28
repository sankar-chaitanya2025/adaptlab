import { createContext, useContext, useState, useCallback } from 'react'

export const AppContext = createContext(null)

const STORAGE_KEY = 'adaptlab_user'
const ROLE_KEY = 'adaptlab_role'

function loadUser() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function loadRole() {
  return localStorage.getItem(ROLE_KEY) || null
}

export function AppProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(loadUser)
  const [userRole, setUserRole] = useState(loadRole)

  const loginStudent = useCallback((user) => {
    setCurrentUser(user)
    setUserRole('student')
    localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
    localStorage.setItem(ROLE_KEY, 'student')
  }, [])

  const loginFaculty = useCallback(() => {
    setCurrentUser(null)
    setUserRole('faculty')
    localStorage.removeItem(STORAGE_KEY)
    localStorage.setItem(ROLE_KEY, 'faculty')
  }, [])

  const logout = useCallback(() => {
    setCurrentUser(null)
    setUserRole(null)
    localStorage.removeItem(STORAGE_KEY)
    localStorage.removeItem(ROLE_KEY)
  }, [])

  return (
    <AppContext.Provider value={{ currentUser, userRole, loginStudent, loginFaculty, logout }}>
      {children}
    </AppContext.Provider>
  )
}

export function useApp() {
  return useContext(AppContext)
}
