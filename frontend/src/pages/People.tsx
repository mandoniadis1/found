import { useEffect, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { Joiner, Options } from '../types'

// For founders: members who opted in to joining a startup. The API only answers verified founders.
export function People() {
  const { user, ready } = useAuth()
  const navigate = useNavigate()
  const [opts, setOpts] = useState<Options | null>(null)
  const [people, setPeople] = useState<Joiner[] | null>(null)
  const [role, setRole] = useState('')
  const [industry, setIndustry] = useState('')
  const [commitment, setCommitment] = useState('')
  const [error, setError] = useState('')

  useEffect(() => { api.options().then(setOpts) }, [])
  useEffect(() => {
    if (!user?.is_founder) return
    api.peopleOpen({ role: role || undefined, industry: industry || undefined, commitment: commitment || undefined })
      .then(setPeople).catch((e) => setError(e.message))
  }, [user, role, industry, commitment])

  if (!ready) return null
  if (!user) return <Navigate to="/login" />

  async function message(p: Joiner) {
    const conv = await api.startConversation(p.id)
    navigate(`/messages/${conv.id}`)
  }

  return (
    <div className="page narrow">
      <div className="page-head">
        <div>
          <p className="eyebrow">For founders</p>
          <h1>People open to joining</h1>
          <p className="lede">Yale members who want to join a startup and chose to be found. Message the ones who fit.</p>
        </div>
      </div>

      {!user.is_founder ? (
        <div className="empty-events">
          <p className="serif-lg">This list is for founders.</p>
          <p className="muted">Add or claim your startup to see who's open to joining. Looking to join one yourself? Turn on "Open to joining" on your profile.</p>
          <div className="opp-actions"><Link to="/profile" className="btn btn-dark">Go to your profile</Link><Link to="/join" className="btn btn-ghost">Join a startup</Link></div>
        </div>
      ) : (
        <>
          <div className="people-filters">
            <select className="sort" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="">Any role</option>{opts?.join_roles.filter((r) => r !== 'Any role').map((r) => <option key={r}>{r}</option>)}
            </select>
            <select className="sort" value={industry} onChange={(e) => setIndustry(e.target.value)}>
              <option value="">Any industry</option>{opts?.industries.map((i) => <option key={i}>{i}</option>)}
            </select>
            <select className="sort" value={commitment} onChange={(e) => setCommitment(e.target.value)}>
              <option value="">Any time commitment</option>{opts?.join_commitments.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          {error && <p className="error">{error}</p>}
          {people && people.length === 0 && <p className="muted">Nobody matches those filters yet.</p>}
          <div className="stack">
            {people?.map((p) => (
              <article key={p.id} className="person-card">
                <div className="avatar">{p.first_name[0]}{p.last_name[0]}</div>
                <div className="person-main">
                  <div className="person-top">
                    <strong>{p.first_name} {p.last_name}</strong>
                    {p.linkedin_url && <a className="li-link" href={p.linkedin_url} target="_blank" rel="noreferrer">LinkedIn ↗</a>}
                    {p.commitment && <span className="pill">{p.commitment}</span>}
                  </div>
                  <p className="muted small">{[p.school, p.headline].filter(Boolean).join(' · ')}</p>
                  {p.pitch && <p className="person-pitch">“{p.pitch}”</p>}
                  <div className="card-meta">
                    {p.roles.map((r) => <span key={r} className="tag tag-stage">{r}</span>)}
                    {p.industries.map((i) => <span key={i} className="tag">{i}</span>)}
                  </div>
                </div>
                <button className="btn btn-dark sm" onClick={() => message(p)}>Message {p.first_name}</button>
              </article>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
