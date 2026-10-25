import { useEffect, useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { ResendButton } from './ResendButton'
import type { SiteConfig } from '../types'

// Reminds logged-in members to click the link sent to their Yale address.
export function VerifyBanner() {
  const { user } = useAuth()
  const [config, setConfig] = useState<SiteConfig | null>(null)

  useEffect(() => { api.config().then(setConfig).catch(() => {}) }, [])

  if (!user || user.email_verified) return null
  return (
    <div className="verify-banner">
      <span>
        <strong>Verify your Yale email.</strong> We sent a link to {user.email}. Until then you can browse, but not message,
        RSVP or claim a startup.
        {config?.mail_mode === 'outbox' && config.dev_mode && (
          <em className="dev-hint"> Local mode: emails aren't sent. <a href="/api/dev/email" target="_blank" rel="noreferrer">Open your email ↗</a></em>
        )}
      </span>
      <ResendButton email={user.email} className="btn btn-ghost sm" />
    </div>
  )
}
