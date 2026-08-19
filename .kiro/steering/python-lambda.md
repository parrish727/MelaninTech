---
inclusion: fileMatch
fileMatchPattern: "**/*.py,**/requirements*.txt,**/pyproject.toml,**/setup.cfg"
description: "Python project configuration, coding standards, and dependency management."
---

# Python Standards

## Project Configuration

### pyproject.toml (preferred)
```toml
[project]
name = "service-name"
version = "1.0.0"
requires-python = ">=3.11"

[tool.ruff]
target-version = "py311"
line-length = 100
select = ["E", "W", "F", "I", "UP", "B", "SIM"]

[tool.ruff.format]
quote-style = "double"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

## FastAPI Service Template

```python
"""Service entry point — FastAPI application."""
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle."""
    # Startup: initialize connections, load models
    yield
    # Shutdown: close connections, cleanup


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy"}
```

## Type Hints (Required)

```python
# Every function signature MUST have type hints
def calculate_fee(amount: Decimal, rate: float = 0.03) -> Decimal:
    ...

async def get_user(user_id: int, db: AsyncSession) -> User | None:
    ...

# Pydantic models for all request/response schemas
class CreateInvoiceRequest(BaseModel):
    vendor_name: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., gt=0)
    category: InvoiceCategory
    
    model_config = ConfigDict(strict=True)
```

## Async Patterns

```python
# IO-bound operations: always async
async def fetch_data(url: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

# CPU-bound operations: use run_in_executor or background tasks
from concurrent.futures import ProcessPoolExecutor

async def process_ocr(file_bytes: bytes) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, _ocr_sync, file_bytes)
```

## Dependency Injection (FastAPI)

```python
from fastapi import Depends

async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    ...

# Route handlers use Depends()
@router.get("/invoices")
async def list_invoices(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> PaginatedResponse[InvoiceResponse]:
    ...
```

## Testing

```python
import pytest
from httpx import AsyncClient

@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_create_invoice(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/invoices",
        json={"vendor_name": "Test Vendor", "amount": "150.00"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["vendor_name"] == "Test Vendor"
```
