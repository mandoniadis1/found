import { useEffect, useMemo, useState } from 'react'
import { api } from '../api'
import { OpportunityCard } from '../components/OpportunityCard'
import { MONTHS } from '../format'
import type { ExpectedDeadline, Opportunity } from '../types'

const CATEGORIES: { key: string; label: string; blurb: string }[] = [
  { key: 'programs', label: 'Programs & events', blurb: 'Accelerators, fellowships, residencies and showcases' },
  { key: 'grants', label: 'Grants', blurb: 'Non-dilutive funding' },
  { key: 'competitions', label: 'Competitions', blurb: 'Pitch and venture competitions with prizes' },
  { key: 'perks', label: 'Perks & credits', blurb: 'Free tools, cloud credits and services' },
  { key: 'asks', label: 'Startup asks', blurb: 'Co-founder searches and startups looking for help' },
]

export function Opportunities() {
  const [items, setItems] = useState<Opportunity[]>([])
  const [counts, setCounts] = useState<Record<string, number>>({})
  const [deadlines, setDeadlines] = useState<ExpectedDeadline[]>([])
  const [cat, setCat] = useState<string | null>(null)
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [soon, setSoon] = useState(false)
  const [sort, setSort] = useState('deadline')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.opportunityCounts().then(setCounts)
    api.deadlines().then(setDeadlines)
  }, [])
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 250)
    return () => clearTimeout(t)
  }, [q])
  useEffect(() => {
    setLoading(true)
    api.opportunities({ q: debouncedQ, category: cat ? [cat] : undefined, within_days: soon ? 30 : undefined, sort })
      .then(setItems).finally(() => setLoading(false))
  }, [debouncedQ, cat, soon, sort])

  const total = Object.values(counts).reduce((a, b) => a + b, 0)

  // Expected deadlines grouped by month, starting with this month.
  const byMonth = useMemo(() => {
    const now = new Date()
    const key = (d: ExpectedDeadline) => (d.expected_year ?? now.getFullYear()) * 12 + ((d.expected_month ?? 1) - 1)
    const thisMonth = now.getFullYear() * 12 + now.getMonth()
    const groups = new Map<number, ExpectedDeadline[]>()
    for (const d of deadlines) {
      if (!d.expected_month || key(d) < thisMonth) continue
      groups.set(key(d), [...(groups.get(key(d)) ?? []), d])
    }
    return [...groups.entries()].sort((a, b) => a[0] - b[0]).slice(0, 4)
  }, [deadlines])

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <p className="eyebrow">Opportunities</p>
          <h1>Fuel for what you're building</h1>
          <p className="lede">Accelerators, grants, competitions, perks and asks from across the Yale ecosystem, sorted by what's due first.</p>
        </div>
      </div>

      <div className="cat-tiles">
        <button className={`cat-tile${cat === null ? ' on' : ''}`} onClick={() => setCat(null)}>
          <strong>{total}</strong><span>Everything</span>
        </button>
        {CATEGORIES.map((c) => (
          <button key={c.key} className={`cat-tile cat-${c.key}${cat === c.key ? ' on' : ''}`} onClick={() => setCat(cat === c.key ? null : c.key)} title={c.blurb}>
            <strong>{counts[c.key] ?? 0}</strong><span>{c.label}</span>
          </button>
        ))}
      </div>

      <div className="opp-layout">
        <section>
          <div className="opp-toolbar">
            <div className="search small-search">
              <span className="search-icon">⌕</span>
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, org, topic or city…" />
            </div>
            <label className="toggle tight inline">
              <input type="checkbox" checked={soon} onChange={(e) => setSoon(e.target.checked)} />
              <span className="switch" /> Due in 30 days
            </label>
            <select className="sort" value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="deadline">Deadline first</option>
              <option value="newest">Newest</option>
            </select>
          </div>
          <p className="muted small results-count">{loading ? 'Loading…' : `${items.length} ${items.length === 1 ? 'opportunity' : 'opportunities'}`}</p>
          <div className="opp-grid">
            {items.map((o) => <OpportunityCard key={o.id} o={o} />)}
          </div>
          {!loading && items.length === 0 && <p className="muted">Nothing matches. Try another category or search.</p>}
          <p className="source-note">
            From the Tsai CITY Yale Startup Opportunities board. Some posts come from outside organizations that
            Tsai CITY doesn't vet, so check details on the official page before applying.
          </p>
        </section>

        <aside className="timeline">
          <h3>On the horizon</h3>
          <p className="muted small">Expected application windows, estimated from past cycles.</p>
          {byMonth.map(([k, list]) => (
            <div key={k} className="tl-month">
              <div className="tl-label">{MONTHS[k % 12]} {Math.floor(k / 12)}</div>
              <ul>
                {list.map((d) => (
                  <li key={d.id}>
                    {d.website ? <a href={d.website} target="_blank" rel="noreferrer">{d.name}</a> : <span>{d.name}</span>}
                    {d.expected_window && <span className="muted tiny">{d.expected_window}</span>}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </aside>
      </div>
    </div>
  )
}
