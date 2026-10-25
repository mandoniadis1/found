import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { Options } from '../types'

// "Open to joining a startup": opt in to be found by founders, with what you'd bring.
export function JoinProfile() {
  const { user, setUser } = useAuth()
  const [opts, setOpts] = useState<Options | null>(null)
  const [open, setOpen] = useState(user?.open_to_join ?? false)
  const [roles, setRoles] = useState<string[]>(user?.join_roles ?? [])
  const [industries, setIndustries] = useState<string[]>(user?.join_industries ?? [])
  const [commitment, setCommitment] = useState(user?.join_commitment ?? '')
  const [pitch, setPitch] = useState(user?.join_pitch ?? '')
  const [msg, setMsg] = useState<{ text: string; error?: boolean } | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => { api.options().then(setOpts) }, [])
  if (!user || !opts) return null

  const toggle = (list: string[], set: (v: string[]) => void, v: string) =>
    set(list.includes(v) ? list.filter((x) => x !== v) : list.length < 4 ? [...list, v] : list)

  async function save() {
    setBusy(true)
    setMsg(null)
    try {
      setUser(await api.updateProfile({ open_to_join: open, join_roles: roles, join_industries: industries, join_commitment: commitment, join_pitch: pitch }))
      setMsg({ text: open ? 'Saved. Founders on found. can now find you.' : 'Saved. You are hidden from founders.' })
    } catch (err) {
      setMsg({ text: (err as Error).message, error: true })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel join-panel">
      <div className="panel-head">
        <h3>Open to joining a startup</h3>
        <label className="toggle tight inline">
          <input type="checkbox" checked={open} disabled={!user.email_verified} onChange={(e) => setOpen(e.target.checked)} />
          <span className="switch" /> {open ? 'Visible to founders' : 'Hidden'}
        </label>
      </div>
      <p className="muted small">
        No startup or idea yet? Turn this on and founders with a startup on found. can find you and message you. Only your name,
        school, headline, LinkedIn link and what you fill in below are shown; never your email. Also see the <Link to="/join">Join a startup</Link> page.
      </p>
      {!user.email_verified && <p className="muted tiny">Verify your Yale email first.</p>}
      <div className="multipick">
        <span className="field-label">Roles you'd take <span className="muted">(up to 4)</span></span>
        <div className="pick-chips">{opts.join_roles.map((r) => (
          <button type="button" key={r} className={`pick${roles.includes(r) ? ' on' : ''}`} onClick={() => toggle(roles, setRoles, r)}>{r}</button>
        ))}</div>
      </div>
      <div className="multipick">
        <span className="field-label">Industries you're excited about <span className="muted">(up to 4, optional)</span></span>
        <div className="pick-chips">{opts.industries.map((i) => (
          <button type="button" key={i} className={`pick${industries.includes(i) ? ' on' : ''}`} onClick={() => toggle(industries, setIndustries, i)}>{i}</button>
        ))}</div>
      </div>
      <div className="row2 form">
        <label>Time you can give
          <select value={commitment} onChange={(e) => setCommitment(e.target.value)}>
            <option value="">Choose…</option>
            {opts.join_commitments.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <label>One line about what you'd bring
          <input maxLength={200} value={pitch} onChange={(e) => setPitch(e.target.value)} placeholder="e.g. CS junior, built two iOS apps, want to work on climate" />
        </label>
      </div>
      <div className="join-save">
        <button className="btn btn-dark" disabled={busy} onClick={save}>{busy ? 'Saving…' : 'Save'}</button>
        {msg && <span className={msg.error ? 'error small' : 'resend-ok'}>{msg.text}</span>}
      </div>
    </section>
  )
}
