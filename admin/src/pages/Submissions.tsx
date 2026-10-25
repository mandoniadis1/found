import { useEffect, useState } from 'react'
import { api, PUBLIC_SITE, type Startup } from '../api'

export function Submissions({ onChange }: { onChange: () => void }) {
  const [items, setItems] = useState<Startup[]>([])
  const [error, setError] = useState('')

  const load = () => api.pendingStartups().then(setItems).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  async function decide(id: number, decision: 'approve' | 'reject') {
    setError('')
    try {
      await api.decideStartup(id, decision)
      await load()
      onChange()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <>
      <header className="page-head">
        <h1>New startups</h1>
        <p className="muted">Startups members added. They stay hidden from Explore until you approve them.</p>
      </header>
      {error && <p className="error">{error}</p>}
      {items.length === 0 && <p className="empty">No submissions waiting.</p>}
      {items.map((s) => (
        <article key={s.id} className="card">
          <div className="card-head">
            <h3><a href={`${PUBLIC_SITE}/startups/${s.id}`} target="_blank" rel="noreferrer">{s.name} ↗</a></h3>
            <span className="muted">{s.industries.join(', ')} · {s.stage}</span>
          </div>
          <p>{s.tagline}</p>
          <p className="muted">
            Submitted by {s.founder ? `${s.founder.first_name} ${s.founder.last_name}` : '—'}
            {s.founder?.linkedin_url && <> · <a href={s.founder.linkedin_url} target="_blank" rel="noreferrer">LinkedIn ↗</a></>} · {s.affiliations.join(', ')}
            {s.website && <> · <a href={s.website} target="_blank" rel="noreferrer">{s.website} ↗</a></>}
          </p>
          <div className="actions right">
            <button className="btn" onClick={() => decide(s.id, 'reject')}>Reject</button>
            <button className="btn primary" onClick={() => decide(s.id, 'approve')}>Approve and list</button>
          </div>
        </article>
      ))}
    </>
  )
}
