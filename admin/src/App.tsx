import { useEffect, useState, type FormEvent } from 'react'
import { NavLink, Navigate, Route, Routes } from 'react-router-dom'
import { api, PUBLIC_SITE, type Admin, type Overview } from './api'
import { Audits } from './pages/Audits'
import { Claims } from './pages/Claims'
import { Dashboard } from './pages/Dashboard'
import { Listings } from './pages/Listings'
import { Members } from './pages/Members'
import { Submissions } from './pages/Submissions'

function Login({ onLogin }: { onLogin: (a: Admin) => void }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try { onLogin(await api.login(email, password)) } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="login-wrap">
      <form className="login" onSubmit={submit}>
        <div className="brand">found<span>.</span> <em>admin</em></div>
        <p className="muted">Sign in with an admin account. This console is separate from the public site.</p>
        <label>Email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoFocus /></label>
        <label>Password<input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <p className="error">{error}</p>}
        <button className="btn primary" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form>
    </div>
  )
}

export default function App() {
  const [admin, setAdmin] = useState<Admin | null>(null)
  const [ready, setReady] = useState(false)
  const [counts, setCounts] = useState<Overview | null>(null)

  useEffect(() => { api.me().then(setAdmin).catch(() => setAdmin(null)).finally(() => setReady(true)) }, [])
  const refreshCounts = () => api.overview().then(setCounts).catch(() => {})
  useEffect(() => { if (admin) refreshCounts() }, [admin])

  if (!ready) return null
  if (!admin) return <Login onLogin={setAdmin} />

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">found<span>.</span> <em>admin</em></div>
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/claims">Founder claims {!!counts?.pending_claims && <b className="badge">{counts.pending_claims}</b>}</NavLink>
          <NavLink to="/submissions">New startups {!!counts?.pending_startups && <b className="badge">{counts.pending_startups}</b>}</NavLink>
          <NavLink to="/listings">All listings</NavLink>
          <NavLink to="/audits">Listing audits</NavLink>
          <NavLink to="/members">Members</NavLink>
        </nav>
        <div className="sidebar-foot">
          <a href={PUBLIC_SITE} target="_blank" rel="noreferrer">Open public site ↗</a>
          <span>{admin.first_name} {admin.last_name}</span>
          <button className="link" onClick={async () => { await api.logout(); setAdmin(null) }}>Sign out</button>
        </div>
      </aside>
      <main className="content">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/claims" element={<Claims onChange={refreshCounts} />} />
          <Route path="/submissions" element={<Submissions onChange={refreshCounts} />} />
          <Route path="/listings" element={<Listings />} />
          <Route path="/audits" element={<Audits />} />
          <Route path="/members" element={<Members />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  )
}
