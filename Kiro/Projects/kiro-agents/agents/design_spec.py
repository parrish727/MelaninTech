"""
Melanin Technologies — Design System & Specification
Loaded statically into agent prompts.
"""

DESIGN_SPEC = """
## Melanin Technologies Design System

### Colors
- Deep Navy #1E2E52 — primary dark backgrounds
- Blue #3D5A99 — section backgrounds, accents
- Blue Dark #2C4275 — nav scroll state, hover
- Gold #B5A84B — primary accent, CTAs
- Gold Light #D4C96A — stat numbers, hover
- Sage #6B9E78 — secondary accent, section tags
- Off White #F5F3EE — cream section backgrounds

### Typography
- Headings: Syne ExtraBold (800)
- Body: Inter Light/Regular (300–400)
- H1: clamp(3.5rem, 6.5rem), tracking -2.5px, line-height 1.02
- H2: clamp(2.2rem, 3rem), tracking -1px, max-width 520px
- Eyebrow tags: 0.68rem semibold, tracking 0.25em, uppercase

### Section Order & Backgrounds
1. Nav — transparent → #1E2E52/95 on scroll
2. Hero — #1E2E52, full viewport
3. Services — white
4. How We Work — #F5F3EE
5. Who We Are — #1E2E52
6. Stack — #3D5A99
7. Contact — white
8. Footer — #1E2E52

### Spacing
- Section padding: py-24 lg:py-32
- Container: max-w-[1200px] mx-auto px-8 lg:px-16

### Buttons
- Primary: bg-[#B5A84B] text-white hover:bg-[#6B9E78] px-8 py-4
- Dark: bg-[#1E2E52] text-white hover:bg-[#B5A84B] px-8 py-4
- All buttons: Inter semibold 0.8rem, include → or ↗ icon, transition 300ms

### Motion
- Section reveals: fade + slide up, 600ms, stagger 100-150ms
- Trigger: -100px from viewport (whileInView, once:true)
- Hover: scale 1.02 on buttons, x-translate 4px on ghost CTAs

### Hard Rules
- No heavy card borders — whitespace separates
- Alternating dark/light sections
- CTAs always include arrows (→ or ↗)
- One primary accent color: #B5A84B
- Fonts: Syne (headings) + Inter (body) only

### Tech Stack
- Next.js + TypeScript, Tailwind CSS, Framer Motion, Lucide React
"""
