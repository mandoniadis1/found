import { api, PUBLIC_SITE, type Audit } from '../api'

const VERDICT = { accurate: 'Accurate', needs_changes: 'Needs changes', unclear: 'Unclear' }

// One Listing Auditor result: current vs suggested, the evidence quotes (checked by code), what it read, and cost.
export function AuditCard({ a, onDecided }: { a: Audit; onDecided?: (a: Audit) => void }) {
  const r = a.result
  const rep = r.report
  const decide = async (d: 'apply' | 'dismiss') => onDecided?.(await api.decideAudit(a.id, d))

  return (
    <article className="card">
      <div className="card-head">
        <h3><a href={`${PUBLIC_SITE}/startups/${a.startup_id}`} target="_blank" rel="noreferrer">{r.name} ↗</a></h3>
        <span>
          <span className={`tag ${a.verdict === 'accurate' ? 'ok' : a.verdict === 'needs_changes' ? 'warn' : ''}`}>{VERDICT[a.verdict]}</span>
          {a.status === 'applied' && <span className="tag ok">applied</span>}
          {a.status === 'dismissed' && <span className="tag">dismissed</span>}
        </span>
      </div>
      <p>{rep.summary}</p>
      {a.verdict === 'needs_changes' && (
        <table className="compare">
          <thead><tr><th /><th>Listing now</th><th>Auditor suggests</th></tr></thead>
          <tbody>
            <tr><th>Pitch</th><td>{r.current_tagline}</td><td>{rep.suggested_tagline ?? <span className="muted">(keep)</span>}</td></tr>
            <tr><th>Industries</th><td>{r.current_industries.join(', ')}</td><td>{rep.suggested_industries.join(', ') || <span className="muted">(keep)</span>}</td></tr>
          </tbody>
        </table>
      )}
      {rep.evidence.length > 0 && (
        <div className="evidence">
          <span className="stat-label">Evidence from the website (verified in code)</span>
          {rep.evidence.map((e, i) => <blockquote key={i}>“{e.quote}”<span>{e.supports}</span></blockquote>)}
        </div>
      )}
      <p className="meta-line">
        Read {r.pages_read.length} page{r.pages_read.length === 1 ? '' : 's'} · {r.input_tokens.toLocaleString()} in
        {r.cached_tokens ? ` (${r.cached_tokens.toLocaleString()} cached)` : ''} / {r.output_tokens.toLocaleString()} out tokens · ${r.cost_usd.toFixed(5)}
        {r.dropped_quotes > 0 && <> · <b>{r.dropped_quotes} unverifiable quote{r.dropped_quotes > 1 ? 's' : ''} removed</b></>}
        {r.flagged_lines.length > 0 && <> · <b>{r.flagged_lines.length} suspicious line{r.flagged_lines.length > 1 ? 's' : ''} flagged</b></>}
      </p>
      {a.status === 'proposed' && onDecided && (
        <div className="actions right">
          <button className="btn" onClick={() => decide('dismiss')}>Dismiss</button>
          <button className="btn primary" onClick={() => decide('apply')}>Apply correction</button>
        </div>
      )}
    </article>
  )
}
