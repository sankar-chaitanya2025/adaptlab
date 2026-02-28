import Navbar from './Navbar'

export default function Layout({ children, fullWidth = false }) {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)' }}>
      <Navbar />
      <main style={{ minHeight: `calc(100vh - var(--navbar-height))` }}>
        {fullWidth ? children : (
          <div className="page-container">{children}</div>
        )}
      </main>
    </div>
  )
}
