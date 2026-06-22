# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

FastAPI service that exposes an Iris flower classifier (scikit-learn `Pipeline` with `StandardScaler` + `LogisticRegression`) via REST. The full CI/CD pipeline builds, tests, and pushes the Docker image to Azure Container Registry, then deploys to Azure Container Instances using the Azure Management REST API directly (no Service Principal — designed for Azure for Students accounts).

## Commands

```bash
# Install dependencies (file lives under app/)
pip install -r app/requirements.txt

# Train and save the model (must run before starting the API)
python app/train_model.py

# Run API locally (from repo root)
uvicorn app.main:app --reload --port 8000

# Run tests (from repo root)
python -m pytest -q

# Run a single test
python -m pytest app/tests/test_api.py::test_predict_endpoint -v

# Build Docker image
docker build -t iris-api-local:latest .

# Run Docker container locally
docker run --rm -p 8000:8000 iris-api-local:latest
```

## Architecture

```
app/
  main.py           # FastAPI app: GET /, GET /health, POST /predict
  train_model.py    # Standalone script — trains and saves the model
  model/
    iris_model.joblib  # Saved as a dict: {model, target_names, features, accuracy}
  tests/
    test_api.py     # pytest with FastAPI TestClient
Dockerfile          # Copies app/ into /app, runs uvicorn main:app
.github/workflows/blank.yml  # CI/CD: build → test → push to ACR → deploy to ACI
```

**Key constraint:** `model = load_model()` runs at module import time in `main.py`. The `.joblib` file must exist before the API starts. In CI, `train_model.py` always runs before tests. Locally, run `python app/train_model.py` once before `uvicorn`.

**Model loading:** `extract_model()` in `main.py` handles both a raw sklearn estimator and the dict format that `train_model.py` produces — check both code paths if changing the save format.

**Tests:** `test_api.py` manually inserts the repo root into `sys.path` so `from app.main import app` works regardless of working directory. Always run pytest from the repo root.

**CI/CD note:** The workflow references `requirements.txt` (root) but the file is at `app/requirements.txt`. If the workflow step fails on dependency install, this path mismatch is the likely cause.

## GitHub Actions secrets required

Solo se necesita **un único secret**: `AZURE_CREDENTIALS` — el JSON que devuelve `az ad sp create-for-rbac --json-auth`.

Los valores no sensibles (`ACR_NAME`, `RESOURCE_GROUP`, `DNS_LABEL`, etc.) están en el bloque `env:` del workflow y se editan directamente en el fichero. Ver `doc/azure-setup_es.md` para los pasos completos de configuración.
