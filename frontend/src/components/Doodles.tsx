// White outline stencils that decorate the cream background (same idea as the Campus Customs Handsome Dan doodles).
// Purely decorative: fixed behind the page, ignored by screen readers and the mouse.

type P = { size?: number }
const svg = (size: number, children: React.ReactNode, viewBox = '0 0 120 120') => (
  <svg width={size} height={size} viewBox={viewBox} fill="none" stroke="#fff" strokeWidth={3.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    {children}
  </svg>
)

// Handsome Dan, Yale's bulldog
const Dan = ({ size = 130 }: P) => svg(size, <>
  <path d="M26 36 C12 22 16 10 34 22" /><path d="M94 36 C108 22 104 10 86 22" />
  <path d="M22 50 C20 24 100 24 98 50 C108 62 104 86 86 94 C72 102 48 102 34 94 C16 86 12 62 22 50 Z" />
  <path d="M38 42 q6 -5 12 0" /><path d="M70 42 q6 -5 12 0" /><path d="M54 34 q6 -3 12 0" />
  <circle cx="44" cy="53" r="3.5" fill="#fff" /><circle cx="76" cy="53" r="3.5" fill="#fff" />
  <path d="M51 64 q9 -7 18 0 q-9 9 -18 0 Z" fill="#fff" /><path d="M60 71 v7" />
  <path d="M60 78 C52 87 40 85 35 76" /><path d="M60 78 C68 87 80 85 85 76" />
  <path d="M48 85 l3 -5 l3 5" /><path d="M66 85 l3 -5 l3 5" />
  <path d="M34 100 C46 110 74 110 86 100" /><path d="M54 104 l6 6 l6 -6 M60 110 v6" />
</>)

const Bulb = ({ size = 90 }: P) => svg(size, <>
  <path d="M60 18 C38 18 26 34 26 50 C26 64 36 72 42 80 C45 84 46 88 46 92 H74 C74 88 75 84 78 80 C84 72 94 64 94 50 C94 34 82 18 60 18 Z" />
  <path d="M48 100 H72" /><path d="M51 108 H69" />
  <path d="M52 92 C52 76 56 66 60 58 C64 66 68 76 68 92" />
  <path d="M60 4 v6 M22 14 l5 5 M98 14 l-5 5 M10 50 h7 M103 50 h7" />
</>)

const Rocket = ({ size = 100 }: P) => svg(size, <>
  <path d="M60 10 C80 26 86 52 78 80 H42 C34 52 40 26 60 10 Z" />
  <circle cx="60" cy="44" r="9" />
  <path d="M42 64 L26 82 L42 80" /><path d="M78 64 L94 82 L78 80" />
  <path d="M50 88 C50 98 56 104 60 112 C64 104 70 98 70 88" />
</>)

const Mug = ({ size = 86 }: P) => svg(size, <>
  <path d="M24 44 H84 V86 C84 98 76 106 64 106 H44 C32 106 24 98 24 86 Z" />
  <path d="M84 54 C100 54 104 82 84 84" />
  <path d="M42 34 C36 26 48 22 42 12" /><path d="M58 34 C52 26 64 22 58 12" /><path d="M74 34 C68 26 80 22 74 12" />
</>)

const Plane = ({ size = 96 }: P) => svg(size, <>
  <path d="M10 56 L108 16 L80 102 L58 72 Z" /><path d="M58 72 L108 16" /><path d="M58 72 L56 96 L70 84" />
  <path d="M6 92 C20 86 26 98 40 92" strokeDasharray="2 8" />
</>)

const Chart = ({ size = 92 }: P) => svg(size, <>
  <path d="M14 14 V106 H108" />
  <path d="M24 88 L48 62 L66 74 L100 32" /><path d="M84 32 H100 V48" />
</>)

const Sparkle = ({ size = 40 }: P) => svg(size, <path d="M60 10 C64 44 76 56 110 60 C76 64 64 76 60 110 C56 76 44 64 10 60 C44 56 56 44 60 10 Z" />)

export function Doodles() {
  return (
    <div className="doodles" aria-hidden>
      <span className="doodle d1"><Dan size={150} /></span>
      <span className="doodle d2"><Bulb /></span>
      <span className="doodle d3"><Rocket /></span>
      <span className="doodle d4"><Mug /></span>
      <span className="doodle d5"><Plane /></span>
      <span className="doodle d6"><Chart /></span>
      <span className="doodle d7"><Sparkle size={46} /></span>
      <span className="doodle d8"><Sparkle size={30} /></span>
      <span className="doodle d9"><Dan size={92} /></span>
    </div>
  )
}
