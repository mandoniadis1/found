import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type DataSources, type Overview, type UsageDay } from '../api'

function Stat({ label, value, sub, to, alert }: { label: string; value: number | string; sub?: string; to?: string; alert?: boolean }) {
  const body = (
    <>
      <span className="stat-label">{label}</span>
      <strong>{value}</strong>
      {sub && <span className="stat-sub">{sub}</span>}
    </>
  )
  return to ? <Link to={to} className={`stat${alert ? ' alert' : ''}`}>{body}</Link> : <div className="stat">{body}</div>
}

export function Dashboard() {
  const [o, setO] = useState<Overview | null>(null)
  const [usage, setUsage] = useState<UsageDay[]>([])
  const [ds, setDs] = useState<DataSources | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [refreshMsg, setRefreshMsg] = useState('')

  useEffect(() => {
    api.overview().then(setO)
    api.usage().then(setUsage)
    api.dataSources().then(setDs)
  }, [])

  async function refreshNow() {
    setRefreshing(true)
    setRefreshMsg('')
    try {
      const r = await api.refreshNow()
      setRefreshMsg(r.status === 'ok'
        ? `Updated: ${r.startups_added} new and ${r.startups_updated} updated startups, ${r.opportunities_added} new opportunities, ${r.startups_removed} listings hidden.`
        : `Not applied: ${r.error}`)
    } catch (e) {
      setRefreshMsg((e as Error).message)
    } finally {
      setRefreshing(false)
      api.dataSources().then(setDs)
      api.overview().then(setO)
    }
  }
  const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—')

  if (!o) return <p className="muted">Loading…</p>
  const pct = Math.min(100, Math.round((o.scout_tokens_today / o.scout_daily_budget) * 100))
  const maxDay = Math.max(1, ...usage.map((u) => u.tokens))

  return (
    <>
      <header className="page-head">
        <h1>Dashboard</h1>
        <p className="muted">What needs you, and how the site is doing.</p>
      </header>

      <h2 className="section">Needs review</h2>
      <div className="stats">
        <Stat label="Founder claims" value={o.pending_claims} sub="waiting for a decision" to="/claims" alert={o.pending_claims > 0} />
        <Stat label="New startups" value={o.pending_startups} sub="hidden until approved" to="/submissions" alert={o.pending_startups > 0} />
      </div>

      <h2 className="section">Community</h2>
      <div className="stats">
        <Stat label="Members" value={o.members} sub={`${o.verified_members} verified Yale email`} to="/members" />
        <Stat label="LinkedIn on profile" value={o.linkedin_members} />
        <Stat label="Moderators" value={o.moderators} />
        <Stat label="Upcoming events" value={o.upcoming_events} />
      </div>

      <h2 className="section">Directory</h2>
      <div className="stats">
        <Stat label="Listed startups" value={o.listed_startups} to="/listings" />
        <Stat label="Claimed by founders" value={o.claimed_startups} />
        <Stat label="Corrected listings" value={o.corrected_startups} />
      </div>

      <h2 className="section">Scout helper (gpt-6-luna)</h2>
      <div className="panel">
        <div className="budget-row">
          <span>Today: <b>{o.scout_tokens_today.toLocaleString()}</b> of {o.scout_daily_budget.toLocaleString()} tokens · {o.scout_questions_today} questions</span>
          <span className="muted">≈ ${(o.scout_tokens_today * 0.1 / 1e6).toFixed(4)}</span>
        </div>
        <div className="meter"><span style={{ width: `${pct}%` }} className={pct > 80 ? 'hot' : ''} /></div>
        {usage.length > 0 && (
          <div className="bars" aria-label="Tokens per day, last 14 days">
            {[...usage].reverse().map((u) => (
              <div key={u.day} className="bar" title={`${u.day}: ${u.tokens.toLocaleString()} tokens, ${u.messages} questions`}>
                <span style={{ height: `${Math.max(4, (u.tokens / maxDay) * 100)}%` }} />
                <em>{u.day.slice(5)}</em>
              </div>
            ))}
          </div>
        )}
      </div>

      <h2 className="section">Data sources</h2>
      {ds && (
        <div className="panel">
          <div className="budget-row">
            <span>
              Yale Startup Directory + Tsai CITY board · last updated <b>{when(ds.last_success)}</b>
              {ds.refresh_days > 0 ? <> · next automatic refresh <b>{when(ds.next_due)}</b> (every {ds.refresh_days} days)</> : ' · automatic refresh off'}
            </span>
            <button className="btn sm" disabled={refreshing} onClick={refreshNow}>{refreshing ? 'Refreshing…' : 'Refresh now'}</button>
          </div>
          <p className="muted small">
            {ds.counts.startups_listed} startups listed{ds.counts.startups_removed ? `, ${ds.counts.startups_removed} hidden (gone from the source)` : ''} ·
            {' '}{ds.counts.opportunities} opportunities · {ds.counts.expected_deadlines} expected deadlines.
            Claimed listings keep their founder's edits; your corrections are re-applied after every refresh.
          </p>
          {refreshMsg && <p className="refresh-msg">{refreshMsg}</p>}
          {ds.history.length > 0 && (
            <table className="mini">
              <tbody>
                {ds.history.slice(0, 5).map((h) => (
                  <tr key={h.id}>
                    <td>{when(h.started_at)}</td>
                    <td>{h.trigger}</td>
                    <td><span className={`tag ${h.status === 'ok' ? 'ok' : 'warn'}`}>{h.status}</span></td>
                    <td className="muted">{h.stats ? `+${h.stats.startups_added} startups, +${h.stats.opportunities_added} opportunities, ${h.stats.startups_removed} hidden` : h.error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <h2 className="section">Setup</h2>
      <div className="panel setup">
        <div><span className="stat-label">Email</span>{o.mail_mode === 'outbox' ? 'Saved to output/outbox (not sent)' : `Sending via ${o.mail_mode}`}</div>
        <div><span className="stat-label">Data refresh</span>Every {ds?.refresh_days ?? 7} days, plus Refresh now</div>
      </div>
    </>
  )
}
