# Deploy Agent Tools

Inherits: [shared.tools.md](shared.tools.md)

## Additional Capabilities

### Docker Socket Access
- Direct access to `/var/run/docker.sock`
- Can build images, start/stop/restart containers
- Uses Docker SDK for known services (no compose path issues)

### Shell Execution
- Can execute bash scripts generated in proposals
- Daemon-aware: detects long-running processes (uvicorn, gunicorn, dev servers) and uses `subprocess.Popen` instead of blocking `subprocess.run`
- Daemon processes log to `deploy.log` and return PID immediately

### Compose Management
- Access to `docker-compose.yml` (read-only mount)
- Can trigger `docker compose up -d --build <service>`
- Environment file access for variable interpolation

### Volume Mounts
- `/app/Projects` (ro) — source code access
- `/app/docker` (ro) — compose and nginx configs
- `/app/.env` (ro) — environment variables
- `/app/melanin-tech-website` (ro) — website source
- `/var/run/docker.sock` — container management
