import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import type { ClaimOptions, ManualClaimInput, Startup } from '../types'
import { Modal } from './Modal'

type Step = 'choose' | 'email_sent' | 'manual' | 'manual_sent'

export function ClaimModal({ s, onClose }: { s: Startup; onClose: () => void }) {
  const { user } = useAuth()
  const [opts, setOpts] = useState<ClaimOptions | null>(null)
  const [step, setStep] = useState<Step>('choose')
  const [workEmail, setWorkEmail] = useState('')
  const [sentTo, setSentTo] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState<ManualClaimInput>({
    full_name: user ? `${user.first_name} ${user.last_name}` : '', role: '', work_email: '',
    linkedin_profile_url: user?.linkedin_url ?? '', evidence_url: '', note: '',
  })

  useEffect(() => { api.claimOptions(s.id).then(setOpts).catch((e) => setError(e.message)) }, [s.id])

  const ready = user?.email_verified

  async function run(fn: () => Promise<void>) {
    setBusy(true)
    setError('')
    try { await fn() } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
  }

  const sendEmail = (e: FormEvent) => {
    e.preventDefault()
    run(async () => { setSentTo((await api.claimByCompanyEmail(s.id, workEmail)).sent_to); setStep('email_sent') })
  }
  const sendManual = (e: FormEvent) => {
    e.preventDefault()
    run(async () => { await api.claimByManualReview(s.id, form); setStep('manual_sent') })
  }
  const set = (k: keyof ManualClaimInput, v: string) => setForm((f) => ({ ...f, [k]: v }))

  return (
    <Modal title={`Claim ${s.name}`} onClose={onClose}>
      {!ready ? (
        <div className="claim-steps">
          <p className="muted">To claim a startup, first verify your Yale email:</p>
          <ol className="checklist">
            <li className={user?.email_verified ? 'done' : ''}>Verify your Yale email</li>
          </ol>
          <Link to={user ? '/profile' : '/login'} className="btn btn-dark" onClick={onClose}>{user ? 'Go to your profile' : 'Log in'}</Link>
        </div>
      ) : step === 'choose' ? (
        <div className="claim-steps">
          {opts?.has_pending_request && <p className="note">You already have a claim in progress for this startup.</p>}
          {opts?.company_domain ? (
            <form className="claim-option" onSubmit={sendEmail}>
              <h4>Fastest: verify with your work email</h4>
              <p className="muted small">We'll email a link to your <strong>@{opts.company_domain}</strong> address. Clicking it confirms you work at {s.name}.</p>
              <div className="inline-form">
                <input required type="email" value={workEmail} onChange={(e) => setWorkEmail(e.target.value)} placeholder={`you@${opts.company_domain}`} />
                <button className="btn btn-dark" disabled={busy}>Send link</button>
              </div>
            </form>
          ) : opts && (
            <p className="muted small">{s.name}'s listed website isn't on its own domain, so we can't verify by work email.</p>
          )}
          <div className="claim-option alt">
            <h4>Unable to verify automatically?</h4>
            <p className="muted small">
              Send a request to the found. team. We'll check your LinkedIn profile and the details you give us, then approve
              or follow up. This usually takes a few days.
            </p>
            <button className="btn btn-ghost" onClick={() => setStep('manual')}>Request a manual review</button>
          </div>
          {error && <p className="error">{error}</p>}
        </div>
      ) : step === 'email_sent' ? (
        <div className="claim-steps">
          <p className="serif-lg">Check {sentTo}</p>
          <p className="muted">Click the link in that email to finish claiming {s.name}. It expires in 24 hours.</p>
          <p className="muted small"><a href={`/api/dev/email?to=${encodeURIComponent(sentTo)}`} target="_blank" rel="noreferrer">Local mode? Open the email here ↗</a></p>
          <button className="btn btn-dark" onClick={onClose}>Done</button>
        </div>
      ) : step === 'manual' ? (
        <form className="form" onSubmit={sendManual}>
          <p className="muted small">Only the found. team sees this. Tell us enough to confirm you're a founder of {s.name}.</p>
          <div className="row2">
            <label>Full name<input required minLength={2} value={form.full_name} onChange={(e) => set('full_name', e.target.value)} /></label>
            <label>Your role<input required minLength={2} placeholder="e.g. Co-founder & CEO" value={form.role} onChange={(e) => set('role', e.target.value)} /></label>
          </div>
          <label>Your LinkedIn profile URL<input required type="url" placeholder="https://www.linkedin.com/in/your-name" value={form.linkedin_profile_url} onChange={(e) => set('linkedin_profile_url', e.target.value)} /></label>
          <div className="row2">
            <label>Work email <span className="muted">(optional)</span><input type="email" value={form.work_email} onChange={(e) => set('work_email', e.target.value)} /></label>
            <label>Proof link <span className="muted">(optional)</span><input type="url" placeholder="Team page, press, Crunchbase…" value={form.evidence_url} onChange={(e) => set('evidence_url', e.target.value)} /></label>
          </div>
          <label>Note to the reviewer<textarea required minLength={10} rows={4} placeholder="e.g. I co-founded the company in 2024. My LinkedIn doesn't list it yet because…" value={form.note} onChange={(e) => set('note', e.target.value)} /></label>
          {error && <p className="error">{error}</p>}
          <div className="opp-actions">
            <button type="button" className="btn btn-ghost" onClick={() => setStep('choose')}>Back</button>
            <button className="btn btn-dark" disabled={busy}>Send for review</button>
          </div>
        </form>
      ) : (
        <div className="claim-steps">
          <p className="serif-lg">Request sent</p>
          <p className="muted">The found. team will review it. You can see its status on your profile.</p>
          <button className="btn btn-dark" onClick={onClose}>Done</button>
        </div>
      )}
    </Modal>
  )
}
