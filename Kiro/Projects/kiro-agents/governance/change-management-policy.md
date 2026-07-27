# Change Management Policy — Melanin Technologies

## Purpose
All code changes across every project must follow this process. No exceptions. No direct pushes to main. This applies to all agents, all interactive sessions, and all automated tasks.

## Git Flow (Mandatory)

### 1. Branch
```
git checkout -b <type>/<scope>
```
Types: `feat`, `fix`, `chore`, `refactor`, `docs`, `perf`, `test`

Examples:
- `feat/perio-charting`
- `fix/patient-messages-cors`
- `chore/pgbouncer-setup`

### 2. Commit (Conventional Commits)
```
git add <specific files>
git commit -m "<type>(<scope>): <description>"
```
- Stage specific files, never `git add .` without reviewing
- Keep commits atomic — one logical change per commit
- Message must follow: `type(scope): description`

### 3. Push Branch
```
git push -u origin <branch-name>
```

### 4. Open Pull Request
```
gh pr create --title "<type>(<scope>): <description>" --body "<what changed, what was tested>"
```
- PR title: concise, under 70 chars
- PR body: summary of changes + what was verified

### 5. CI Runs Automatically
- Tests (pytest, npm audit, Trivy scan)
- Build (Docker images pushed to GHCR)
- All checks must pass before merge

### 6. Merge (Auto or Manual Approval)
- Auto-merge enabled for passing PRs on non-production projects
- Production projects (OrthoFlow, melanin-tech-website): require human approval
- Squash merge preferred for feature branches

### 7. Deploy (Automatic)
- GHCR images updated on merge to main
- Watchtower detects new images within 5 minutes
- Containers auto-restart with new code
- No manual Docker builds on the server

## What Is NEVER Allowed
- ❌ Direct push to main/master
- ❌ Force push (`git push --force`) on any branch
- ❌ Local `docker build` as a deployment method (bypasses CI)
- ❌ Manual container restart as a substitute for proper deployment
- ❌ Skipping CI by pushing directly to main
- ❌ Leaving changes uncommitted after implementation

## What Agents Must Do After Every Implementation
1. Verify the build passes locally (`vite build`, `pytest`, etc.)
2. Create a feature branch
3. Commit with conventional commit message
4. Push the branch
5. Open a PR via `gh pr create`
6. Confirm CI passes
7. Verify the deployment lands (check the live URL)

## What Interactive Sessions (Kiro CLI) Must Do
Same as above. Being in an interactive session with pktech_dev does NOT exempt from this process. The conversation may be live, but the code still goes through the pipeline.

## Emergency Hotfix Process
Only when production is down (P1 incident):
1. Branch from main: `git checkout -b hotfix/<description>`
2. Minimal fix only — no feature work
3. Push + PR with `[HOTFIX]` prefix
4. Can be self-approved by pktech_dev
5. Merge immediately, verify deployment

## Monitoring Deployment
After merge, verify:
- CI passes (check GitHub Actions)
- GHCR image updated (check package registry)
- Watchtower pulls new image (check container logs or force pull)
- Live URL reflects changes (test the feature end-to-end)
