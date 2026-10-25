import { useEffect, useRef, useState, type FormEvent } from 'react'
import { ApiError, api } from '../api'
import type { ChatTurn, ScoutOut } from '../types'
import { OpportunityCard } from './OpportunityCard'
import { StartupCard } from './StartupCard'

type Turn = ChatTurn & { result?: ScoutOut; note?: boolean }

const TIRED = "🐾 Woof, that's all my sniffing for today! Handsome Dan says rest up and come back tomorrow. Meanwhile, the filters on the left can find anything."
const HICCUP = '🐶 Oops, I got distracted by a squirrel. Mind asking that again?'

const SUGGESTIONS = [
  'Climate startups making revenue',
  'Startups that are hiring',
  'Grants due in the next month',
  'Free credits for my startup',
]

// Small, budgeted helper (gpt-6-luna). If the whole site's daily budget is used up it isn't shown at all.
// If only this visitor's daily budget is used up, it stays and tells them (cutely) to come back tomorrow.
export function Scout() {
  const [available, setAvailable] = useState(false)  // site budget left today
  const [tired, setTired] = useState(false)          // this visitor's budget is used up
  const [open, setOpen] = useState(false)
  const [turns, setTurns] = useState<Turn[]>([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.scoutStatus()
      .then((s) => { setAvailable(s.site_available); setTired(!s.visitor_available) })
      .catch(() => setAvailable(false))
  }, [])
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [turns, busy])

  async function ask(message: string) {
    if (!message.trim() || busy || tired) return
    const history: ChatTurn[] = turns.map(({ role, content }) => ({ role, content }))
    setTurns((t) => [...t, { role: 'user', content: message }])
    setText('')
    setBusy(true)
    try {
      const result = await api.scout(message, history)
      setTurns((t) => [...t, { role: 'assistant', content: result.reply, result }])
      if (!result.visitor_available || !result.site_available) setTired(true)
    } catch (err) {
      const reason = err instanceof ApiError ? err.message : ''
      if (reason === 'site_limit' || reason === 'visitor_limit') setTired(true)
      else setTurns((t) => [...t, { role: 'assistant', content: HICCUP, note: true }])
    } finally {
      setBusy(false)
    }
  }

  const submit = (e: FormEvent) => { e.preventDefault(); ask(text) }

  if (!available) return null

  if (!open) {
    return (
      <button className="scout-fab" onClick={() => setOpen(true)}>
        <span className="scout-spark">✦</span> Ask Scout
      </button>
    )
  }

  return (
    <aside className="scout-panel">
      <header className="scout-head">
        <div>
          <strong>Scout</strong>
          <span className="muted small"> · quick search helper</span>
        </div>
        <button className="icon-btn" onClick={() => setOpen(false)} aria-label="Close">✕</button>
      </header>

      <div className="scout-body">
        {turns.length === 0 && !tired && (
          <div className="scout-empty">
            <p className="serif-lg">What are you looking for?</p>
            <p className="muted small">Scout searches Yale startups and the Tsai CITY opportunities board for you.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => <button key={s} className="chip" onClick={() => ask(s)}>{s}</button>)}
            </div>
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} className={`bubble-row ${t.role}`}>
            <div className={`bubble ${t.role}`}>{t.content}</div>
            {t.result && t.result.startups.length > 0 && (
              <div className="scout-cards">{t.result.startups.map((s) => <StartupCard key={s.id} s={s} compact />)}</div>
            )}
            {t.result && t.result.opportunities.length > 0 && (
              <div className="scout-cards">{t.result.opportunities.map((o) => <OpportunityCard key={o.id} o={o} compact />)}</div>
            )}
          </div>
        ))}
        {tired && <div className="bubble-row assistant"><div className="bubble assistant tired">{TIRED}</div></div>}
        {busy && <div className="bubble-row assistant"><div className="bubble assistant typing"><span /><span /><span /></div></div>}
        <div ref={endRef} />
      </div>

      {!tired && (
        <form className="scout-input" onSubmit={submit}>
          <input value={text} maxLength={300} onChange={(e) => setText(e.target.value)} placeholder="e.g. edtech startups from Yale College" autoFocus />
          <button className="btn btn-dark" disabled={busy || !text.trim()}>Send</button>
        </form>
      )}
    </aside>
  )
}
