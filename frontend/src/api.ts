import type {
  ChatTurn, ClaimOptions, JoinBoard, Joiner, ClaimRequest, Conversation, EventInput, ManualClaimInput, SiteConfig, ExpectedDeadline, Filters, FoundEvent, Message, Opportunity, Options, PublicUser,
  ScoutOut, Startup, StartupInput, User,
} from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    credentials: 'include',
    ...init,
    headers: init.body ? { 'Content-Type': 'application/json', ...init.headers } : init.headers,
  })
  if (!res.ok) {
    let msg = res.statusText
    try {
      const data = await res.json()
      msg = typeof data.detail === 'string' ? data.detail : (data.detail?.[0]?.msg ?? msg)
    } catch { /* not JSON */ }
    throw new ApiError(res.status, msg)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export type StartupQuery = {
  q?: string
  industry?: string[]
  stage?: string[]
  affiliation?: string[]
  round?: string[]
  location?: string[]
  team_min?: number
  team_max?: number
  raised_min?: number
  hiring?: boolean
  has_ask?: boolean
  sort?: string
}

export type OpportunityQuery = { q?: string; category?: string[]; within_days?: number; sort?: string }

function toParams(query: Record<string, unknown>): string {
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === '' || v === false) continue
    if (Array.isArray(v)) v.forEach((x) => p.append(k, x))
    else p.set(k, String(v))
  }
  return p.toString()
}

export const api = {
  config: () => request<SiteConfig>('/api/config'),
  me: () => request<User | null>('/api/me'),
  resendVerification: () => post<void>('/api/auth/resend-verification'),
  login: (email: string, password: string) => post<User>('/api/auth/login', { email, password }),
  signup: (body: { first_name: string; last_name: string; email: string; password: string; school?: string }) =>
    post<User>('/api/auth/signup', body),
  logout: () => post<void>('/api/auth/logout'),
  updateProfile: (body: { school?: string; headline?: string; linkedin_url?: string; open_to_join?: boolean;
    join_roles?: string[]; join_industries?: string[]; join_commitment?: string; join_pitch?: string }) =>
    request<User>('/api/me', { method: 'PATCH', body: JSON.stringify(body) }),
  becomeModerator: () => post<User>('/api/me/moderator'),

  filters: () => request<Filters>('/api/filters'),
  options: () => request<Options>('/api/options'),
  startups: (query: StartupQuery) => request<Startup[]>(`/api/startups?${toParams(query)}`),
  startup: (id: number) => request<Startup>(`/api/startups/${id}`),
  myStartups: () => request<Startup[]>('/api/startups/mine'),
  claimOptions: (id: number) => request<ClaimOptions>(`/api/startups/${id}/claim-options`),
  claimByCompanyEmail: (id: number, work_email: string) =>
    post<{ sent_to: string }>(`/api/startups/${id}/claim/company-email`, { work_email }),
  claimByManualReview: (id: number, body: ManualClaimInput) => post<ClaimRequest>(`/api/startups/${id}/claim/manual`, body),
  myClaims: () => request<ClaimRequest[]>('/api/claims/mine'),

  createStartup: (body: StartupInput) => post<Startup>('/api/startups', body),
  updateStartup: (id: number, body: StartupInput) =>
    request<Startup>(`/api/startups/${id}`, { method: 'PUT', body: JSON.stringify(body) }),

  opportunities: (query: OpportunityQuery) => request<Opportunity[]>(`/api/opportunities?${toParams(query)}`),
  opportunityCounts: () => request<Record<string, number>>('/api/opportunities/counts'),
  opportunity: (id: number) => request<Opportunity>(`/api/opportunities/${id}`),
  deadlines: () => request<ExpectedDeadline[]>('/api/deadlines'),

  joinBoard: () => request<JoinBoard>('/api/join'),
  peopleOpen: (q: { role?: string; industry?: string; commitment?: string }) =>
    request<Joiner[]>(`/api/people/open?${toParams(q)}`),

  events: () => request<FoundEvent[]>('/api/events'),
  createEvent: (body: EventInput) => post<FoundEvent>('/api/events', body),
  rsvp: (id: number) => post<FoundEvent>(`/api/events/${id}/rsvp`),

  member: (id: number) => request<PublicUser>(`/api/members/${id}`),
  conversations: () => request<Conversation[]>('/api/conversations'),
  startConversation: (user_id: number) => post<Conversation>('/api/conversations', { user_id }),
  messages: (cid: number) => request<Message[]>(`/api/conversations/${cid}/messages`),
  send: (cid: number, body: string) => post<Message>(`/api/conversations/${cid}/messages`, { body }),

  scoutStatus: () => request<{ site_available: boolean; visitor_available: boolean }>('/api/scout/status'),
  scout: (message: string, history: ChatTurn[]) => post<ScoutOut>('/api/scout', { message, history }),
}
