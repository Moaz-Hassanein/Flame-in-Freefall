# ADR 0002 — Read-only API without Authentication

- Status: Accepted
- Date: 2026-11-14
- Phase: 8

## Context

Phase 8 exposes the Flame in Freefall RAG and retrieval pipeline through a FastAPI HTTP service (`/api/v1`). The system provides scientific exploration, structured experiment queries, metadata introspection, and grounded natural-language question answering over public NASA and JAXA microgravity combustion datasets.

All data exposed by this service originates from publicly released research publications, NASA open data repositories, and JAXA archives. There are no private user profiles, sensitive personal records, write operations, or mutable states handled by the API.

## Decision

We decided to deploy the API **without authentication or user authorization mechanisms** (no API keys, OAuth2, JWTs, or session tokens) for local exploration, internal research, and evaluation.

### Rationale

1. **Read-Only Scope**: Every endpoint (`GET /api/v1/health`, `GET /api/v1/ready`, `GET /api/v1/meta`, `GET /api/v1/experiments`, `GET /api/v1/experiments/{id}`, `POST /api/v1/ask`) is strictly idempotent and read-only.
2. **Deterministic SQL Guardrails**: The API never permits arbitrary SQL from the client; all queries are compiled through strict Pydantic `QueryPlan` schemas against an immutable, read-only DuckDB in-memory view over the Parquet snapshot.
3. **In-Process Abuse Protection**: In-memory rate limiting per client IP prevents denial-of-service and runaway LLM costs on the `/ask` endpoint without adding external auth complexity.

## Changes Required if Exposed Publicly

If the Flame in Freefall API is deployed publicly on the open Internet or exposed to untrusted external callers, the following security controls must be implemented:

1. **API Key Authentication / Bearer Tokens**:
   - Issue tenant or user API keys to meter and attribute query volumes.
   - Implement FastAPI security dependencies (`HTTPBearer` or `APIKeyHeader`) to authenticate requests.
2. **Distributed Rate Limiting and Quota Management**:
   - Replace the in-process sliding window (`InMemoryRateLimiter`) with a Redis-backed token bucket to enforce per-user monthly query quotas and throttle LLM inference costs across distributed server replicas.
3. **Tiered Access & Usage Tracking**:
   - Attribute token usage and compute costs to specific user accounts.
4. **WAF & DDoS Mitigation**:
   - Place the service behind an API gateway (e.g., Cloudflare, AWS API Gateway, or Kong) with Web Application Firewall (WAF) rules, TLS termination, and DDoS filtering.
5. **CORS Hardening**:
   - Restrict `cors_origins` strictly to production frontend domains rather than development localhost origins.
