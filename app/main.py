from pathlib import Path
from typing import Dict, Any

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


# ---------------------------------------------------------
# 1. Configuración básica de la aplicación
# ---------------------------------------------------------

app = FastAPI(
    title="API Modelo IA - Iris",
    description="API sencilla para desplegar un modelo de Machine Learning con FastAPI, Docker, ACR, ACI y GitHub Actions.",
    version="1.0.0"
)


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

@app.get("/")
def home() -> Dict[str, str]:
    return {
        "message": "API de modelo IA desplegada correctamente",
        "docs": "/docs",
        "health": "/health",
        "predict": "/predict"
    }


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

@app.post("/predict")
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