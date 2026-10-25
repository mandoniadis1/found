import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import { EventCard } from '../components/EventCard'
import { OpportunityCard } from '../components/OpportunityCard'
import { StartupCard } from '../components/StartupCard'
import type { JoinBoard } from '../types'

// For people with no startup or idea yet: every way into a Yale startup, in one place.
export function Join() {
  const { user } = useAuth()
  const [board, setBoard] = useState<JoinBoard | null>(null)

  useEffect(() => { api.joinBoard().then(setBoard) }, [])

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <p className="eyebrow">Join a startup</p>
          <h1>No idea yet? Join one.</h1>
          <p className="lede">Yale startups looking for people, co-founder searches, and events where you can meet founders. Then make yourself findable.</p>
        </div>
      </div>

      <div className="join-steps">
        <div className="join-step">
          <span className="step">1</span>
          <div><strong>Make yourself findable</strong><p className="muted small">Turn on "Open to joining" on your profile with the roles and industries you want. Founders on found. can then message you.</p>
            <Link to={user ? '/profile' : '/signup'} className="btn btn-dark sm">{user?.open_to_join ? 'Edit your joining profile' : user ? 'Turn it on' : 'Join found.'}</Link></div>
        </div>
        <div className="join-step">
          <span className="step">2</span>
          <div><strong>Reach out</strong><p className="muted small">Message founders of the startups below, or answer a co-founder search. Founders who haven't joined found. yet list a contact in their ask.</p></div>
        </div>
        <div className="join-step">
          <span className="step">3</span>
          <div><strong>Show up</strong><p className="muted small">Meet founders in person at events{board?.events.length ? ' coming up below' : ' (see Events)'}.</p></div>
        </div>
      </div>

      {user?.is_founder && (
        <div className="founder-callout">
          <span><b>You're a founder.</b> {board?.open_people ?? 0} {board?.open_people === 1 ? 'person is' : 'people are'} open to joining a startup.</span>
          <Link to="/people" className="btn btn-dark sm">Browse people open to joining</Link>
        </div>
      )}

      <h2 className="section-title">Startups looking for people</h2>
      {board && board.startups.length === 0 && <p className="muted">No startups have posted an ask yet.</p>}
      <div className="grid">{board?.startups.map((s) => <StartupCard key={s.id} s={s} />)}</div>

      <h2 className="section-title">Co-founder searches and startup asks</h2>
      <p className="muted small">From the Tsai CITY board: people looking for co-founders and help, and startups looking for new owners.</p>
      <div className="opp-grid">{board?.asks.map((o) => <OpportunityCard key={o.id} o={o} />)}</div>

      {board && board.events.length > 0 && (
        <>
          <h2 className="section-title">Meet founders</h2>
          <div className="stack">{board.events.map((e) => <EventCard key={e.id} e={e} />)}</div>
        </>
      )}
    </div>
  )
}
