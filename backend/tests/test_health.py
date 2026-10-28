"""Tests for health and settings endpoints."""


def test_root_endpoint(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "FinSight Intelligence"
    assert data["status"] == "online"


def test_health_endpoint(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "database" in data
    assert data["database"]["status"] == "connected"
    assert "vector_store" in data
    assert "ai_providers" in data


def test_readiness_endpoint(client):
    response = client.get("/api/readiness")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["database"] == "connected"


def test_settings_endpoint(client):
    response = client.get("/api/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["project_name"] == "FinSight Intelligence"
    assert "providers" in data
    # Ensure no raw secret keys are exposed
    assert "LLM_API_KEY" not in data
    assert "SECRET_KEY" not in data
