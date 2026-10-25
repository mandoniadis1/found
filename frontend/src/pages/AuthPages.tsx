import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

export function Login() {
  const { setUser } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      setUser(await api.login(email, password))
      navigate('/')
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <div className="auth">
      <form className="auth-card form" onSubmit={submit}>
        <h1>Welcome back</h1>
        <p className="muted">Log in to message founders and RSVP to events.</p>
        <label>Yale email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>Password<input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {error && <p className="error">{error}</p>}
        <button className="btn btn-dark full">Log in</button>
        <p className="muted small">New here? <Link to="/signup">Create an account</Link></p>
        <p className="demo-hint">Local-mode test accounts (password found2026): member demo@yale.edu · fake founder test.founder@yale.edu (owns "Bulldog Test Co.") · admin admin@yale.edu at /admin</p>
      </form>
    </div>
  )
}

export function Signup() {
  const { setUser } = useAuth()
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', password: '', confirm: '', school: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [sentTo, setSentTo] = useState('')
  const set = (k: keyof typeof form, v: string) => setForm((f) => ({ ...f, [k]: v }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (!form.email.toLowerCase().trim().endsWith('@yale.edu')) return setError('Use your @yale.edu email.')
    if (form.password !== form.confirm) return setError("Passwords don't match.")
    setBusy(true)
    try {
      const { confirm: _confirm, ...body } = form
      void _confirm
      setUser(await api.signup(body))
      setSentTo(body.email)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (sentTo) {
    return (
      <div className="auth">
        <div className="auth-card">
          <h1>Check your inbox</h1>
          <p className="muted">We sent a verification link to <strong>{sentTo}</strong>. Click it to finish setting up your account.</p>
          <p className="muted small"><a href="/api/dev/email" target="_blank" rel="noreferrer">Local mode? Open the email here ↗</a></p>
          <p className="muted small">Not there after a minute? Check spam, or resend it from your <Link to="/profile">profile</Link>. You can browse found. while you wait. <Link to="/">Go to Explore →</Link></p>
        </div>
      </div>
    )
  }

  return (
    <div className="auth">
      <form className="auth-card form" onSubmit={submit}>
        <h1>Join found.</h1>
        <p className="muted">For Yale students, alumni, faculty and staff. You'll need your @yale.edu email.</p>
        <div className="row2">
          <label>First name<input required value={form.first_name} onChange={(e) => set('first_name', e.target.value)} /></label>
          <label>Last name<input required value={form.last_name} onChange={(e) => set('last_name', e.target.value)} /></label>
        </div>
        <label>Yale email<input type="email" required placeholder="first.last@yale.edu" value={form.email} onChange={(e) => set('email', e.target.value)} /></label>
        <label>School<input placeholder="e.g. Yale SOM" value={form.school} onChange={(e) => set('school', e.target.value)} /></label>
        <div className="row2">
          <label>Password<input type="password" required minLength={8} value={form.password} onChange={(e) => set('password', e.target.value)} /></label>
          <label>Confirm<input type="password" required value={form.confirm} onChange={(e) => set('confirm', e.target.value)} /></label>
        </div>
        {error && <p className="error">{error}</p>}
        <button className="btn btn-dark full" disabled={busy}>{busy ? 'Creating account…' : 'Create account'}</button>
        <p className="muted small">Already a member? <Link to="/login">Log in</Link></p>
      </form>
    </div>
  )
}

// Where emailed links land after the backend checks them.
export function Verified() {
  const [params] = useSearchParams()
  const { setUser } = useAuth()
  const result = params.get('result')
  const startup = params.get('startup')

  useEffect(() => { api.me().then(setUser).catch(() => {}) }, [setUser])

  const copy = {
    email_ok: { title: 'Your Yale email is verified', body: 'You can now message founders, RSVP, claim your startup and host events. Add your LinkedIn link on your profile so people can find you.', to: '/profile', cta: 'Go to your profile' },
    claim_ok: { title: "You've claimed this startup", body: 'Add your team size, round, funding and location so founders can find you.', to: `/startups/${startup}`, cta: 'Open your startup' },
  }[result ?? ''] ?? { title: 'That link didn’t work', body: 'It may have expired or already been used. You can request a new one from your profile.', to: '/profile', cta: 'Go to your profile' }

  return (
    <div className="auth">
      <div className="auth-card">
        <h1>{copy.title}</h1>
        <p className="muted">{copy.body}</p>
        <Link to={copy.to} className="btn btn-dark full">{copy.cta}</Link>
      </div>
    </div>
  )
}
