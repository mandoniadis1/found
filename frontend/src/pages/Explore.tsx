import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type StartupQuery } from '../api'
import { OpportunityCard } from '../components/OpportunityCard'
import { Scout } from '../components/Scout'
import { StartupCard } from '../components/StartupCard'
import { YaleMark } from '../components/YaleMark'
import { sectorTone } from '../format'
import type { FilterOption, Filters, Opportunity, Startup } from '../types'

type Multi = 'industry' | 'stage' | 'affiliation' | 'round' | 'location'
const EMPTY_MULTI: Record<Multi, string[]> = { industry: [], stage: [], affiliation: [], round: [], location: [] }

const TEAM_BUCKETS = [
  { label: 'Any', min: undefined, max: undefined },
  { label: '1–5', min: 1, max: 5 },
  { label: '6–15', min: 6, max: 15 },
  { label: '16+', min: 16, max: undefined },
]

function FilterGroup({ title, options, selected, onToggle, startOpen = true, swatches = false }: {
  title: string
  options: FilterOption[]
  selected: string[]
  onToggle: (v: string) => void
  startOpen?: boolean
  swatches?: boolean
}) {
  const [open, setOpen] = useState(startOpen)
  const [all, setAll] = useState(false)
  const shown = all ? options : options.slice(0, 7)
  return (
    <div className="filter-group">
      <button className="filter-title" onClick={() => setOpen(!open)}>
        {title}
        {selected.length > 0 && <span className="count-badge">{selected.length}</span>}
        <span className="chev">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="filter-options">
          {shown.map((o) => (
            <label key={o.value} className={`filter-opt${selected.includes(o.value) ? ' on' : ''}`}>
              <input type="checkbox" checked={selected.includes(o.value)} onChange={() => onToggle(o.value)} />
              {swatches && <span className="swatch" style={{ background: sectorTone(o.value) }} />}
              <span>{o.value}</span>
              <span className="muted small">{o.count}</span>
            </label>
          ))}
          {options.length > 7 && (
            <button className="link-btn more" onClick={() => setAll(!all)}>{all ? 'Show less' : `Show all ${options.length}`}</button>
          )}
        </div>
      )}
    </div>
  )
}

