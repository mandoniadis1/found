import { useEffect, useState, type FormEvent } from 'react'
import { api } from '../api'
import type { Options, Startup, StartupInput } from '../types'

const EMPTY: StartupInput = {
  name: '', tagline: '', description: '', industries: [], affiliations: [], stage: 'Building', website: '',
  looking_for: '', round: null, raised_usd: null, team_size: null, location: '', founded_year: null, hiring: false,
}

function MultiPick({ label, options, value, onChange, max = 4 }: {
  label: string
  options: string[]
  value: string[]
  onChange: (v: string[]) => void
  max?: number
}) {
  const toggle = (o: string) =>
    onChange(value.includes(o) ? value.filter((x) => x !== o) : value.length < max ? [...value, o] : value)
  return (
    <div className="multipick">
      <span className="field-label">{label} <span className="muted">(up to {max})</span></span>
      <div className="pick-chips">
        {options.map((o) => (
          <button type="button" key={o} className={`pick${value.includes(o) ? ' on' : ''}`} onClick={() => toggle(o)}>{o}</button>
        ))}
      </div>
    </div>
  )
}

const num = (v: string) => (v === '' ? null : Number(v))

export function StartupForm({ initial, onSaved, asAdmin = false }: { initial?: Startup; onSaved: (s: Startup) => void; asAdmin?: boolean }) {
  const [form, setForm] = useState<StartupInput>(initial ? { ...EMPTY, ...initial, correction_reason: initial.correction_note ?? '' } : EMPTY)
  const [opts, setOpts] = useState<Options | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => { api.options().then(setOpts) }, [])

  const set = <K extends keyof StartupInput>(k: K, v: StartupInput[K]) => setForm((f) => ({ ...f, [k]: v }))

  async function submit(e: FormEvent) {
    e.preventDefault()
    if (form.industries.length === 0 || form.affiliations.length === 0) return setError('Pick at least one industry and one Yale affiliation.')
    setBusy(true)
    setError('')
    try {
      onSaved(initial ? await api.updateStartup(initial.id, form) : await api.createStartup(form))
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!opts) return <p className="muted">Loading…</p>

  return (
    <form className="form" onSubmit={submit}>
      <div className="row2">
        <label>Name<input required value={form.name} onChange={(e) => set('name', e.target.value)} /></label>
        <label>Website<input value={form.website ?? ''} placeholder="https://" onChange={(e) => set('website', e.target.value)} /></label>
      </div>
      <label>One-line pitch<input required maxLength={400} value={form.tagline} onChange={(e) => set('tagline', e.target.value)} /></label>
      <label>About <span className="muted">(optional)</span><textarea rows={3} value={form.description ?? ''} onChange={(e) => set('description', e.target.value)} /></label>
      <MultiPick label="Industries" options={opts.industries} value={form.industries} onChange={(v) => set('industries', v)} />
      <MultiPick label="Yale affiliation" options={opts.affiliations} value={form.affiliations} onChange={(v) => set('affiliations', v)} />
      <div className="row3">
        <label>Stage
          <select value={form.stage} onChange={(e) => set('stage', e.target.value)}>
            {opts.stages.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label>Round
          <select value={form.round ?? ''} onChange={(e) => set('round', e.target.value || null)}>
            <option value="">Not shared</option>
            {opts.rounds.map((s) => <option key={s}>{s}</option>)}
          </select>
        </label>
        <label>Raised (USD)<input type="number" min={0} step={1000} placeholder="Not shared" value={form.raised_usd ?? ''} onChange={(e) => set('raised_usd', num(e.target.value))} /></label>
      </div>
      <div className="row3">
        <label>Team size<input type="number" min={1} placeholder="—" value={form.team_size ?? ''} onChange={(e) => set('team_size', num(e.target.value))} /></label>
        <label>Location<input placeholder="e.g. New Haven, CT" value={form.location ?? ''} onChange={(e) => set('location', e.target.value)} /></label>
        <label>Founded<input type="number" min={1950} max={2100} placeholder="—" value={form.founded_year ?? ''} onChange={(e) => set('founded_year', num(e.target.value))} /></label>
      </div>
      <label>Looking for <span className="muted">(optional: co-founder, interns, pilots, investors…)</span>
        <textarea rows={2} value={form.looking_for ?? ''} onChange={(e) => set('looking_for', e.target.value)} />
      </label>
      <label className="check"><input type="checkbox" checked={form.hiring} onChange={(e) => set('hiring', e.target.checked)} /> We're hiring</label>
      {asAdmin && initial?.source === 'yale_pitchbook' && (
        <label>What was wrong? <span className="muted">(admin correction, shown on the listing and saved to corrections.json)</span>
          <textarea required rows={2} value={form.correction_reason ?? ''} onChange={(e) => set('correction_reason', e.target.value)}
            placeholder="e.g. Listed as healthcare; it's a real estate investment firm (per its website)." />
        </label>
      )}
      {error && <p className="error">{error}</p>}
      <button className="btn btn-dark" disabled={busy}>{initial ? 'Save changes' : 'Add startup'}</button>
    </form>
  )
}
