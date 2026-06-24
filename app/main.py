import os
from pathlib import Path
from typing import Dict, Any

import joblib
import numpy as np
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field


# ---------------------------------------------------------
# 1. Configuración básica de la aplicación
# ---------------------------------------------------------

app = FastAPI(
    title="API Modelo IA - Iris",
    description="API sencilla para desplegar un modelo de Machine Learning con FastAPI, Docker, ACR, ACI y GitHub Actions.",
    version="1.0.0"
)

_API_KEY = os.getenv("API_KEY", "")
_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _check_api_key(key: str | None = Depends(_key_header)) -> None:
    if _API_KEY and key != _API_KEY:
        raise HTTPException(status_code=403, detail="API key inválida o ausente")


# ---------------------------------------------------------
# 2. Ruta del modelo entrenado
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH = BASE_DIR / "app" / "model" / "iris_model.joblib"
ALTERNATIVE_MODEL_PATH = BASE_DIR / "model" / "iris_model.joblib"


def extract_model(loaded_object: Any):
    """
    Extrae el modelo real desde el objeto cargado con joblib.

    Puede pasar una de estas dos cosas:
    1. Que el fichero .joblib contenga directamente el modelo.
    2. Que el fichero .joblib contenga un diccionario con el modelo dentro.
    """

    # Caso 1: el objeto cargado ya es directamente un modelo
    if hasattr(loaded_object, "predict"):
        return loaded_object

    # Caso 2: el objeto cargado es un diccionario
    if isinstance(loaded_object, dict):
        possible_keys = ["model", "modelo", "classifier", "clf", "pipeline", "estimator"]

        for key in possible_keys:
            if key in loaded_object and hasattr(loaded_object[key], "predict"):
                return loaded_object[key]

        # Si no encontramos una clave conocida, buscamos cualquier valor que tenga predict()
        for value in loaded_object.values():
            if hasattr(value, "predict"):
                return value

        raise ValueError(
            f"El fichero .joblib contiene un diccionario, pero no se ha encontrado ningún modelo válido. "
            f"Claves disponibles: {list(loaded_object.keys())}"
        )

    raise ValueError(
        f"El objeto cargado desde .joblib no es un modelo válido. Tipo encontrado: {type(loaded_object)}"
    )


def load_model():
    """
    Carga el modelo desde la ruta esperada.
    """

    if MODEL_PATH.exists():
        loaded_object = joblib.load(MODEL_PATH)
        return extract_model(loaded_object)

    if ALTERNATIVE_MODEL_PATH.exists():
        loaded_object = joblib.load(ALTERNATIVE_MODEL_PATH)
        return extract_model(loaded_object)

    raise FileNotFoundError(
        f"No se ha encontrado el modelo. Se esperaba en: {MODEL_PATH} "
        f"o en: {ALTERNATIVE_MODEL_PATH}"
    )


model = load_model()


CLASS_NAMES = {
    0: "setosa",
    1: "versicolor",
    2: "virginica"
}


# ---------------------------------------------------------
# 3. Modelo de datos de entrada
# ---------------------------------------------------------

class IrisInput(BaseModel):
    sepal_length: float = Field(..., example=5.1)
    sepal_width: float = Field(..., example=3.5)
    petal_length: float = Field(..., example=1.4)
    petal_width: float = Field(..., example=0.2)


# ---------------------------------------------------------
# 4. Endpoint raíz
# ---------------------------------------------------------

