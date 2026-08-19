---
inclusion: fileMatch
fileMatchPattern: "**/governance/**,**/auth*,**/security*,**/.env*,**/secrets*,**/fail2ban*"
description: "Security standards covering authentication, authorization, secrets management, and compliance."
---

# Security Standards

## Authentication Architecture

### OrthoFlow (Multi-Tenant SaaS)
```
User → Login (email + password) → JWT issued (practice_id in claims)
      → MFA required for admin (SMS OTP)
      → Every API call validates JWT + checks practice_id scope
      → Audit log entry for every data access
```

### HUD (Internal)
```
User → Login (password) → TOTP 2FA verification → Session established
      → Session timeout: 8 hours
      → Single admin user (pktech_dev)
```

### Agent System
```
Slack message → Signing secret verification → Bot token auth → Orchestrator routes
```

## Secure Coding Patterns

### Input Validation
```python
# Always validate at the API boundary with Pydantic
class InvoiceCreate(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., gt=0, le=1_000_000)
    file_type: Literal["pdf", "png", "jpeg"]
    
    @field_validator("vendor_name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        # Strip control characters
        return "".join(c for c in v if c.isprintable())
```

### SQL Injection Prevention
```python
# ALWAYS parameterized queries
result = await db.execute(
    select(Invoice).where(Invoice.practice_id == practice_id)
)

# NEVER string interpolation
# ❌ f"SELECT * FROM invoices WHERE practice_id = {practice_id}"
```

### File Upload Security
```python
# ClamAV scan before processing
scan_result = await clam_client.scan(file_bytes)
if scan_result.infected:
    raise HTTPException(status_code=400, detail="File rejected by security scan")

# Validate file type by magic bytes, not extension
# Limit file size (10MB max)
# Store in MinIO, never local filesystem
```

### JWT Security
```python
# Short-lived tokens (1 hour)
# Practice-scoped claims (data isolation)
# Refresh token rotation
# Blacklist on logout

payload = {
    "sub": str(user.id),
    "practice_id": user.practice_id,
    "role": user.role,
    "exp": datetime.utcnow() + timedelta(hours=1),
}
```

## Container Security

### Build-Time
- Multi-stage builds (no build tools in runtime image)
- Pin base image versions (no `:latest`)
- Run as non-root user
- No secrets in build args or layers
- Minimal packages (no shells in production images when possible)

### Runtime
- Read-only filesystem where applicable
- No privileged mode
- Drop all capabilities, add back only what's needed
- Resource limits (memory + CPU) in docker-compose.yml
- Health checks for all services
- No exposed ports except through nginx

## Secrets Management

### DO
- Store in `.env` file (gitignored)
- Use environment variable interpolation in docker-compose.yml
- Rotate on suspected exposure
- Use separate credentials per environment
- Reference by name in documentation

### DON'T
- Commit secrets to git (even in private repos)
- Log secret values
- Pass secrets as command-line arguments (visible in ps)
- Share secrets between production and development
- Hardcode in Dockerfiles or source code

## Network Security

### External-Facing
- nginx is the ONLY externally accessible service
- Cloudflare proxy (orange cloud) hides origin IP
- Rate limiting: 10 req/s per IP, burst 20
- fail2ban: bans after 5 failed attempts

### Internal
- All inter-service communication on Docker bridge network
- No service exposes ports to host except nginx (80/443)
- K8s NetworkPolicy for client namespace isolation
