# Iris API — Clasificador de flores con FastAPI y CI/CD

Servicio REST en Python con FastAPI que expone un clasificador de flores Iris (scikit-learn), contenerizado con Docker y desplegado automáticamente mediante GitHub Actions en **AWS ECS Fargate** o **Azure ACI**.

## Descripción del proyecto

Cualquier push a la rama `main` desencadena el pipeline de CI/CD:

1. **test** — instala dependencias, entrena el modelo y ejecuta `pytest`.
2. **build-and-push** — construye la imagen Docker y la sube al registro de contenedores (ECR o ACR).
3. **deploy** — despliega la nueva imagen en el servicio en la nube y verifica que `/health` responde.

El endpoint `/predict` requiere una `API_KEY` enviada en la cabecera `X-API-Key`.

## Requisitos previos

- Python 3.11+
- [Docker](https://www.docker.com/) — opcional, para pruebas locales con contenedor

## Instalación

```bash
pip install -r app/requirements.txt
```

## Entrenar el modelo

El modelo debe existir antes de arrancar la API. Solo es necesario ejecutarlo una vez (o si se modifica `train_model.py`):

```bash
python app/train_model.py
```

Genera `app/model/iris_model.joblib`.

## Ejecutar en local

```bash
uvicorn app.main:app --reload --port 8000
```

Abre <http://localhost:8000> — interfaz web con el clasificador.  
Documentación interactiva: <http://localhost:8000/docs>

## Ejecutar los tests

```bash
python -m pytest -q                                              # todos los tests
python -m pytest app/tests/test_api.py::test_predict_endpoint -v # test individual
```

## Docker

### Construir la imagen

```bash
docker build -t iris-api-local:latest .
```

### Ejecutar en primer plano

```bash
docker run --rm -p 8000:8000 iris-api-local:latest
```

Detener con `Ctrl+C`. Abre <http://localhost:8000>.

### Ejecutar en segundo plano

```bash
docker run -d --name iris-api -p 8000:8000 iris-api-local:latest
```

### Ver logs / detener / eliminar

```bash
docker logs iris-api
docker stop iris-api
docker rm iris-api
```

## Pipeline CI/CD

El fichero `.github/workflows/aws.yml` se dispara en cada push a `main` y ejecuta en orden:

1. Instala dependencias y entrena el modelo
2. Ejecuta `pytest`
3. Configura credenciales AWS y hace login en ECR
4. Construye la imagen Docker y realiza un smoke test local (`/health`)
5. Sube la imagen a ECR con el SHA del commit como tag
6. Inyecta la `API_KEY` en la definición de tarea ECS
7. Registra la nueva revisión y actualiza el servicio Fargate
8. Espera a que el servicio estabilice y verifica que `/health` responde

### Secrets requeridos

| Secret | Descripción |
|---|---|
| `AWS_ACCESS_KEY_ID` | Clave de acceso AWS |
| `AWS_SECRET_ACCESS_KEY` | Clave secreta AWS |
| `AWS_SESSION_TOKEN` | Token de sesión (solo AWS Academy Labs) |
| `API_KEY` | Clave para proteger `/predict` |

Los valores no sensibles (`AWS_REGION`, `ECR_REPOSITORY`, `ECS_CLUSTER`, etc.) se definen en el bloque `env:` del workflow.

Para el procedimiento completo de configuración:

- AWS estándar → [`doc/aws-setup_es.md`](doc/aws-setup_es.md)
- AWS Academy Lab → [`doc/awsacademy-setup_es.md`](doc/awsacademy-setup_es.md)
- Azure → [`doc/azure-setup_es.md`](doc/azure-setup_es.md)

## Aplicación desplegada

Tras cada ejecución exitosa el pipeline imprime la URL en los logs de Actions (paso **"Verificar endpoint ECS desplegado"**).

> En AWS Fargate la IP cambia en cada despliegue. En Azure ACI la URL es estable (`http://<dns-label>.<region>.azurecontainer.io:<port>`).

## Arquitectura

```
GitHub (push a main)
        │
        ▼
GitHub Actions (.github/workflows/aws.yml)
  ├── pytest        → tests sobre el código fuente
  ├── docker build  → imagen Docker → ECR
  └── ecs update    → ECS Fargate (us-east-1)
                          │
                          ▼
              http://<ip-pública>:8000
```

### Ficheros principales

| Fichero | Propósito |
|---|---|
| `app/main.py` | FastAPI app — endpoints `/`, `/health`, `/predict` |
| `app/train_model.py` | Entrena y guarda el modelo |
| `app/model/iris_model.joblib` | Modelo entrenado (generado, no en el repo) |
| `app/tests/test_api.py` | Tests de la API |
| `app/requirements.txt` | Dependencias Python |
| `Dockerfile` | Imagen basada en `python:3.11-slim` |
| `aws/task-definition.json` | Definición de tarea ECS |
| `.github/workflows/aws.yml` | Pipeline CI/CD para AWS |
| `doc/aws-setup_es.md` | Guía de configuración AWS estándar |
| `doc/awsacademy-setup_es.md` | Guía de configuración AWS Academy Lab |
| `doc/azure-setup_es.md` | Guía de configuración Azure |