_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Iris Classifier</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#080d1a;--surface:#0f1629;--border:#1e2d4a;
  --accent:#7c3aed;--accent-glow:rgba(124,58,237,.22);
  --text:#e8edf5;--muted:#5a6a8a;
  --setosa:#a78bfa;--versicolor:#60a5fa;--virginica:#34d399;
}
body{
  background:var(--bg);color:var(--text);
  font-family:'Courier New',Courier,monospace;
  min-height:100vh;display:flex;flex-direction:column;
  align-items:center;justify-content:center;padding:2rem 1rem;
}
header{text-align:center;margin-bottom:2.5rem}
.eyebrow{
  font-size:.7rem;letter-spacing:.25em;text-transform:uppercase;
  color:var(--accent);margin-bottom:.75rem;
}
h1{font-size:1.75rem;font-weight:700;letter-spacing:-.02em}
h1 span{color:var(--accent)}
.card{
  background:var(--surface);border:1px solid var(--border);
  border-radius:12px;padding:2rem;width:100%;max-width:480px;
}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:1.25rem;margin-bottom:1.5rem}
.field label{
  display:block;font-size:.65rem;letter-spacing:.15em;
  text-transform:uppercase;color:var(--muted);margin-bottom:.4rem;
}
.unit{color:var(--accent)}
.field input{
  width:100%;background:var(--bg);border:1px solid var(--border);
  border-radius:6px;color:var(--text);font-family:inherit;
  font-size:1rem;padding:.6rem .75rem;outline:none;
  transition:border-color .15s,box-shadow .15s;
  -moz-appearance:textfield;
}
.field input::-webkit-outer-spin-button,
.field input::-webkit-inner-spin-button{-webkit-appearance:none}
.field input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow)}
button[type=submit]{
  width:100%;background:var(--accent);color:#fff;border:none;
  border-radius:6px;font-family:inherit;font-size:.8rem;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;padding:.8rem;
  cursor:pointer;transition:opacity .15s,transform .1s;
}
button[type=submit]:hover{opacity:.85}
button[type=submit]:active{transform:scale(.99)}
button[type=submit]:disabled{opacity:.4;cursor:not-allowed}
.error{
  margin-top:1rem;padding:.75rem 1rem;
  background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);
  border-radius:6px;color:#fca5a5;font-size:.8rem;display:none;
}
.error.on{display:block}
.result{
  margin-top:1.75rem;padding-top:1.75rem;
  border-top:1px solid var(--border);display:none;
}
.result.on{display:block}
.result-label{
  font-size:.65rem;letter-spacing:.15em;
  text-transform:uppercase;color:var(--muted);margin-bottom:.4rem;
}
.result-species{font-size:1.5rem;font-weight:700;margin-bottom:1.5rem}
.result-species.setosa{color:var(--setosa)}
.result-species.versicolor{color:var(--versicolor)}
.result-species.virginica{color:var(--virginica)}
.probs{display:flex;flex-direction:column;gap:.75rem}
.prob-header{
  display:flex;justify-content:space-between;
  font-size:.7rem;letter-spacing:.1em;
  text-transform:uppercase;color:var(--muted);margin-bottom:.3rem;
}
.prob-header .pct{color:var(--text);font-weight:700}
.track{background:var(--border);border-radius:2px;height:4px;overflow:hidden}
.fill{height:100%;border-radius:2px;width:0;transition:width .6s cubic-bezier(.4,0,.2,1)}
.fill.setosa{background:var(--setosa)}
.fill.versicolor{background:var(--versicolor)}
.fill.virginica{background:var(--virginica)}
.links{margin-top:1.5rem;display:flex;gap:1.5rem;justify-content:center}
.links a{
  font-size:.65rem;letter-spacing:.15em;text-transform:uppercase;
  color:var(--muted);text-decoration:none;transition:color .15s;
}
.links a:hover{color:var(--accent)}
@media(max-width:400px){.grid{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){.fill{transition:none}}
</style>
</head>
<body>
<header>
  <p class="eyebrow">Iris · Scikit-learn · FastAPI</p>
  <h1>Clasificador <span>Iris</span></h1>
</header>
<div class="card">
  <form id="f">
    <div class="grid">
      <div class="field">
        <label>Sépalo longitud <span class="unit">cm</span></label>
        <input type="number" id="sepal_length" step="0.1" value="5.1" required>
      </div>
      <div class="field">
        <label>Sépalo anchura <span class="unit">cm</span></label>
        <input type="number" id="sepal_width" step="0.1" value="3.5" required>
      </div>
      <div class="field">
        <label>Pétalo longitud <span class="unit">cm</span></label>
        <input type="number" id="petal_length" step="0.1" value="1.4" required>
      </div>
      <div class="field">
        <label>Pétalo anchura <span class="unit">cm</span></label>
        <input type="number" id="petal_width" step="0.1" value="0.2" required>
      </div>
    </div>
    <button type="submit" id="btn">Clasificar</button>
    <div class="error" id="err"></div>
    <div class="result" id="res">
      <p class="result-label">Especie detectada</p>
      <p class="result-species" id="species"></p>
      <div class="probs">
        <div>
          <div class="prob-header"><span>Setosa</span><span class="pct" id="pct-setosa"></span></div>
          <div class="track"><div class="fill setosa" id="bar-setosa"></div></div>
        </div>
        <div>
          <div class="prob-header"><span>Versicolor</span><span class="pct" id="pct-versicolor"></span></div>
          <div class="track"><div class="fill versicolor" id="bar-versicolor"></div></div>
        </div>
        <div>
          <div class="prob-header"><span>Virginica</span><span class="pct" id="pct-virginica"></span></div>
          <div class="track"><div class="fill virginica" id="bar-virginica"></div></div>
        </div>
      </div>
    </div>
  </form>
</div>
<nav class="links">
  <a href="/docs" target="_blank" rel="noopener">API Docs</a>
  <a href="/health" target="_blank" rel="noopener">Health</a>
</nav>
<script>
const KEY = "__API_KEY__";
document.getElementById('f').addEventListener('submit', async e => {
  e.preventDefault();
  const btn = document.getElementById('btn');
  const err = document.getElementById('err');
  const res = document.getElementById('res');
  btn.disabled = true;
  btn.textContent = 'Clasificando…';
  err.classList.remove('on');
  res.classList.remove('on');
  try {
    const r = await fetch('/predict', {
      method: 'POST',
      headers: {'Content-Type':'application/json', ...(KEY && {'X-API-Key': KEY})},
      body: JSON.stringify({
        sepal_length: +document.getElementById('sepal_length').value,
        sepal_width:  +document.getElementById('sepal_width').value,
        petal_length: +document.getElementById('petal_length').value,
        petal_width:  +document.getElementById('petal_width').value,
      })
    });
    if (!r.ok) { const j = await r.json().catch(()=>({})); throw new Error(j.detail || 'Error '+r.status); }
    const d = await r.json();
    const sp = d.class_name;
    const pr = d.probabilities || {};
    document.getElementById('species').textContent = 'Iris ' + sp;
    document.getElementById('species').className = 'result-species ' + sp;
    for (const [n, v] of [['setosa', pr.setosa||0],['versicolor', pr.versicolor||0],['virginica', pr.virginica||0]]) {
      document.getElementById('pct-'+n).textContent = (v*100).toFixed(1)+'%';
      requestAnimationFrame(() => { document.getElementById('bar-'+n).style.width = (v*100).toFixed(1)+'%'; });
    }
    res.classList.add('on');
  } catch(e) {
    err.textContent = e.message;
    err.classList.add('on');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Clasificar';
  }
});
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return _HTML.replace("__API_KEY__", _API_KEY)


# ---------------------------------------------------------
# 5. Endpoint de salud
# ---------------------------------------------------------

@app.get("/health")
def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "model": "loaded",
        "model_type": str(type(model))
    }


# ---------------------------------------------------------
# 6. Endpoint de predicción
# ---------------------------------------------------------

@app.post("/predict", dependencies=[Depends(_check_api_key)])
def predict(data: IrisInput) -> Dict[str, Any]:
    try:
        input_data = np.array([
            [
                data.sepal_length,
                data.sepal_width,
                data.petal_length,
                data.petal_width
            ]
        ])

        raw_prediction = model.predict(input_data)[0]
        prediction = int(raw_prediction)

        response = {
            "input": {
                "sepal_length": data.sepal_length,
                "sepal_width": data.sepal_width,
                "petal_length": data.petal_length,
                "petal_width": data.petal_width
            },
            "prediction": prediction,
            "class_name": CLASS_NAMES.get(prediction, "clase_desconocida")
        }

        if hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(input_data)[0]

            response["probabilities"] = {
                "setosa": float(probabilities[0]),
                "versicolor": float(probabilities[1]),
                "virginica": float(probabilities[2])
            }

        return response

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error realizando la predicción: {str(e)}"
        )