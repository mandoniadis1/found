import { useState } from 'react'

// Shows the official Yale logo if a file is placed at frontend/public/yale-logo.svg (use is governed by Yale's
// trademark guidelines), otherwise a simple "Yale" wordmark in Yale Blue.
export function YaleMark() {
  const [hasLogo, setHasLogo] = useState(true)
  return (
    <div className="yale-mark" title="Built for the Yale community">
      {hasLogo ? (
        <img src="/yale-logo.svg" alt="Yale" onError={() => setHasLogo(false)} />
      ) : (
        <span className="yale-word">Yale</span>
      )}
      <span className="yale-sub">for Yale founders</span>
    </div>
  )
}
