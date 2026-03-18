import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to the Private GTO Wizard API"}

def test_list_solutions_empty():
    response = client.get("/solutions")
    assert response.status_code == 200
    assert response.json() == []

@pytest.mark.asyncio
async def test_ingest_endpoint_status():
    # Test that the ingest endpoint accepts requests
    response = client.post("/ingest", json={
        "file_path": "/tmp/test.csv",
        "name": "Test Solution",
        "format": "pio_csv"
    })
    assert response.status_code == 200
    assert "Ingestion started" in response.json()["message"]
