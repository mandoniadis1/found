import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { eventDate } from '../format'
import type { FoundEvent } from '../types'

export function EventCard({ e, onChange, compact = false }: {
  e: FoundEvent
  onChange?: (e: FoundEvent) => void
  compact?: boolean
}) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const d = eventDate(e.starts_at)
  const full = e.attending >= e.capacity

  async function rsvp() {
    if (!user) return navigate('/login')
    setBusy(true)
    setError('')
    try {
      onChange?.(await api.rsvp(e.id))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className={`event-card${compact ? ' compact' : ''}`}>
      <div className="event-date">
        <span>{d.month}</span>
        <strong>{d.day}</strong>
      </div>
      <div className="event-body">
        <div className="event-kicker">
          <span className="pill">{e.kind === 'startup' ? 'Startup event' : 'Sector event'}</span>
          {e.sector && <span className="muted small">{e.sector}</span>}
        </div>
        <h3>{e.title}</h3>
        <p className="muted small">
          {d.weekday}, {d.time} · {e.location}
        </p>
        {!compact && <p className="event-desc">{e.description}</p>}
        <p className="muted small">
          {e.host_startup && e.host_startup_id ? (
            <>Hosted by <Link to={`/startups/${e.host_startup_id}`}>{e.host_startup}</Link> · </>
          ) : null}
          Organized by {e.organizer.first_name} {e.organizer.last_name}
        </p>
      </div>
      {!compact && (
        <div className="event-side">
          <div className="attending">
            <strong>{e.attending}</strong>
            <span className="muted small">/ {e.capacity} going</span>
          </div>
          <button
            className={e.i_am_going ? 'btn btn-ghost' : 'btn btn-dark'}
            disabled={busy || (full && !e.i_am_going)}
            onClick={rsvp}
          >
            {e.i_am_going ? 'Going ✓' : full ? 'Full' : 'RSVP'}
          </button>
          {error && <p className="error small">{error}</p>}
        </div>
      )}
    </article>
  )
}
