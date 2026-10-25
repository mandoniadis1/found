// Admin console API client: only /api/admin/* routes, using the separate admin session cookie.

export type Admin = { id: number; first_name: string; last_name: string; email: string }

export type Overview = {
  pending_claims: number
  pending_startups: number
  members: number
  verified_members: number
  linkedin_members: number
  moderators: number
  listed_startups: number
  claimed_startups: number
  corrected_startups: number
  upcoming_events: number
  scout_tokens_today: number
  scout_questions_today: number
  scout_daily_budget: number
  mail_mode: string
  linkedin_configured: boolean
}

export type Claim = {
  id: number
  startup_id: number
  startup_name: string
  method: 'company_email' | 'manual_review'
  status: 'email_sent' | 'pending' | 'approved' | 'denied'
  full_name: string | null
  role: string | null
  work_email: string | null
  linkedin_profile_url: string | null
  evidence_url: string | null
  note: string | null
  admin_note: string | null
  created_at: string
  decided_at: string | null
  requester_name: string | null
  requester_email: string | null
  requester_linkedin_name: string | null
  requester_linkedin_email: string | null
  requester_linkedin_dev_standin: boolean
}

export type Startup = {
  id: number
  name: string
  tagline: string
  industries: string[]
  affiliations: string[]
  stage: string
  website: string | null
  source: string
  status: 'listed' | 'pending' | 'rejected'
  claimed: boolean
  founder_verified_via: string | null
  correction_note: string | null
  founder: { first_name: string; last_name: string; linkedin_verified: boolean } | null
}

export type Member = {
  id: number
  first_name: string
  last_name: string
  email: string
  school: string | null
  email_verified: number
  linkedin: number
  linkedin_name: string | null
  linkedin_dev_standin: number
  is_moderator: number
  is_test_account: number
  created_at: string
  startups: number
}

export type AuditReport = {
  verdict: 'accurate' | 'needs_changes' | 'unclear'
  suggested_tagline: string | null
  suggested_industries: string[]
  evidence: { quote: string; supports: string }[]
  summary: string
}

export type Audit = {
  id: number
  startup_id: number
  verdict: AuditReport['verdict']
  status: 'proposed' | 'applied' | 'dismissed' | 'info'
  created_at: string
  decided_at: string | null
  result: {
    name: string
    website: string | null
    current_tagline: string
    current_industries: string[]
    report: AuditReport
    dropped_quotes: number
    flagged_lines: string[]
    pages_read: string[]
    input_tokens: number
    cached_tokens: number
    output_tokens: number
    cost_usd: number
    stop_reason: string
  }
}

export type UsageDay = { day: string; tokens: number; messages: number }

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api/admin${path}`, {
    credentials: 'include',
    ...init,
    headers: init.body ? { 'Content-Type': 'application/json' } : undefined,
  })
  if (!res.ok) {
    let msg = res.statusText
    try { msg = (await res.json()).detail ?? msg } catch { /* not JSON */ }
    throw new ApiError(res.status, typeof msg === 'string' ? msg : 'Request failed')
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

const post = <T>(path: string, body: unknown = {}) => request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  me: () => request<Admin>('/me'),
  login: (email: string, password: string) => post<Admin>('/login', { email, password }),
  logout: () => post<void>('/logout'),
  overview: () => request<Overview>('/overview'),
  claims: (status: string) => request<Claim[]>(`/claims?status=${status}`),
  decideClaim: (id: number, decision: 'approve' | 'deny', admin_note: string) => post<Claim>(`/claims/${id}/${decision}`, { admin_note }),
  pendingStartups: () => request<Startup[]>('/startups'),
  decideStartup: (id: number, decision: 'approve' | 'reject') => post<Startup>(`/startups/${id}/${decision}`),
  allStartups: (q: string) => request<Startup[]>(`/startups/all${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  members: () => request<Member[]>('/members'),
  audit: (startupId: number) => post<Audit>(`/startups/${startupId}/audit`),
  audits: () => request<Audit[]>('/audits'),
  decideAudit: (id: number, decision: 'apply' | 'dismiss') => post<Audit>(`/audits/${id}/${decision}`),
  usage: () => request<UsageDay[]>('/scout-usage'),
}

// Links into the public site: same origin when served by the backend, port 5185 when using the Vite dev servers.
export const PUBLIC_SITE = window.location.port === '5186'
  ? `${window.location.protocol}//${window.location.hostname}:5185`
  : window.location.origin
