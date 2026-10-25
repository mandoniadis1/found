import { useState } from 'react'
import { deadlineLabel } from '../format'
import type { Opportunity } from '../types'
import { Modal } from './Modal'

const CATEGORY_SHORT: Record<string, string> = {
  programs: 'Program',
  perks: 'Perk',
  grants: 'Grant',
  competitions: 'Competition',
  asks: 'Startup ask',
}

function Paragraphs({ text }: { text: string }) {
  return <>{text.split(/\n{2,}|\n/).filter(Boolean).map((p, i) => <p key={i}>{p}</p>)}</>
}

export function OpportunityDetail({ o }: { o: Opportunity }) {
  const due = deadlineLabel(o.deadline, o.rolling)
  return (
    <div className="opp-detail">
      <p className="muted">{[o.org, o.location].filter(Boolean).join(' · ')}</p>
      <div className="opp-facts">
        <div><span className="muted small">Deadline</span><strong className={due.soon ? 'soon' : ''}>{due.text}</strong></div>
        {o.start_date && <div><span className="muted small">Starts</span><strong>{new Date(o.start_date + 'T12:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</strong></div>}
        {o.grand_prize && <div><span className="muted small">Prize</span><strong>{o.grand_prize}</strong></div>}
      </div>
      {o.description && <div className="prose"><Paragraphs text={o.description} /></div>}
      {o.ideal_candidate && (
        <>
          <h4>Who it's for</h4>
          <div className="prose"><Paragraphs text={o.ideal_candidate} /></div>
        </>
      )}
      {o.curator_note && <p className="note">{o.curator_note}</p>}
      <div className="opp-actions">
        {o.apply_url && <a className="btn btn-dark" href={o.apply_url} target="_blank" rel="noreferrer">Apply ↗</a>}
        {!o.apply_url && o.apply_email && <a className="btn btn-dark" href={`mailto:${o.apply_email}`}>Email to apply</a>}
        {o.website && o.website !== o.apply_url && <a className="btn btn-ghost" href={o.website} target="_blank" rel="noreferrer">Website ↗</a>}
      </div>
      <p className="source-note">From the Tsai CITY Yale Startup Opportunities board</p>
    </div>
  )
}

export function OpportunityCard({ o, compact = false }: { o: Opportunity; compact?: boolean }) {
  const [open, setOpen] = useState(false)
  const due = deadlineLabel(o.deadline, o.rolling)
  return (
    <>
      <button className={`opp-card cat-${o.category}${compact ? ' compact' : ''}`} onClick={() => setOpen(true)}>
        <div className="opp-top">
          <span className="opp-cat">{CATEGORY_SHORT[o.category] ?? o.category_label}</span>
          <span className={`opp-due${due.soon ? ' soon' : ''}`}>{due.text}</span>
        </div>
        <h3>{o.title}</h3>
        {(o.org || o.location) && <p className="muted small ellipsis">{[o.org, o.location].filter(Boolean).join(' · ')}</p>}
        {!compact && o.description && <p className="opp-desc clamp">{o.description}</p>}
      </button>
      {open && (
        <Modal title={o.title} onClose={() => setOpen(false)}>
          <OpportunityDetail o={o} />
        </Modal>
      )}
    </>
  )
}
