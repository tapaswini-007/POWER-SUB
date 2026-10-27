"""Tests for security headers, API key authentication, rate limiting, and CORS enforcement."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.core.security import rate_limiter
from app.main import app


def test_security_headers_present(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    headers = response.headers

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert headers.get("Referrer-Policy") == "no-referrer"
    assert "X-Request-ID" in headers
    # Dynamic API response has Cache-Control: no-store
    assert "no-store" in headers.get("Cache-Control", "")


def test_api_key_enforcement():
    # Configure API key temporarily
    old_key = settings.API_KEY
    settings.API_KEY = "test-secret-api-key-999"

    try:
        with TestClient(app) as test_client:
            # 1. Health endpoint is exempt
            res_health = test_client.get("/api/v1/health")
            assert res_health.status_code == 200

            # 2. Protected endpoint without key -> 401
            res_no_key = test_client.get("/api/v1/datasets")
            assert res_no_key.status_code == 401
            assert res_no_key.json()["error"]["code"] == "UNAUTHORIZED"

            # 3. Protected endpoint with invalid key -> 401
            res_bad_key = test_client.get("/api/v1/datasets", headers={"X-API-Key": "wrong-key"})
            assert res_bad_key.status_code == 401

            # 4. Protected endpoint with valid key -> 200
            res_good = test_client.get(
                "/api/v1/datasets", headers={"X-API-Key": "test-secret-api-key-999"}
            )
            assert res_good.status_code == 200
    finally:
        settings.API_KEY = old_key


def test_rate_limiting(client: TestClient):
    # Reset limiter history
    rate_limiter.reset()
    old_limit = rate_limiter.limit
    rate_limiter.limit = 3  # Set tight limit for test

    try:
        # 3 requests allowed
        for _ in range(3):
            res = client.post(
                "/api/v1/upload",
                files={
                    "file": (
                        "small.csv",
                        b"date,energy_kwh\n2024-01-01,10\n",
                        "text/csv",
                    )
                },
            )
            assert res.status_code in (201, 400, 422)

        # 4th request must be rejected with 429
        res_blocked = client.post(
            "/api/v1/upload",
            files={"file": ("small.csv", b"date,energy_kwh\n2024-01-01,10\n", "text/csv")},
        )
        assert res_blocked.status_code == 429
        assert res_blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    finally:
        rate_limiter.limit = old_limit
        rate_limiter.reset()


def test_cors_headers(client: TestClient):
    # Allowed origin
    res_allowed = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_allowed.headers.get("access-control-allow-origin") == "http://localhost:3000"

    # Disallowed origin
    res_disallowed = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://evil-attacker.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res_disallowed.headers.get("access-control-allow-origin") is None


def test_production_mode_refuses_wildcard_cors():
    # Wildcard in ALLOWED_ORIGINS should fail validation
    with pytest.raises(ValueError, match="Wildcard"):
        Settings(APP_ENV="production", ALLOWED_ORIGINS="*")

    # Empty ALLOWED_ORIGINS in production should fail validation
    with pytest.raises(ValueError, match="cannot be empty"):
        Settings(APP_ENV="production", ALLOWED_ORIGINS="")


def test_error_envelope_contains_no_internal_stack_traces(client: TestClient):
    # Trigger 404
    res = client.get("/api/v1/datasets/00000000-0000-4000-8000-000000000000")
    assert res.status_code == 404
    body = res.json()

    assert "error" in body
    assert "code" in body["error"]
    assert "message" in body["error"]
    assert "request_id" in body

    # Must NOT leak file paths, tracebacks, or SQL queries
    body_str = str(body)
    assert "Traceback" not in body_str
    assert "SELECT " not in body_str
    assert "c:\\" not in body_str.lower()
    assert "/home/" not in body_str
