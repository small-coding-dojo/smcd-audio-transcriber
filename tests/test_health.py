"""Tests for the Phase 0 health-check endpoint and basic app wiring."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_check_returns_ok_status():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_response_includes_request_id_header():
    response = client.get("/health")

    assert "x-request-id" in response.headers
