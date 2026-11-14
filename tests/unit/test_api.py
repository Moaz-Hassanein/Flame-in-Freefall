"""Integration tests for the HTTP API endpoints, middleware, and error handling."""

from __future__ import annotations

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from flame.api.main import create_app
from flame.config import Settings
from tests.doubles.fake_llm import FakeLLMClient


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient()


@pytest.fixture
def test_app(fake_llm: FakeLLMClient):
    app = create_app(llm_client=fake_llm)
    return app


@pytest.mark.anyio
async def test_health_endpoint(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] == "ok"
        assert "x-request-id" in resp.headers


@pytest.mark.anyio
async def test_ready_endpoint(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/v1/ready")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["status"] == "ready"
        assert data["dataset_loaded"] is True
        assert data["manifest_loaded"] is True
        assert data["total_rows"] > 0
        assert data["llm_configured"] is True
        assert "x-request-id" in resp.headers


@pytest.mark.anyio
async def test_meta_endpoint(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/v1/meta")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "version_info" in data
        assert "field_catalog" in data
        assert "dataset_families" in data
        assert len(data["dataset_families"]) > 0
        assert data["modeled_rows_count"] > 0
        assert len(data["data_limitations"]) > 0
        assert "x-request-id" in resp.headers


@pytest.mark.anyio
async def test_experiments_listing_and_pagination(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # Request with pagination limit and family filter
        resp = await client.get(
            "/api/v1/experiments",
            params={"dataset_family": "BASS-II", "limit": 10, "offset": 0},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "items" in data
        assert len(data["items"]) == 10
        assert data["total"] > 10
        assert data["limit"] == 10
        assert data["offset"] == 0
        assert all(row["dataset_family"] == "BASS-II" for row in data["items"])
        assert "x-request-id" in resp.headers


@pytest.mark.anyio
async def test_get_experiment_by_id_success(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # Get one experiment ID from listing first
        list_resp = await client.get("/api/v1/experiments?limit=1")
        eid = list_resp.json()["items"][0]["experiment_id"]

        resp = await client.get(f"/api/v1/experiments/{eid}")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["experiment_id"] == eid
        assert "dataset_family" in data
        assert "source_url" in data
        assert "data_quality_flags" in data
        assert "x-request-id" in resp.headers


@pytest.mark.anyio
async def test_get_experiment_by_id_not_found(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/v1/experiments/NON_EXISTENT_ID_99999")
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        data = resp.json()
        assert data["error_code"] == "NOT_FOUND"
        assert "not found" in data["message"].lower()
        assert "request_id" in data
        assert "x-request-id" in resp.headers


@pytest.mark.anyio
async def test_ask_valid_question(test_app, fake_llm: FakeLLMClient):
    # Enqueue planner output
    fake_llm.enqueue_structured(
        {
            "intent": "lookup",
            "filters": [
                {"field": "dataset_family", "op": "eq", "value": "BASS-II"},
            ],
            "limit": 5,
        }
    )
    # Enqueue generator output
    fake_llm.enqueue_structured(
        {
            "answer_text": "BASS-II evaluated solid fuel combustion in microgravity.",
            "cited_ids": [],
            "limitations": [],
        }
    )

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/ask",
            json={"question": "What fuels were burned in BASS-II?"},
        )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["question"] == "What fuels were burned in BASS-II?"
        assert data["status"] == "answered"
        assert data["answer_markdown"] is not None
        assert "x-request-id" in resp.headers


@pytest.mark.anyio
async def test_ask_validation_failure_empty_question(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.post("/api/v1/ask", json={"question": ""})
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        data = resp.json()
        assert data["error_code"] == "VALIDATION_ERROR"
        assert "request_id" in data
        assert "x-request-id" in resp.headers


@pytest.mark.anyio
async def test_ask_rate_limit_exceeded():
    fake_llm = FakeLLMClient()
    # Configure app with low rate limit: 2 requests per minute
    custom_settings = Settings(rate_limit_per_minute=2)
    app = create_app(settings=custom_settings, llm_client=fake_llm)

    # Enqueue 2 responses
    for _ in range(2):
        fake_llm.enqueue_structured({"intent": "out_of_scope"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Request 1: OK
        r1 = await client.post("/api/v1/ask", json={"question": "q1"})
        assert r1.status_code == status.HTTP_200_OK

        # Request 2: OK
        r2 = await client.post("/api/v1/ask", json={"question": "q2"})
        assert r2.status_code == status.HTTP_200_OK

        # Request 3: Throttled (429)
        r3 = await client.post("/api/v1/ask", json={"question": "q3"})
        assert r3.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        data = r3.json()
        assert data["error_code"] == "RATE_LIMIT_EXCEEDED"
        assert "rate limit exceeded" in data["message"].lower()
        assert "request_id" in data
        assert "x-request-id" in r3.headers


@pytest.mark.anyio
async def test_ask_service_unavailable_without_llm():
    # App created without any LLM configured
    app = create_app(llm_client=None)
    app.state.llm_client = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/ask", json={"question": "test question"})
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = resp.json()
        assert data["error_code"] == "SERVICE_UNAVAILABLE"
        assert "not configured" in data["message"].lower()
        assert "request_id" in data
        assert "x-request-id" in resp.headers


@pytest.mark.anyio
async def test_request_id_header_forwarding(test_app):
    custom_req_id = "custom_trace_id_45678"
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        resp = await client.get("/api/v1/health", headers={"x-request-id": custom_req_id})
        assert resp.status_code == status.HTTP_200_OK
        assert resp.headers.get("x-request-id") == custom_req_id