export function Explore() {
  const [filters, setFilters] = useState<Filters | null>(null)
  const [startups, setStartups] = useState<Startup[]>([])
  const [closing, setClosing] = useState<Opportunity[]>([])
  const [oppTotal, setOppTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [multi, setMulti] = useState(EMPTY_MULTI)
  const [team, setTeam] = useState(0)
  const [hiring, setHiring] = useState(false)
  const [hasAsk, setHasAsk] = useState(false)
  const [hasFounder, setHasFounder] = useState(false)
  const [sort, setSort] = useState('name')

  useEffect(() => {
    api.filters().then(setFilters)
    api.opportunities({ within_days: 21 }).then((o) => setClosing(o.slice(0, 3)))
    api.opportunityCounts().then((c) => setOppTotal(Object.values(c).reduce((a, b) => a + b, 0)))
  }, [])
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 250)
    return () => clearTimeout(t)
  }, [q])

  const query: StartupQuery = useMemo(() => ({
    q: debouncedQ, ...multi, team_min: TEAM_BUCKETS[team].min, team_max: TEAM_BUCKETS[team].max,
    hiring, has_ask: hasAsk, has_founder: hasFounder, sort,
  }), [debouncedQ, multi, team, hiring, hasAsk, hasFounder, sort])

  useEffect(() => {
    setLoading(true)
    api.startups(query).then(setStartups).finally(() => setLoading(false))
  }, [query])

  const toggle = (key: Multi, v: string) =>
    setMulti((m) => ({ ...m, [key]: m[key].includes(v) ? m[key].filter((x) => x !== v) : [...m[key], v] }))

  const activeCount = Object.values(multi).flat().length + (team ? 1 : 0) + (hiring ? 1 : 0) + (hasAsk ? 1 : 0) + (hasFounder ? 1 : 0)
  const clear = () => { setMulti(EMPTY_MULTI); setTeam(0); setHiring(false); setHasAsk(false); setHasFounder(false); setQ('') }

  return (
    <div className="page">
      <section className="hero">
        <div className="hero-top">
          <p className="eyebrow">The Yale startup network</p>
          <YaleMark />
        </div>
        <h1 className="one-line">Find the people building <em>next door.</em></h1>
        <p className="lede">
          Every Yale startup and every opportunity to help them grow, in one place. Search by industry, stage and
          school, then meet the founders.
        </p>
        <div className="hero-row">
          <div className="search">
            <span className="search-icon">⌕</span>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search startups, industries, ideas…" />
          </div>
          <div className="hero-stats">
            <div><strong>{filters?.total ?? '—'}</strong><span className="muted small">startups</span></div>
            <Link to="/opportunities"><strong>{oppTotal || '—'}</strong><span className="muted small">opportunities</span></Link>
          </div>
        </div>
      </section>

      {closing.length > 0 && (
        <section className="closing">
          <div className="closing-head">
            <h2 className="section-title">Closing soon</h2>
            <Link to="/opportunities" className="link-arrow">All opportunities →</Link>
          </div>
          <div className="closing-grid">{closing.map((o) => <OpportunityCard key={o.id} o={o} compact />)}</div>
        </section>
      )}

      <div className="explore">
        <aside className="filters">
          <div className="filters-head">
            <strong>Filters</strong>
            {activeCount > 0 && <button className="link-btn" onClick={clear}>Clear all</button>}
          </div>
          {filters && (
            <>
              <FilterGroup title="Industry" options={filters.industries} selected={multi.industry} onToggle={(v) => toggle('industry', v)} swatches />
              <FilterGroup title="Stage" options={filters.stages} selected={multi.stage} onToggle={(v) => toggle('stage', v)} />
              <FilterGroup title="Yale affiliation" options={filters.affiliations} selected={multi.affiliation} onToggle={(v) => toggle('affiliation', v)} />
              {filters.rounds.length > 0 && (
                <FilterGroup title="Round" options={filters.rounds} selected={multi.round} onToggle={(v) => toggle('round', v)} startOpen={false} />
              )}
              {filters.locations.length > 0 && (
                <FilterGroup title="Location" options={filters.locations} selected={multi.location} onToggle={(v) => toggle('location', v)} startOpen={false} />
              )}
              {filters.with_team_size > 0 && (
                <div className="filter-group">
                  <div className="filter-title static">Team size</div>
                  <div className="segmented">
                    {TEAM_BUCKETS.map((b, i) => (
                      <button key={b.label} className={team === i ? 'on' : ''} onClick={() => setTeam(i)}>{b.label}</button>
                    ))}
                  </div>
                </div>
              )}
              <label className="toggle">
                <input type="checkbox" checked={hiring} onChange={(e) => setHiring(e.target.checked)} />
                <span className="switch" /> Hiring
              </label>
              <label className="toggle tight">
                <input type="checkbox" checked={hasAsk} onChange={(e) => setHasAsk(e.target.checked)} />
                <span className="switch" /> Has an ask
              </label>
              <label className="toggle tight" title="Startups whose founder has joined found. — you can message them">
                <input type="checkbox" checked={hasFounder} onChange={(e) => setHasFounder(e.target.checked)} />
                <span className="switch" /> Founder on found. <span className="muted small">({filters.with_founder})</span>
              </label>
              {(filters.rounds.length === 0 || filters.with_team_size === 0) && (
                <p className="filter-note">
                  Round, funding, team size and location filters appear as founders claim their listings and add them.
                </p>
              )}
            </>
          )}
        </aside>

        <section className="results">
          <div className="results-head">
            <p className="muted">{loading ? 'Loading…' : `${startups.length} startup${startups.length === 1 ? '' : 's'}`}</p>
            <select className="sort" value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="name">A–Z</option>
              <option value="stage">Most advanced stage</option>
              <option value="newest">Recently added</option>
            </select>
          </div>
          {filters && (
            <div className="legend" aria-label="Color key">
              <span className="legend-title">Color = industry</span>
              {filters.industries.map((o) => (
                <button key={o.value} className={`legend-item${multi.industry.includes(o.value) ? ' on' : ''}`} onClick={() => toggle('industry', o.value)}>
                  <span className="swatch" style={{ background: sectorTone(o.value) }} />{o.value}
                </button>
              ))}
            </div>
          )}
          {!loading && startups.length === 0 ? (
            <div className="empty">
              <p className="serif-lg">No startups match those filters.</p>
              <button className="btn btn-ghost" onClick={clear}>Clear filters</button>
            </div>
          ) : (
            <div className="grid">
              {startups.map((s) => <StartupCard key={s.id} s={s} />)}
            </div>
          )}
          <p className="source-note">Startup listings from the Yale Startup Directory (Yale Pitchbook).</p>
        </section>
      </div>
      <Scout />
    </div>
  )
}
