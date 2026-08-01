"""Unit tests for core/web_server.py FastAPI endpoints."""

from fastapi.testclient import TestClient
from core.web_server import app

client = TestClient(app)

def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200

def test_status_endpoint():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "lock" in data

def test_telemetry_endpoint():
    response = client.get("/api/telemetry")
    assert response.status_code == 200
    data = response.json()
    assert "gpus" in data

def test_sessions_endpoint():
    response = client.get("/api/sessions")
    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert "current" in data

def test_files_tree_endpoint():
    response = client.get("/api/files/tree")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_tasks_endpoint():
    response = client.get("/api/tasks")
    assert response.status_code == 200
    data = response.json()
    assert "todo" in data
    assert "done" in data
