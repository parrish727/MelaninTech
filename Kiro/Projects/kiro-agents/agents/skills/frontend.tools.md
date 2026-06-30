# Frontend Agent Tools

Inherits: [shared.tools.md](shared.tools.md)

## Additional Capabilities

### Design Spec Injection
- Full Melanin Technologies design system injected into every prompt
- Colors, typography, spacing, component patterns pre-loaded
- Ensures visual consistency across all generated UI

### Volume Mounts (read-write)
- `/app/Projects` — general project access
- `/app/melanin-tech-website` — company website (Next.js 16 + Tailwind + Framer Motion)
- `/app/orthoflow-frontend` — OrthoFlow React frontend

### Framework Knowledge
- Next.js App Router (melanin-tech-website)
- React + Vite + React Router (OrthoFlow)
- Tailwind CSS for all styling
- Framer Motion for animations
- Lucide React for icons
