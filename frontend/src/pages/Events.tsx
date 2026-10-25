import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { EventCard } from '../components/EventCard'
import { Modal } from '../components/Modal'
import { OpportunityCard } from '../components/OpportunityCard'
import type { EventInput, FoundEvent, Opportunity, Startup } from '../types'

type Idea = { emoji: string; title: string; description: string; kind: 'startup' | 'sector'; sector: string | null; capacity: number }

// Starter formats for moderators. Clicking one fills in the form; the moderator adds the date and place.
const IDEAS: Idea[] = [
  {
    emoji: '☕', title: 'Founders Breakfast', kind: 'sector', sector: 'Climate & Sustainability', capacity: 40,
    description: 'Monthly breakfast for founders working in this space. Everyone brings one ask and one offer.',
  },
  {
    emoji: '🔧', title: 'Open Lab', kind: 'startup', sector: null, capacity: 30,
    description: "Come see what we're building: a live demo, a chance to meet the team, and a conversation about who we're hiring.",
  },
  {
    emoji: '🎤', title: 'Demo Night', kind: 'sector', sector: 'Technology', capacity: 120,
    description: 'Five Yale teams demo what they built. Short demos, then honest Q&A about what broke along the way.',
  },
  {
    emoji: '🩺', title: 'Founders × Clinicians Mixer', kind: 'sector', sector: 'Health & Biotech', capacity: 60,
    description: 'Meet clinicians who want to pilot new tools, and the founders building them.',
  },
  {
    emoji: '🥂', title: 'Milestone Celebration', kind: 'startup', sector: null, capacity: 80,
    description: "We're celebrating a launch or funding round. Drinks, a short talk on lessons learned, and a recruiting table.",
  },
  {
    emoji: '💼', title: 'Office Hours with Alumni Angels', kind: 'sector', sector: null, capacity: 24,
    description: '15-minute slots with Yale alumni investors. Bring your deck and your hardest question.',
  },
]

