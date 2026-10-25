import { useEffect, useState } from 'react'
import { api, PUBLIC_SITE, type Audit, type Startup } from '../api'
import { AuditCard } from './AuditCard'

const VERIFIED = { company_email: 'Company email', admin_review: 'Admin review' } as Record<string, string>

export function Listings() {
  const [q, setQ] = useState('')
  const [items, setItems] = useState<Startup[]>([])
  const [running, setRunning] = useState<number | null>(null)
  const [result, setResult] = useState<Audit | null>(null)
  const [error, setError] = useState('')

  async function audit(s: Startup) {
    setRunning(s.id)
    setError('')
    setResult(null)
    try { setResult(await api.audit(s.id)) } catch (e) { setError(`${s.name}: ${(e as Error).message}`) } finally { setRunning(null) }
  }

  useEffect(() => {
    const t = setTimeout(() => api.allStartups(q).then(setItems), 200)
    return () => clearTimeout(t)
  }, [q])

  return (
    <>
      <header className="page-head">
        <h1>All listings</h1>
        <p className="muted">Every startup in the directory. Click Audit to have the Listing Auditor check a listing against the startup's own website, or open it on the public site (as an admin) to edit it by hand.</p>
      </header>
      <input className="search" placeholder="Search by name or pitch…" value={q} onChange={(e) => setQ(e.target.value)} />
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="audit-result">
          <div className="audit-result-head"><span className="stat-label">Latest audit</span><button className="link dark" onClick={() => setResult(null)}>Close</button></div>
          <AuditCard a={result} onDecided={(u) => { setResult(u); api.allStartups(q).then(setItems) }} />
        </div>
      )}
      <table className="table">
        <thead>
          <tr><th>Startup</th><th>Industries</th><th>Stage</th><th>Source</th><th>Status</th><th>Founder</th><th /></tr>
        </thead>
        <tbody>
          {items.map((s) => (
            <tr key={s.id}>
              <td><strong>{s.name}</strong>{s.correction_note && <span className="tag" title={s.correction_note}>corrected</span>}</td>
              <td>{s.industries.join(', ')}</td>
              <td>{s.stage}</td>
              <td>{s.source === 'yale_pitchbook' ? 'Pitchbook' : s.source === 'demo' ? <span className="tag">Demo</span> : 'Member'}</td>
              <td><span className={`tag ${s.status === 'listed' ? 'ok' : 'warn'}`}>{s.status}</span></td>
              <td>{s.founder ? <>{s.founder.first_name} {s.founder.last_name}<span className="muted"> · {VERIFIED[s.founder_verified_via ?? ''] ?? '—'}</span></> : <span className="muted">Unclaimed</span>}</td>
              <td className="row-actions">
                <button className="btn sm" disabled={running !== null || !s.website} title={s.website ? 'Check this listing against its website' : 'No website'} onClick={() => audit(s)}>
                  {running === s.id ? 'Auditing…' : 'Audit'}
                </button>
                <a href={`${PUBLIC_SITE}/startups/${s.id}`} target="_blank" rel="noreferrer">Open ↗</a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted small">{items.length} listings</p>
    </>
  )
}
