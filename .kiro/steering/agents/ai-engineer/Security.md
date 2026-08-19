---
inclusion: fileMatch
fileMatchPattern: "**/*.py,**/*.ts,**/*.tsx,**/auth*,**/security*,**/jwt*,**/middleware*"
description: "AI Engineering agent security rules for auth, JWT, and middleware patterns."
---

# AI Engineering Agent — Security

## Secure Coding Responsibilities

### Authentication Implementation
```python
# JWT with practice scoping — the standard pattern for OrthoFlow
from jose import jwt, JWTError
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate JWT and extract practice-scoped user."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id = int(payload["sub"])
        practice_id = int(payload["practice_id"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user = await db.get(User, user_id)
    if not user or user.practice_id != practice_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user
```

### Input Validation
```python
# ALWAYS validate at API boundary — never trust client input
class InvoiceCreate(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., gt=0, le=Decimal("1000000"))
    file_type: Literal["pdf", "png", "jpeg"] | None = None
    
    @field_validator("vendor_name")
    @classmethod
    def no_control_chars(cls, v: str) -> str:
        return "".join(c for c in v if c.isprintable())
```

### SQL Injection Prevention
```python
# ✅ ALWAYS: Parameterized queries
result = await db.execute(
    select(Invoice).where(
        Invoice.practice_id == user.practice_id,
        Invoice.status == status_filter,
    )
)

# ✅ ALWAYS: SQLAlchemy text() with bind params
result = await db.execute(
    text("SELECT * FROM invoices WHERE practice_id = :pid"),
    {"pid": user.practice_id},
)

# ❌ NEVER: String interpolation
# f"SELECT * FROM invoices WHERE practice_id = {practice_id}"
```

### File Upload Security
```python
import clamav

async def validate_upload(file: UploadFile) -> bytes:
    """Validate uploaded file: size, type, virus scan."""
    # Size limit
    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")
    
    # Magic byte validation (not just extension)
    mime = magic.from_buffer(contents, mime=True)
    if mime not in ALLOWED_MIMES:
        raise HTTPException(status_code=400, detail=f"File type {mime} not allowed")
    
    # ClamAV virus scan
    scan_result = await clam_client.scan(contents)
    if scan_result.infected:
        logger.warning("malware_detected", filename=file.filename, virus=scan_result.virus_name)
        raise HTTPException(status_code=400, detail="File rejected by security scan")
    
    return contents
```

### XSS Prevention (Frontend)
```typescript
// React auto-escapes by default — DON'T bypass it
// ❌ NEVER: dangerouslySetInnerHTML={{ __html: userInput }}
// ✅ ALWAYS: Render user content as text nodes

// Sanitize if HTML rendering is absolutely necessary
import DOMPurify from "dompurify";
const sanitized = DOMPurify.sanitize(userContent);
```

## HIPAA Compliance (OrthoFlow)

### Audit Logging Pattern
```python
async def audit_log(
    db: AsyncSession,
    user: User,
    action: str,
    resource_type: str,
    resource_id: int,
    details: str | None = None,
) -> None:
    """Log all PHI access for HIPAA compliance. NEVER skip this."""
    entry = AuditLog(
        user_id=user.id,
        practice_id=user.practice_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        ip_address=get_client_ip(),
        timestamp=datetime.utcnow(),
    )
    db.add(entry)
    await db.flush()  # Don't wait for commit — ensure audit log is persisted
```

### Data Access Rules
- All patient data queries MUST filter by `practice_id` from JWT
- Cross-practice queries are impossible by design (no admin endpoint for bulk patient data)
- Audit log every read and write to patient-related tables
- Error messages never include patient names, IDs, or medical information

## LLM Security

### Prompt Injection Defense
```python
def prepare_llm_input(user_text: str, system_context: str) -> list[dict]:
    """Structure LLM input to resist prompt injection."""
    return [
        {"role": "system", "content": system_context},
        {"role": "user", "content": f"<user_input>{user_text}</user_input>"},
    ]
    # The system prompt defines behavior; user input is clearly delimited
    # Never concatenate user input directly into system prompts
```

### Model Output Sanitization
```python
def sanitize_model_output(output: str) -> str:
    """Remove any PII that may have leaked into model output."""
    # Strip SSN patterns
    output = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED]", output)
    # Strip phone patterns
    output = re.sub(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "[REDACTED]", output)
    # Strip email addresses in sensitive contexts
    # (context-dependent — not always needed)
    return output
```

## Secret Handling in Code

### DO
```python
# Read from environment
import os
API_KEY = os.environ["ANTHROPIC_API_KEY"]

# Use settings object
from app.config import settings
client = AsyncClient(api_key=settings.ANTHROPIC_API_KEY)
```

### DON'T
```python
# ❌ Hardcoded
API_KEY = "sk-ant-..."

# ❌ In default parameter
def call_llm(key: str = "sk-ant-..."):

# ❌ In test fixtures committed to git
@pytest.fixture
def api_key():
    return "sk-ant-real-key-here"

# ❌ Logged
logger.info(f"Using key: {settings.ANTHROPIC_API_KEY}")
```
