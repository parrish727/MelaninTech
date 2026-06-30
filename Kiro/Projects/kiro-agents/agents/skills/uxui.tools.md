# UX/UI Agent Tools

Inherits: [shared.tools.md](shared.tools.md)

## Additional Capabilities

### Design Spec Injection
- Full Melanin Technologies design system injected into every prompt
- Color system, typography scale, spacing, component library

### Playwright Visual Audit
- Access to Playwright MCP service (http://playwright-mcp:9001)
- Takes screenshots of generated pages for visual verification
- Compares against design spec for consistency

### Volume Mounts (read-write)
- `/app/Projects` — general project access
- `/app/melanin-tech-website` — company website source
