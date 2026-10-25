export function money(usd: number): string {
  if (!usd) return '$0'
  if (usd >= 1_000_000) return `$${(usd / 1_000_000).toFixed(usd % 1_000_000 === 0 ? 0 : 1)}M`
  if (usd >= 1_000) return `$${Math.round(usd / 1_000)}K`
  return `$${usd}`
}

export function initials(name: string): string {
  return name.split(/\s+/).map((w) => w[0]).join('').slice(0, 2).toUpperCase()
}

// A quiet, consistent tone per industry (used for monogram tiles). No rainbow: muted earth tones only.
const TONES: Record<string, string> = {
  Technology: '#2f3b4a',
  'Health & Biotech': '#6b3f3f',
  'Climate & Sustainability': '#3d4f3a',
  Consumer: '#7a4a33',
  Education: '#5a4a6b',
  Fintech: '#2e4a48',
  'Social Impact': '#4a4a3a',
  'Media & Entertainment': '#5b3a4a',
  'Real Estate': '#4f4536',
  Robotics: '#3a4450',
  Marketing: '#6a5536',
  Logistics: '#3f3a36',
}
export const sectorTone = (sector: string) => TONES[sector] ?? '#3a3733'

// Pitchbook stages, shortened for small tags.
export const shortStage = (stage: string) => stage.replace('Launched: ', '')

export function deadlineLabel(iso: string | null, rolling: boolean): { text: string; soon: boolean } {
  if (!iso) return { text: rolling ? 'Rolling admissions' : 'No deadline listed', soon: false }
  const d = new Date(iso + 'T23:59:00')
  const days = Math.ceil((d.getTime() - Date.now()) / 86_400_000)
  const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: d.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined })
  if (days <= 0) return { text: `Due today · ${date}`, soon: true }
  if (days <= 14) return { text: `Due in ${days} day${days === 1 ? '' : 's'} · ${date}`, soon: true }
  return { text: `Due ${date}`, soon: false }
}

export const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export function eventDate(iso: string) {
  const d = new Date(iso)
  return {
    month: d.toLocaleString('en-US', { month: 'short' }).toUpperCase(),
    day: d.getDate(),
    weekday: d.toLocaleString('en-US', { weekday: 'long' }),
    time: d.toLocaleString('en-US', { hour: 'numeric', minute: '2-digit' }),
  }
}

export function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'now'
  if (s < 3600) return `${Math.floor(s / 60)}m`
  if (s < 86400) return `${Math.floor(s / 3600)}h`
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}
