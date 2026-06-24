import os
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient


ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from app.main import app  # noqa: E402

client = TestClient(app)

PAYLOAD = {
    "sepal_length": 5.1,
    "sepal_width": 3.5,
    "petal_length": 1.4,
    "petal_width": 0.2,
}


def test_home_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "/predict" in response.text
    assert "/docs" in response.text
    assert "/health" in response.text


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["model"] == "loaded"


def test_predict_sin_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "")
    import importlib
    import app.main as main_module
    monkeypatch.setattr(main_module, "_API_KEY", "")
    response = client.post("/predict", json=PAYLOAD)
    assert response.status_code == 200
    data = response.json()
    assert data["class_name"] in ["setosa", "versicolor", "virginica"]


def test_predict_con_api_key_correcta(monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(main_module, "_API_KEY", "clave-test")
    response = client.post("/predict", json=PAYLOAD, headers={"X-API-Key": "clave-test"})
    assert response.status_code == 200
    data = response.json()
    assert data["class_name"] in ["setosa", "versicolor", "virginica"]


def test_predict_con_api_key_incorrecta(monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(main_module, "_API_KEY", "clave-test")
    response = client.post("/predict", json=PAYLOAD, headers={"X-API-Key": "clave-mala"})
    assert response.status_code == 403


def test_predict_sin_header_cuando_api_key_activa(monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(main_module, "_API_KEY", "clave-test")
    response = client.post("/predict", json=PAYLOAD)
    assert response.status_code == 403