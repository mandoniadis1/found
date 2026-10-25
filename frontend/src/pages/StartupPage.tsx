import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { ClaimModal } from '../components/ClaimModal'
import { EventCard } from '../components/EventCard'
import { Modal } from '../components/Modal'
import { Monogram } from '../components/StartupCard'
import { StartupForm } from '../components/StartupForm'
import { money } from '../format'
import type { FoundEvent, Startup } from '../types'

export function StartupPage() {
  const { id } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [s, setS] = useState<Startup | null>(null)
  const [events, setEvents] = useState<FoundEvent[]>([])
  const [error, setError] = useState('')
  const [claiming, setClaiming] = useState(false)
  const [editing, setEditing] = useState(false)

  useEffect(() => {
    api.startup(Number(id)).then(setS).catch((e) => setError(e.message))
    api.events().then((all) => setEvents(all.filter((e) => e.host_startup_id === Number(id))))
  }, [id])

  async function message() {
    if (!user) return navigate('/login')
    if (!s?.founder) return
    const conv = await api.startConversation(s.founder.id)
    navigate(`/messages/${conv.id}`)
  }

  if (error) return <div className="page"><p className="error">{error}</p></div>
  if (!s) return <div className="page"><p className="muted">Loading…</p></div>

  const mine = user && s.founder?.id === user.id
  const stats: [string, string | null][] = [
    ['Stage', s.stage],
    ['Round', s.round],
    ['Raised', s.raised_usd ? money(s.raised_usd) : null],
    ['Team', s.team_size ? String(s.team_size) : null],
    ['Based in', s.location],
    ['Founded', s.founded_year ? String(s.founded_year) : null],
  ]

  return (
    <div className="page narrow">
      <Link to="/" className="back">← All startups</Link>
      {s.status === 'pending' && <p className="note review-note">Under review: only you and the found. team can see this listing until it's approved.</p>}
      <header className="startup-head">
        <Monogram name={s.name} sector={s.industries[0] ?? ''} size={72} />
        <div>
          <h1>{s.name}</h1>
          <p className="lede">{s.tagline}</p>
          <div className="card-meta head-tags">
            {s.industries.map((i) => <span key={i} className="tag">{i}</span>)}
            {s.affiliations.map((a) => <span key={a} className="tag tag-quiet">{a}</span>)}
          </div>
        </div>
      </header>

      <div className="stats">
        {stats.map(([label, value]) => (
          <div key={label}>
            <span className="muted small">{label}</span>
            {value ? <strong>{value}</strong> : <span className="unknown">Not listed</span>}
          </div>
        ))}
      </div>

      <div className="two-col">
        <section>
          {s.description && (
            <>
              <h2 className="section-title">About</h2>
              <p className="body-text">{s.description}</p>
            </>
          )}
          {s.looking_for && (
            <div className="ask">
              <p className="eyebrow">Looking for</p>
              <p className="body-text pre">{s.looking_for}</p>
            </div>
          )}
          <p className="muted small links-row">
            {s.website ? <a href={s.website} target="_blank" rel="noreferrer">{s.website.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')} ↗</a> : 'No website listed'}
            {s.hiring && <span className="pill pill-hiring">Hiring</span>}
          </p>
          {events.length > 0 && (
            <>
              <h2 className="section-title">Upcoming events</h2>
              <div className="stack">{events.map((e) => (
                <EventCard key={e.id} e={e} onChange={(u) => setEvents((all) => all.map((x) => (x.id === u.id ? u : x)))} />
              ))}</div>
            </>
          )}
          <p className="source-note">
            {s.source === 'yale_pitchbook' ? 'Listing from the Yale Startup Directory (Yale Pitchbook).'
              : s.source === 'demo' ? 'Demo listing (local mode only) for testing the founder card and messaging. Not a real company.'
              : 'Added on found. by its founder and approved by the found. team.'}
          </p>
          {s.correction_note && <p className="correction-note"><strong>Corrected by found.</strong> {s.correction_note}</p>}
          {user?.is_admin && !mine && (
            <button className="link-btn" onClick={() => setEditing(true)}>Admin: edit this listing</button>
          )}
        </section>

        <aside className="founder-card">
          <p className="eyebrow">Founder</p>
          {s.founder ? (
            <>
              <div className="person">
                <div className="avatar">{s.founder.first_name[0]}{s.founder.last_name[0]}</div>
                <div>
                  <strong>{s.founder.first_name} {s.founder.last_name}</strong>
                  {s.founder.linkedin_url && <a className="li-link" href={s.founder.linkedin_url} target="_blank" rel="noreferrer">LinkedIn ↗</a>}
                  <p className="muted small">{s.founder.headline}</p>
                  <p className="muted small">{s.founder.school}</p>
                </div>
              </div>
              {s.founder_verified_via && (
                <p className="verified-how">
                  ✓ Verified founder · {s.founder_verified_via === 'company_email' ? 'confirmed with a company email' : 'reviewed by the found. team'}
                </p>
              )}
              {mine ? (
                <button className="btn btn-ghost full" onClick={() => setEditing(true)}>Edit listing</button>
              ) : (
                <button className="btn btn-dark full" onClick={message}>Message {s.founder.first_name}</button>
              )}
            </>
          ) : (
            <>
              {s.founders_public ? (
                <p><strong>{s.founders_public}</strong></p>
              ) : (
                <p className="muted small">The founders of {s.name} haven't joined found. yet.</p>
              )}
              <div className="claim-box">
                <p className="small"><strong>Is this your startup?</strong> Claim it to add your team, round, funding and location, and let founders message you.</p>
                <button className="btn btn-dark full" onClick={() => (user ? setClaiming(true) : navigate('/login'))}>Claim this startup</button>
              </div>
            </>
          )}
        </aside>
      </div>

      {claiming && <ClaimModal s={s} onClose={() => { setClaiming(false); api.startup(s.id).then(setS) }} />}
      {editing && (
        <Modal title={`Edit ${s.name}`} onClose={() => setEditing(false)}>
          <StartupForm initial={s} asAdmin={!!user?.is_admin && !mine} onSaved={(u) => { setS(u); setEditing(false) }} />
        </Modal>
      )}
    </div>
  )
}
