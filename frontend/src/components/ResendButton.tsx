import { useState } from 'react'
import { api } from '../api'

// "Resend link" with visible feedback: Sending… → Sent ✓ (or the error), so a click never looks ignored.
export function ResendButton({ email, className = 'btn btn-ghost' }: { email: string; className?: string }) {
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle')
  const [error, setError] = useState('')

  async function resend() {
    setState('sending')
    setError('')
    try {
      await api.resendVerification()
      setState('sent')
    } catch (err) {
      setError((err as Error).message)
      setState('error')
    }
  }

  return (
    <span className="resend">
      <button className={className} disabled={state === 'sending'} onClick={resend}>
        {state === 'sending' ? 'Sending…' : state === 'sent' ? 'Send again' : 'Resend link'}
      </button>
      {state === 'sent' && <span className="resend-ok">Sent ✓ Check {email} (and your spam folder).</span>}
      {state === 'error' && <span className="resend-err">{error}</span>}
    </span>
  )
}
