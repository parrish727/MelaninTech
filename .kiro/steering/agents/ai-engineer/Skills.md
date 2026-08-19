---
inclusion: fileMatch
fileMatchPattern: "**/*.py,**/*.ts,**/*.tsx,**/agents/**,**/skills/**,**/ollama*,**/embeddings/**,**/mcp*"
description: "AI Engineering agent skill definitions for code generation, embeddings, and MCP."
---

# AI Engineering Agent — Skills

## FastAPI Service Development

### New Endpoint Pattern
```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import PaginatedResponse, InvoiceCreate, InvoiceResponse

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_invoice(
    payload: InvoiceCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InvoiceResponse:
    """Create a new invoice for the authenticated user's practice."""
    invoice = Invoice(**payload.model_dump(), practice_id=user.practice_id)
    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)
    return InvoiceResponse.model_validate(invoice)
```

### Database Migration Pattern
```python
# migrations/versions/0042_add_insurance_claims.py
"""Add insurance claims table.

Revision ID: 0042
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "insurance_claims",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("practice_id", sa.Integer, sa.ForeignKey("practices.id"), nullable=False),
        sa.Column("patient_name", sa.Text, nullable=False),
        sa.Column("claim_amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("idx_claims_practice_status", "insurance_claims", ["practice_id", "status"])


def downgrade() -> None:
    op.drop_table("insurance_claims")
```

## React Frontend Development

### Component Pattern
```typescript
import { motion } from "framer-motion";
import { FileText, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

interface InvoiceCardProps {
  invoice: Invoice;
  onApprove: (id: number) => void;
  isLoading?: boolean;
}

export const InvoiceCard: React.FC<InvoiceCardProps> = ({
  invoice,
  onApprove,
  isLoading = false,
}) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        "rounded-xl border bg-white p-4 shadow-sm transition-colors",
        invoice.status === "overdue" && "border-red-200 bg-red-50",
      )}
    >
      <div className="flex items-center gap-3">
        <FileText className="h-5 w-5 text-gray-400" />
        <div className="flex-1">
          <p className="font-medium text-gray-900">{invoice.vendorName}</p>
          <p className="text-sm text-gray-500">${invoice.amount.toFixed(2)}</p>
        </div>
        <button
          onClick={() => onApprove(invoice.id)}
          disabled={isLoading}
          className="rounded-md bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Approve
        </button>
      </div>
    </motion.div>
  );
};
```

### Custom Hook Pattern
```typescript
import { useState, useEffect, useCallback } from "react";

interface UseApiOptions<T> {
  url: string;
  enabled?: boolean;
}

interface UseApiResult<T> {
  data: T | null;
  isLoading: boolean;
  error: Error | null;
  refetch: () => void;
}

export function useApi<T>({ url, enabled = true }: UseApiOptions<T>): UseApiResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await fetch(url, { headers: getAuthHeaders() });
      if (!response.ok) throw new ApiError(response.status);
      setData(await response.json());
    } catch (e) {
      setError(e instanceof Error ? e : new Error("Unknown error"));
    } finally {
      setIsLoading(false);
    }
  }, [url]);

  useEffect(() => {
    if (enabled) fetchData();
  }, [fetchData, enabled]);

  return { data, isLoading, error, refetch: fetchData };
}
```

## Ollama Model Management

### Embedding Pipeline
```python
import httpx
from typing import List

OLLAMA_URL = "http://ollama:11434"
EMBED_MODEL = "nomic-embed-text"


async def generate_embedding(text: str) -> List[float]:
    """Generate embedding vector using local Ollama instance."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()["embedding"]


async def semantic_search(
    query: str,
    db: AsyncSession,
    limit: int = 10,
    similarity_threshold: float = 0.7,
) -> list[MemoryResult]:
    """Search agent memory using pgvector similarity."""
    query_embedding = await generate_embedding(query)
    results = await db.execute(
        text("""
            SELECT content, metadata, 1 - (embedding <=> :query_vec::vector) AS similarity
            FROM agent_memory
            WHERE 1 - (embedding <=> :query_vec::vector) > :threshold
            ORDER BY embedding <=> :query_vec::vector
            LIMIT :limit
        """),
        {"query_vec": str(query_embedding), "threshold": similarity_threshold, "limit": limit},
    )
    return [MemoryResult(**row._mapping) for row in results]
```

### Custom Model Creation
```bash
# Create a custom classification model (Modelfile)
FROM nomic-embed-text
PARAMETER temperature 0
SYSTEM "You are a document classifier for orthodontic invoices..."

# Build and serve
ollama create orthoflow-classify -f ./Modelfile
ollama run orthoflow-classify "Classify: Delta Dental payment $1,250"
```

## Agent Skill Authoring

### Skill File Format (*.skill.md)
```markdown
# skill: invoice-classifier
## trigger
keywords: classify, categorize, sort, invoice, vendor
## context
- Access to OrthoFlow invoice categories
- Uses orthoflow-classify model (Ollama)
## instructions
1. Accept invoice text or image OCR output
2. Run classification via Ollama orthoflow-classify model
3. Return category, confidence score, and suggested GL code
4. If confidence < 0.8, flag for human review
## constraints
- Never modify invoice data directly
- Log all classification results to audit trail
- Defer to human if multiple categories have similar confidence
```

### MCP Server Integration
```python
from mcp import Server, Tool

server = Server("melanin-tools")

@server.tool()
async def query_memory(query: str, limit: int = 5) -> str:
    """Search agent semantic memory for relevant context."""
    results = await semantic_search(query, db, limit=limit)
    return "\n".join(f"[{r.similarity:.2f}] {r.content}" for r in results)

@server.tool()
async def list_active_services() -> str:
    """List all running Docker services and their health status."""
    # Implementation using docker stats
    ...
```

## Testing Patterns

### FastAPI Integration Test
```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_create_invoice(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/invoices/",
        json={"vendor_name": "Test Vendor", "amount": "150.00", "category": "supplies"},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["vendor_name"] == "Test Vendor"
```

### React Component Test
```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { InvoiceCard } from "./InvoiceCard";

describe("InvoiceCard", () => {
  const mockInvoice = {
    id: 1,
    vendorName: "Test Vendor",
    amount: 150.0,
    status: "pending" as const,
  };

  it("renders vendor name and amount", () => {
    render(<InvoiceCard invoice={mockInvoice} onApprove={vi.fn()} />);
    expect(screen.getByText("Test Vendor")).toBeInTheDocument();
    expect(screen.getByText("$150.00")).toBeInTheDocument();
  });

  it("calls onApprove when button clicked", () => {
    const onApprove = vi.fn();
    render(<InvoiceCard invoice={mockInvoice} onApprove={onApprove} />);
    fireEvent.click(screen.getByText("Approve"));
    expect(onApprove).toHaveBeenCalledWith(1);
  });
});
```
