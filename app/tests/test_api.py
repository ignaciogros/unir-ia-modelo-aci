import pathlib
import sys

from fastapi.testclient import TestClient


# ---------------------------------------------------------
# 1. Añadimos la raíz del proyecto al path de Python
# ---------------------------------------------------------

ROOT_DIR = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))


# ---------------------------------------------------------
# 2. Importamos la aplicación FastAPI
# ---------------------------------------------------------

from app.main import app  # noqa: E402


client = TestClient(app)


# ---------------------------------------------------------
# 3. Test del endpoint raíz
# ---------------------------------------------------------

def test_home_endpoint():
    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert "message" in data
    assert data["docs"] == "/docs"
    assert data["health"] == "/health"
    assert data["predict"] == "/predict"


# ---------------------------------------------------------
# 4. Test del endpoint /health
# ---------------------------------------------------------

def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "ok"
    assert data["model"] == "loaded"


# ---------------------------------------------------------
# 5. Test del endpoint /predict
# ---------------------------------------------------------

def test_predict_endpoint():
    payload = {
        "sepal_length": 5.1,
        "sepal_width": 3.5,
        "petal_length": 1.4,
        "petal_width": 0.2
    }

    response = client.post("/predict", json=payload)

    assert response.status_code == 200

    data = response.json()

    assert "prediction" in data
    assert "class_name" in data
    assert data["class_name"] in ["setosa", "versicolor", "virginica"]