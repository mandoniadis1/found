// Mirrors backend/models.py

export type User = {
  id: number
  first_name: string
  last_name: string
  email: string
  school: string | null
  headline: string | null
  email_verified: boolean
  linkedin_url: string | null
  is_moderator: boolean
  is_admin: boolean
}

export type PublicUser = {
  id: number
  first_name: string
  last_name: string
  school: string | null
  headline: string | null
  linkedin_url: string | null
}

export type Startup = {
  id: number
  name: string
  tagline: string
  description: string | null
  industries: string[]
  affiliations: string[]
  stage: string
  website: string | null
  looking_for: string | null
  founders_public: string | null
  round: string | null
  raised_usd: number | null
  team_size: number | null
  location: string | null
  founded_year: number | null
  hiring: boolean
  source: 'yale_pitchbook' | 'member'
  correction_note: string | null
  status: 'listed' | 'pending' | 'rejected'
  claimed: boolean
  founder_verified_via: 'company_email' | 'admin_review' | null
  founder: PublicUser | null
}

export type StartupInput = Omit<Startup, 'id' | 'founder' | 'founders_public' | 'source' | 'claimed' | 'status' | 'founder_verified_via' | 'correction_note'> & {
  correction_reason?: string
}

export type FilterOption = { value: string; count: number }

export type Filters = {
  industries: FilterOption[]
  stages: FilterOption[]
  affiliations: FilterOption[]
  rounds: FilterOption[]
  locations: FilterOption[]
  with_team_size: number
  with_funding: number
  total: number
}

export type Options = {
  industries: string[]
  stages: string[]
  affiliations: string[]
  rounds: string[]
  opportunity_categories: Record<string, string>
}

export type Opportunity = {
  id: number
  category: string
  category_label: string
  title: string
  org: string | null
  description: string | null
  website: string | null
  location: string | null
  ideal_candidate: string | null
  apply_url: string | null
  apply_email: string | null
  deadline: string | null
  rolling: boolean
  start_date: string | null
  grand_prize: string | null
  curator_note: string | null
  posted_at: string | null
}

export type ExpectedDeadline = {
  id: number
  name: string
  category: string
  organizer: string | null
  website: string | null
  expected_window: string | null
  expected_month: number | null
  expected_year: number | null
  eligibility_note: string | null
}

export type FoundEvent = {
  id: number
  title: string
  description: string
  kind: 'startup' | 'sector'
  sector: string | null
  host_startup: string | null
  host_startup_id: number | null
  organizer: PublicUser
  starts_at: string
  location: string
  capacity: number
  attending: number
  i_am_going: boolean
}

export type EventInput = {
  title: string
  description: string
  kind: 'startup' | 'sector'
  sector: string | null
  host_startup_id: number | null
  starts_at: string
  location: string
  capacity: number
}

export type Conversation = {
  id: number
  other: PublicUser
  last_message: string | null
  last_at: string | null
}

export type Message = { id: number; sender_id: number; body: string; created_at: string }

export type ChatTurn = { role: 'user' | 'assistant'; content: string }

export type ScoutOut = {
  reply: string
  startups: Startup[]
  events: FoundEvent[]
  opportunities: Opportunity[]
  tools_used: string[]
  site_available: boolean
  visitor_available: boolean
}

export type SiteConfig = { dev_mode: boolean; mail_mode: string }

export type ClaimOptions = { company_domain: string | null; has_pending_request: boolean }

export type ClaimRequest = {
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
  requester_linkedin_url: string | null
}

export type ManualClaimInput = {
  full_name: string
  role: string
  work_email: string
  linkedin_profile_url: string
  evidence_url: string
  note: string
}
