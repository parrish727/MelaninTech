# Scaffold Agent Tools

Inherits: [shared.tools.md](shared.tools.md)

## Additional Capabilities

### Volume Mounts (read-write)
- `/app/Projects` — creates new project directories here

### Project Bootstrapping
- Generates full project structure (directories, configs, boilerplate)
- Supported stacks: Next.js, FastAPI, React+Vite, Python CLI
- Creates package.json/requirements.txt with pinned dependencies
- Initializes git repo with .gitignore
- Sets up Docker/Compose files for the new project
