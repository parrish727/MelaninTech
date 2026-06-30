# Backend Agent Tools

Inherits: [shared.tools.md](shared.tools.md)

## Additional Capabilities

### Volume Mounts (read-write)
- `/app/Projects` — general project access
- `/app/orthoflow-backend` — OrthoFlow FastAPI backend

### Framework Knowledge
- FastAPI + Pydantic for API routes
- SQLAlchemy + Alembic for database models/migrations
- PostgreSQL (pgvector for embeddings)
- Redis for queues (ARQ async workers)
- MinIO for S3-compatible object storage
- JWT + RBAC authentication patterns
- HIPAA-compliant audit logging
