import { useEffect, useState } from 'react'
import { api, PUBLIC_SITE, type Claim } from '../api'

const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—')

export function Claims({ onChange }: { onChange: () => void }) {
  const [tab, setTab] = useState<'pending' | 'approved' | 'denied'>('pending')
  const [claims, setClaims] = useState<Claim[]>([])
  const [notes, setNotes] = useState<Record<number, string>>({})
  const [error, setError] = useState('')

  const load = () => api.claims(tab).then(setClaims).catch((e) => setError(e.message))
  useEffect(() => { load() }, [tab])

  async function decide(id: number, decision: 'approve' | 'deny') {
    setError('')
    try {
      await api.decideClaim(id, decision, notes[id] ?? '')
      await load()
      onChange()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <>
      <header className="page-head">
        <h1>Founder claims</h1>
        <p className="muted">People who couldn't verify with a company email. Check their LinkedIn, then approve or deny.</p>
      </header>
      <div className="tabs">
        {(['pending', 'approved', 'denied'] as const).map((t) => (
          <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>{t[0].toUpperCase() + t.slice(1)}</button>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
      {claims.length === 0 && <p className="empty">Nothing here.</p>}

      {claims.map((c) => (
        <article key={c.id} className="card">
          <div className="card-head">
            <h3><a href={`${PUBLIC_SITE}/startups/${c.startup_id}`} target="_blank" rel="noreferrer">{c.startup_name} ↗</a></h3>
            <span className="muted">{c.method === 'company_email' ? 'Company email link' : 'Manual review'} · {when(c.created_at)}</span>
          </div>
          <table className="kv">
            <tbody>
              <tr><th>Claimed by</th><td>{c.full_name}{c.role && ` · ${c.role}`}</td></tr>
              <tr><th>Verified Yale email</th><td>{c.requester_email}</td></tr>
              <tr><th>LinkedIn sign-in</th><td>{c.requester_linkedin_name ?? '—'}{c.requester_linkedin_email && ` · ${c.requester_linkedin_email}`}
                {c.requester_linkedin_dev_standin && <span className="tag warn">dev stand-in</span>}</td></tr>
              <tr><th>LinkedIn profile</th><td>{c.linkedin_profile_url ? <a href={c.linkedin_profile_url} target="_blank" rel="noreferrer">{c.linkedin_profile_url} ↗</a> : '—'}</td></tr>
              <tr><th>Work email</th><td>{c.work_email ?? '—'}</td></tr>
              <tr><th>Proof link</th><td>{c.evidence_url ? <a href={c.evidence_url} target="_blank" rel="noreferrer">{c.evidence_url} ↗</a> : '—'}</td></tr>
              <tr><th>Note</th><td className="pre">{c.note ?? '—'}</td></tr>
              {c.status !== 'pending' && <tr><th>Decision</th><td>{c.status} · {when(c.decided_at)}{c.admin_note && ` · “${c.admin_note}”`}</td></tr>}
            </tbody>
          </table>
          {c.status === 'pending' && (
            <>
              <p className="hint">Does their LinkedIn profile list {c.startup_name}, and does the name match their LinkedIn sign-in?</p>
              <div className="actions">
                <input placeholder="Note (optional, saved with the decision)" value={notes[c.id] ?? ''} onChange={(e) => setNotes({ ...notes, [c.id]: e.target.value })} />
                <button className="btn" onClick={() => decide(c.id, 'deny')}>Deny</button>
                <button className="btn primary" onClick={() => decide(c.id, 'approve')}>Approve</button>
              </div>
            </>
          )}
        </article>
      ))}
    </>
  )
}
