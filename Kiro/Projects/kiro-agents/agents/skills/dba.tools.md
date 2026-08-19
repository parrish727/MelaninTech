# DBA Agent Tools

Inherits: [shared.tools.md](shared.tools.md)

## Additional Capabilities

### Database Access
- PostgreSQL kiro (via POSTGRES_DSN env var)
- PostgreSQL orthoflow (via host.docker.internal:5433)
- Read-only queries against pg_stat_activity, pg_stat_statements, pg_stat_user_tables

### Health Queries (no LLM needed)
- Connection count and utilization
- Active vs idle vs idle-in-transaction
- Database size
- Dead tuple count and bloat ratio
- Long-running query detection
- Lock contention

### Analysis Queries (LLM-assisted)
- Slow query optimization recommendations
- Index suggestions based on query patterns
- Schema migration risk assessment
- Capacity forecasting based on growth trends
