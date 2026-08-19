# Step: Generate Fix

Implement the recommended SEO improvement by dispatching to the frontend agent.

## Actions
1. Read the design system from `/app/melanin-tech-website/design-system.json`
2. Build a task for the frontend agent that includes:
   - The specific fix from the analysis step
   - Design system constraints (colors, fonts, components)
   - File paths to modify
3. Dispatch to the frontend agent
4. Evaluate the output quality (must pass structural checks)

## Constraints
- Must maintain existing design system tokens
- Must output proper code blocks with file paths
- Mobile-first responsive
- Tailwind CSS only
