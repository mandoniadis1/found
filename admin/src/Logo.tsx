import { useId } from 'react'

// The found. wordmark with a hand-drawn circle over it, like someone circled it with a pen.
// The loop overshoots where it started and has a slightly rough edge (SVG displacement filter).
export function CircleMark({ className = 'logo-circle' }: { className?: string }) {
  const id = useId().replace(/:/g, '')
  return (
    <svg className={className} viewBox="0 0 120 52" preserveAspectRatio="none" aria-hidden>
      <defs>
        <filter id={`rough-${id}`} x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="2" seed="7" />
          <feDisplacementMap in="SourceGraphic" scale="1.8" />
        </filter>
      </defs>
      <path
        d="M97 9 C 78 1.5, 33 2, 14 12 C 1 19.5, 3 37, 27 44.5 C 55 52, 103 47, 114.5 31 C 121 21, 109 8.5, 85 6.5 C 71 5.5, 60 7, 49 9.5"
        fill="none" stroke="currentColor" strokeWidth="2.3" strokeLinecap="round" strokeLinejoin="round"
        filter={`url(#rough-${id})`} opacity="0.85"
      />
    </svg>
  )
}

export function Logo() {
  return (
    <span className="logo-mark">
      found<span className="logo-dot">.</span>
      <CircleMark />
    </span>
  )
}
