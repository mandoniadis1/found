import { useEffect, useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { Modal } from '../components/Modal'
import { ResendButton } from '../components/ResendButton'
import { StartupCard } from '../components/StartupCard'
import { StartupForm } from '../components/StartupForm'
import type { ClaimRequest, SiteConfig, Startup } from '../types'

const LINKEDIN_RESULT: Record<string, { text: string; error?: boolean }> = {
  connected: { text: 'LinkedIn connected.' },
  cancelled: { text: 'LinkedIn sign-in was cancelled.', error: true },
  expired: { text: 'That LinkedIn sign-in took too long. Please try again.', error: true },
  failed: { text: "We couldn't reach LinkedIn. Please try again.", error: true },
  taken: { text: 'That LinkedIn account is already connected to another found. member.', error: true },
}

const CLAIM_STATUS: Record<ClaimRequest['status'], string> = {
  email_sent: 'Waiting for you to click the work-email link',
  pending: 'Waiting for review by the found. team',
  approved: 'Approved',
  denied: 'Not approved',
}

export function Profile() {
  const { user, ready, setUser } = useAuth()
  const [params, setParams] = useSearchParams()
  const [config, setConfig] = useState<SiteConfig | null>(null)
  const [mine, setMine] = useState<Startup[]>([])
  const [claims, setClaims] = useState<ClaimRequest[]>([])
  const [adding, setAdding] = useState(false)
  const [headline, setHeadline] = useState('')
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null)

  useEffect(() => { api.config().then(setConfig) }, [])
  useEffect(() => {
    if (!user) return
    api.myStartups().then(setMine)
    api.myClaims().then(setClaims)
    setHeadline(user.headline ?? '')
  }, [user])
  useEffect(() => {
    const result = params.get('linkedin')
    if (!result) return
    setMsg(LINKEDIN_RESULT[result] ?? null)
    api.me().then(setUser)
    setParams({}, { replace: true })
  }, [params, setParams, setUser])

  if (!ready) return null
  if (!user) return <Navigate to="/login" />

  async function run(fn: () => Promise<void>, ok: string) {
    setMsg(null)
    try {
      await fn()
      setMsg({ text: ok })
    } catch (err) {
      setMsg({ text: (err as Error).message, error: true })
    }
  }

  const openClaims = claims.filter((c) => c.status === 'pending' || c.status === 'email_sent')
  const linkedInReady = config?.linkedin_configured || config?.linkedin_dev_standin

  return (
    <div className="page narrow">
      <div className="page-head">
        <div>
          <p className="eyebrow">Your profile</p>
          <h1>{user.first_name} {user.last_name}</h1>
          <p className="muted">{user.email} · {user.school || 'Add your school'}</p>
        </div>
      </div>

      {msg && <p className={msg.error ? 'error' : 'success'}>{msg.text}</p>}

      <div className="panels">
        <section className="panel">
          <div className="panel-head">
            <h3><span className="step">1</span>Yale email</h3>
            {user.email_verified ? <span className="verified">✓ Verified</span> : <span className="pill">Not verified</span>}
          </div>
          {user.email_verified ? (
            <p className="muted small">{user.email} is confirmed.</p>
          ) : (
            <>
              <p className="muted small">Click the link we sent to {user.email}.</p>
              <ResendButton email={user.email} />
              {config?.mail_mode === 'outbox' && config.dev_mode && (
                <p className="muted tiny">Local mode: emails aren't sent. <a href="/api/dev/email" target="_blank" rel="noreferrer">Open your email ↗</a></p>
              )}
            </>
          )}
        </section>

        <section className="panel">
          <div className="panel-head">
            <h3><span className="step">2</span>LinkedIn</h3>
            {user.linkedin_connected ? <span className="verified">✓ Connected</span> : <span className="pill">Not connected</span>}
          </div>
          {user.linkedin_connected ? (
            <>
              <div className="li-identity">
                {user.linkedin_picture ? <img src={user.linkedin_picture} alt="" /> : <span className="li-logo">in</span>}
                <span className="small"><strong>{user.linkedin_name}</strong></span>
              </div>
              {user.linkedin_dev_standin && <p className="muted tiny">Connected with the local dev stand-in, not real LinkedIn.</p>}
              <button className="link-btn" onClick={() => run(async () => setUser(await api.disconnectLinkedIn()), 'LinkedIn disconnected.')}>Disconnect</button>
            </>
          ) : (
            <>
              <p className="muted small">Sign in with LinkedIn to prove you're a real person. Needed to claim a startup or host events.</p>
              {linkedInReady ? (
                <a className={`btn btn-linkedin${user.email_verified ? '' : ' disabled'}`} href={user.email_verified ? '/api/auth/linkedin/start' : undefined}>
                  <span className="li-logo">in</span> Sign in with LinkedIn
                </a>
              ) : (
                <p className="muted tiny">LinkedIn sign-in isn't set up on this server yet.</p>
              )}
              {!user.email_verified && <p className="muted tiny">Verify your Yale email first.</p>}
              {config?.linkedin_dev_standin && <p className="muted tiny">Dev mode: uses a local stand-in until LinkedIn keys are added.</p>}
            </>
          )}
        </section>

        <section className="panel">
          <div className="panel-head">
            <h3><span className="step">3</span>Moderator</h3>
            {user.is_moderator ? <span className="verified">✓ Moderator</span> : <span className="pill">Member</span>}
          </div>
          {user.is_moderator ? (
            <p className="muted small">You can host events. <Link to="/events">Go to Events →</Link></p>
          ) : (
            <>
              <p className="muted small">Moderators plan events: launches for their startup, or industry meetups.</p>
              <button className="btn btn-ghost" disabled={!user.email_verified || !user.linkedin_connected}
                onClick={() => run(async () => setUser(await api.becomeModerator()), 'You are now a moderator.')}>
                Sign up as moderator
              </button>
            </>
          )}
        </section>
      </div>

      <section className="panel headline-panel">
        <div className="panel-head"><h3>Headline</h3></div>
        <form className="inline-form" onSubmit={(e) => { e.preventDefault(); run(async () => setUser(await api.updateProfile({ headline })), 'Saved.') }}>
          <input maxLength={140} value={headline} onChange={(e) => setHeadline(e.target.value)} placeholder="e.g. Building in climate fintech" />
          <button className="btn btn-ghost">Save</button>
        </form>
      </section>

      {openClaims.length > 0 && (
        <>
          <h2 className="section-title">Your claims</h2>
          <div className="stack tight">
            {openClaims.map((c) => (
              <div key={c.id} className="claim-row">
                <Link to={`/startups/${c.startup_id}`}><strong>{c.startup_name}</strong></Link>
                <span className="muted small">{CLAIM_STATUS[c.status]}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <div className="page-head small-gap">
        <h2 className="section-title">Your startups</h2>
        <button className="btn btn-dark" disabled={!user.email_verified || !user.linkedin_connected} onClick={() => setAdding(true)}>+ Add startup</button>
      </div>
      {mine.length === 0 ? (
        <p className="muted">
          You haven't claimed or listed a startup yet. If it's in the Yale Startup Directory, find it on <Link to="/">Explore</Link> and
          click “Claim this startup”. Otherwise add it here; new startups are reviewed before they're listed.
        </p>
      ) : (
        <div className="grid">{mine.map((s) => (
          <div key={s.id} className="mine-wrap">
            {s.status !== 'listed' && <span className={`status-tag ${s.status}`}>{s.status === 'pending' ? 'Under review' : 'Not approved'}</span>}
            <StartupCard s={s} />
          </div>
        ))}</div>
      )}

      {adding && (
        <Modal title="Add your startup" onClose={() => setAdding(false)}>
          <p className="muted small modal-note">New startups are reviewed by the found. team before they appear on Explore.</p>
          <StartupForm onSaved={(s) => { setMine((m) => [...m, s]); setAdding(false); setMsg({ text: `${s.name} was submitted for review.` }) }} />
        </Modal>
      )}
    </div>
  )
}
