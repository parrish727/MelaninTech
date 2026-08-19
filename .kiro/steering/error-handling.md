---
inclusion: fileMatch
fileMatchPattern: "**/*.py,**/*.ts,**/*.tsx"
description: "Error handling patterns and standards for Python and TypeScript services."
---

# Error Handling Standards

## Python (FastAPI)

### HTTP Exceptions
```python
from fastapi import HTTPException, status

# Use specific status codes with descriptive messages
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail=f"Invoice {invoice_id} not found for practice {practice_id}",
)

raise HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Access denied: practice scope mismatch",
)

raise HTTPException(
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    detail="File must be PDF, PNG, or JPEG",
)
```

### Exception Handlers
```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log full traceback internally
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}")
    # Return safe message to client (no internal details)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Contact support if this persists."},
    )
```

### Structured Logging
```python
import structlog

logger = structlog.get_logger()

# Always include context
logger.error(
    "invoice_processing_failed",
    invoice_id=invoice_id,
    practice_id=practice_id,
    error_type=type(exc).__name__,
    # Never log: patient names, SSNs, raw file contents
)
```

### Try/Except Patterns
```python
# DO: Catch specific exceptions
try:
    result = await db.execute(query)
except IntegrityError as e:
    raise HTTPException(status_code=409, detail="Duplicate entry")
except OperationalError as e:
    logger.error("database_connection_failed", error=str(e))
    raise HTTPException(status_code=503, detail="Database unavailable")

# DON'T: Bare except or catch Exception blindly
# DON'T: Silently swallow errors (except pass)
```

## TypeScript (React)

### Error Boundaries
```typescript
// Every page/route should have an error boundary
<ErrorBoundary fallback={<ErrorFallback />}>
  <InvoiceDashboard />
</ErrorBoundary>
```

### API Error Handling
```typescript
// Consistent error response handling
async function fetchInvoices(practiceId: number): Promise<Invoice[]> {
  const response = await fetch(`/api/invoices?practice=${practiceId}`);
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "Unknown error" }));
    throw new ApiError(response.status, error.detail);
  }
  
  return response.json();
}
```

### User-Facing Errors
```typescript
// Always show user-friendly messages
// Never expose stack traces or internal details
// Provide actionable guidance when possible

const errorMessages: Record<number, string> = {
  401: "Your session has expired. Please log in again.",
  403: "You don't have permission to view this resource.",
  404: "The requested item was not found.",
  429: "Too many requests. Please wait a moment.",
  500: "Something went wrong. Please try again or contact support.",
};
```

## Common Anti-Patterns (Don't Do This)

- ❌ `except: pass` (swallowing errors)
- ❌ `catch (e) { console.log(e) }` (log and continue silently)
- ❌ Returning 200 with error in body
- ❌ Exposing stack traces to end users
- ❌ Logging PII in error messages
- ❌ Retry loops without backoff or max attempts
- ❌ Generic "Something went wrong" without logging specifics internally
