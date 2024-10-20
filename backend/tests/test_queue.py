import pytest
from fastapi.testclient import TestClient
from main import app  # Assuming your FastAPI app is named 'app'

client = TestClient(app)

def test_create_queue_point():
    response = client.post("/queue-point/", json={"name": "Test Queue", "max_simultaneous": 3, "avg_time": 5})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Queue"
    assert "id" in data


def test_get_queues():
    response = client.get("/queues")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0  # Assuming there is at least one queue point