function HostForm({ onCreated }: { onCreated: (e: FoundEvent) => void }) {
  const [mine, setMine] = useState<Startup[]>([])
  const [industries, setIndustries] = useState<string[]>([])
  const [form, setForm] = useState<EventInput>({
    title: '', description: '', kind: 'sector', sector: null, host_startup_id: null, starts_at: '', location: '', capacity: 40,
  })
  const [picked, setPicked] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.myStartups().then(setMine)
    api.options().then((o) => setIndustries(o.industries))
  }, [])

  const set = <K extends keyof EventInput>(k: K, v: EventInput[K]) => setForm((f) => ({ ...f, [k]: v }))

  function applyIdea(idea: Idea) {
    setPicked(idea.title)
    setForm((f) => ({
      ...f, title: idea.title, description: idea.description, kind: idea.kind, sector: idea.sector, capacity: idea.capacity,
      host_startup_id: idea.kind === 'startup' && mine.length === 1 ? mine[0].id : f.host_startup_id,
    }))
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      onCreated(await api.createEvent(form))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="host">
      <div className="ideas">
        <p className="eyebrow">Ideas for moderators</p>
        <div className="idea-grid">
          {IDEAS.map((idea) => (
            <button key={idea.title} type="button" className={`idea${picked === idea.title ? ' on' : ''}`} onClick={() => applyIdea(idea)}>
              <span className="idea-emoji">{idea.emoji}</span>
              <span>
                <strong>{idea.title}</strong>
                <span className="muted tiny">{idea.kind === 'startup' ? 'Your startup' : idea.sector ?? 'Any industry'}</span>
              </span>
            </button>
          ))}
        </div>
        <p className="muted tiny">Pick one to fill in the form, then make it yours.</p>
      </div>

      <form className="form" onSubmit={submit}>
        <div className="segmented wide">
          <button type="button" className={form.kind === 'sector' ? 'on' : ''} onClick={() => set('kind', 'sector')}>Industry / community event</button>
          <button type="button" className={form.kind === 'startup' ? 'on' : ''} onClick={() => set('kind', 'startup')}>My startup's event</button>
        </div>
        {form.kind === 'startup' && (
          mine.length === 0 ? (
            <p className="muted small">Claim or add your startup first to host a startup event. Find it on <Link to="/">Explore</Link> or add it on your <Link to="/profile">profile</Link>.</p>
          ) : (
            <label>Hosting startup
              <select required value={form.host_startup_id ?? ''} onChange={(e) => set('host_startup_id', Number(e.target.value) || null)}>
                <option value="">Choose…</option>
                {mine.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
          )
        )}
        <label>Title<input required value={form.title} onChange={(e) => set('title', e.target.value)} /></label>
        <label>Description<textarea required rows={3} value={form.description} onChange={(e) => set('description', e.target.value)} /></label>
        <div className="row2">
          <label>Industry
            <select value={form.sector ?? ''} onChange={(e) => set('sector', e.target.value || null)}>
              <option value="">All industries</option>
              {industries.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
          <label>Date & time<input required type="datetime-local" value={form.starts_at} onChange={(e) => set('starts_at', e.target.value)} /></label>
        </div>
        <div className="row2">
          <label>Location<input required placeholder="e.g. Tsai CITY, Room 201" value={form.location} onChange={(e) => set('location', e.target.value)} /></label>
          <label>Capacity<input type="number" min={1} value={form.capacity} onChange={(e) => set('capacity', Number(e.target.value))} /></label>
        </div>
        {error && <p className="error">{error}</p>}
        <button className="btn btn-dark" disabled={busy}>Publish event</button>
      </form>
    </div>
  )
}

export function Events() {
  const { user } = useAuth()
  const [events, setEvents] = useState<FoundEvent[]>([])
  const [programs, setPrograms] = useState<Opportunity[]>([])
  const [kind, setKind] = useState<'all' | 'startup' | 'sector'>('all')
  const [hosting, setHosting] = useState(false)

  useEffect(() => { api.events().then(setEvents) }, [user])
  useEffect(() => {
    api.opportunities({ category: ['programs', 'competitions'], within_days: 45 }).then((o) => setPrograms(o.slice(0, 4)))
  }, [])

  const shown = events.filter((e) => kind === 'all' || e.kind === kind)
  const update = (u: FoundEvent) => setEvents((all) => all.map((e) => (e.id === u.id ? u : e)))

  return (
    <div className="page narrow">
      <div className="page-head">
        <div>
          <p className="eyebrow">Events</p>
          <h1>What's happening</h1>
          <p className="lede">Founder breakfasts, demo nights and open labs, hosted by Yale founders and moderators.</p>
        </div>
        {user?.is_moderator ? (
          <button className="btn btn-dark" onClick={() => setHosting(true)}>+ Host an event</button>
        ) : (
          <Link to={user ? '/profile' : '/login'} className="btn btn-ghost">Become a moderator to host</Link>
        )}
      </div>

      {events.length > 0 && (
        <div className="segmented">
          {(['all', 'sector', 'startup'] as const).map((k) => (
            <button key={k} className={kind === k ? 'on' : ''} onClick={() => setKind(k)}>
              {k === 'all' ? 'All' : k === 'sector' ? 'Industry events' : 'Startup events'}
            </button>
          ))}
        </div>
      )}

      <div className="stack">
        {shown.map((e) => <EventCard key={e.id} e={e} onChange={update} />)}
        {events.length === 0 && (
          <div className="empty-events">
            <p className="serif-lg">No events yet. Host the first one.</p>
            <p className="muted">
              Moderators can host industry meetups or events for their own startup. Verify your LinkedIn and sign up as
              a moderator on your profile, then pick a format to start from.
            </p>
            <div className="idea-strip">
              {IDEAS.slice(0, 4).map((i) => <span key={i.title} className="chip static">{i.emoji} {i.title}</span>)}
            </div>
            {user?.is_moderator ? (
              <button className="btn btn-dark" onClick={() => setHosting(true)}>Host an event</button>
            ) : (
              <Link to={user ? '/profile' : '/login'} className="btn btn-dark">Become a moderator</Link>
            )}
          </div>
        )}
      </div>

      {programs.length > 0 && (
        <>
          <h2 className="section-title">Programs & competitions closing soon</h2>
          <div className="opp-grid two">{programs.map((o) => <OpportunityCard key={o.id} o={o} />)}</div>
          <p className="source-note">From the Tsai CITY Yale Startup Opportunities board. <Link to="/opportunities">See all →</Link></p>
        </>
      )}

      {hosting && (
        <Modal title="Host an event" onClose={() => setHosting(false)}>
          <HostForm onCreated={(e) => { setEvents((all) => [...all, e].sort((a, b) => a.starts_at.localeCompare(b.starts_at))); setHosting(false) }} />
        </Modal>
      )}
    </div>
  )
}
