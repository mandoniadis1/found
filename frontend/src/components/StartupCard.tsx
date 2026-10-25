import { Link } from 'react-router-dom'
import { initials, money, sectorTone, shortStage } from '../format'
import type { Startup } from '../types'

export function Monogram({ name, sector, size = 44 }: { name: string; sector: string; size?: number }) {
  return (
    <div className="monogram" style={{ background: sectorTone(sector), width: size, height: size, fontSize: size * 0.42 }}>
      {initials(name.replace(/[^\p{L}\p{N}\s]/gu, '') || name)}
    </div>
  )
}

const prettyUrl = (url: string) => url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '')

// The name link stretches over the whole card (click anywhere to open the startup), and the website link sits
// above it so it can be clicked on its own. Links can't be nested, so the card itself isn't one big <a>.
export function StartupCard({ s, compact = false }: { s: Startup; compact?: boolean }) {
  const extras = [
    s.location,
    s.team_size ? `${s.team_size} ${s.team_size === 1 ? 'person' : 'people'}` : null,
    s.raised_usd ? `${money(s.raised_usd)} raised` : null,
  ].filter(Boolean)

  return (
    <article className={`startup-card${compact ? ' compact' : ''}`}>
      <div className="card-top">
        <Monogram name={s.name} sector={s.industries[0] ?? ''} size={compact ? 36 : 44} />
        <div className="card-title">
          <h3><Link to={`/startups/${s.id}`} className="stretched">{s.name}</Link></h3>
          <p className="muted small ellipsis">{s.affiliations.join(' · ')}</p>
        </div>
        {!compact && s.source === 'demo' ? <span className="pill pill-demo">Demo</span> : !compact && (s.hiring ? <span className="pill pill-hiring">Hiring</span> : s.looking_for ? <span className="pill pill-ask">Has an ask</span> : null)}
      </div>
      <p className="tagline clamp">{s.tagline}</p>
      <div className="card-meta">
        {s.industries.slice(0, 2).map((i) => <span key={i} className="tag">{i}</span>)}
        <span className="tag tag-stage">{shortStage(s.stage)}</span>
      </div>
      {!compact && (
        <div className="card-foot muted small">
          {extras.map((e, i) => <span key={i}>{i > 0 && <span className="dot">·</span>}{e}</span>)}
          {s.website ? (
            <a className="card-link" href={s.website} target="_blank" rel="noreferrer">
              {extras.length > 0 && <span className="dot">·</span>}{prettyUrl(s.website)} ↗
            </a>
          ) : extras.length === 0 && <span>No website listed</span>}
          {s.claimed && <span className="claimed" title="The founder is on found. — open the startup to message them">✓ Founder on found.</span>}
        </div>
      )}
    </article>
  )
}
