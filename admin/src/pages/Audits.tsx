import { useEffect, useState } from 'react'
import { api, type Audit } from '../api'
import { AuditCard } from './AuditCard'

export function Audits() {
  const [items, setItems] = useState<Audit[]>([])
  const [tab, setTab] = useState<'proposed' | 'all'>('proposed')
  useEffect(() => { api.audits().then(setItems) }, [])

  const shown = items.filter((a) => tab === 'all' || a.status === 'proposed')
  const spent = items.reduce((t, a) => t + a.result.cost_usd, 0)
  const replace = (u: Audit) => setItems((all) => all.map((a) => (a.id === u.id ? u : a)))

  return (
    <>
      <header className="page-head">
        <h1>Listing audits</h1>
        <p className="muted">
          The Listing Auditor (gpt-6-luna) reads a startup's own website and checks the listing. It only suggests;
          nothing changes until you apply it. Run audits from <b>All listings</b>.
        </p>
      </header>
      <div className="tabs">
        <button className={tab === 'proposed' ? 'on' : ''} onClick={() => setTab('proposed')}>Suggested fixes ({items.filter((a) => a.status === 'proposed').length})</button>
        <button className={tab === 'all' ? 'on' : ''} onClick={() => setTab('all')}>All audits ({items.length})</button>
      </div>
      <p className="muted small">Total spent on audits: ${spent.toFixed(4)}</p>
      {shown.length === 0 && <p className="empty">Nothing here yet.</p>}
      {shown.map((a) => <AuditCard key={a.id} a={a} onDecided={replace} />)}
    </>
  )
}
