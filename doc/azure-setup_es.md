# Guía de configuración Azure — iris-api

Esta guía te lleva desde cero hasta tener el pipeline de CI/CD funcionando.  
Todos los comandos usan **PowerShell** y **Azure CLI**.

---

## 1. Requisitos previos

- [Azure CLI](https://learn.microsoft.com/es-es/cli/azure/install-azure-cli) instalado
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y en ejecución
- Cuenta Azure activa (Azure for Students es suficiente)
- Repositorio en GitHub con este código

---

## 2. Variables de entorno local

Define estas variables en PowerShell. Deben coincidir **exactamente** con los valores `env:` del workflow `.github/workflows/blank.yml`.

```powershell
$RG             = "rg-entregable4b-github"
$LOCATION       = "westeurope"
$ACR_NAME       = "acrentregable4b202606"
$IMAGE_NAME     = "iris-api"
$CONTAINER_NAME = "aci-entregable4b"
$DNS_LABEL      = "aci-entregable4b"      # debe ser globalmente único en Azure
$PORT           = 8000
```

---

## 3. Iniciar sesión en Azure

```powershell
az login
az account show --output table
```

---

## 4. Crear el grupo de recursos

```powershell
az group create `
  --name $RG `
  --location $LOCATION
```

---

## 5. Crear Azure Container Registry

El flag `--admin-enabled true` es necesario para que ACI pueda autenticarse con ACR al desplegar.

```powershell
az acr create `
  --resource-group $RG `
  --name $ACR_NAME `
  --sku Basic `
  --admin-enabled true
```

---

## 6. Registrar el proveedor de Azure Container Instances

Solo es necesario la primera vez en la suscripción.

```powershell
az provider register --namespace Microsoft.ContainerInstance
```

Esperar hasta que devuelva `Registered`:

```powershell
az provider show `
  --namespace Microsoft.ContainerInstance `
  --query registrationState `
  --output tsv
```

---

## 7. Crear el Service Principal para GitHub Actions

```powershell
$SUBSCRIPTION_ID = az account show --query id --output tsv

az ad sp create-for-rbac `
  --name "sp-github-entregable4b" `
  --role contributor `
  --scopes "/subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG" `
  --json-auth
```

El comando devuelve un JSON con este formato:

```json
{
  "clientId": "...",
  "clientSecret": "...",
  "subscriptionId": "...",
  "tenantId": "...",
  ...
}
```

Copia el JSON completo (incluidas las llaves `{}`).

---

## 8. Añadir el secret en GitHub

En el repositorio de GitHub:  
**Settings → Secrets and variables → Actions → New repository secret**

| Nombre | Valor |
|---|---|
| `AZURE_CREDENTIALS` | JSON completo del paso anterior |
| `API_KEY` | Clave aleatoria para proteger `/predict` (ver más abajo) |

Generar una clave aleatoria:

```powershell
-join ((65..90) + (97..122) + (48..57) | Get-Random -Count 32 | ForEach-Object { [char]$_ })
```

O con OpenSSL si está disponible:

```powershell
openssl rand -hex 32
```

---

## 9. Ajustar los valores `env:` del workflow

Abre `.github/workflows/blank.yml` y edita el bloque `env:` con tus valores reales si son distintos a los actuales:

```yaml
env:
  IMAGE_NAME: iris-api
  CONTAINER_NAME: aci-entregable4b
  ACR_NAME: acrentregable4b202606
  RESOURCE_GROUP: rg-entregable4b-github
  DNS_LABEL: aci-entregable4b        # prefijo DNS — debe ser único en Azure
  LOCATION: westeurope
  PORT: 8000
```

> El `DNS_LABEL` determina la URL pública:  
> `http://{DNS_LABEL}.{LOCATION}.azurecontainer.io:{PORT}/health`

---

## 10. Lanzar el pipeline

Haz un `push` a `main` o dispara el workflow manualmente desde **Actions → Run workflow**.

El pipeline ejecuta estos pasos en orden:
1. Instala dependencias Python
2. Entrena el modelo y comprueba que el `.joblib` existe
3. Ejecuta `pytest`
4. Login en Azure con `AZURE_CREDENTIALS`
5. Construye la imagen Docker
6. Smoke test del contenedor local (`/health`)
7. Sube la imagen a ACR con el SHA del commit como tag
8. Elimina el contenedor ACI anterior (si existe) y crea uno nuevo
9. Espera y verifica que `/health` responde en la URL pública

---

## 11. Verificar el resultado

URL pública de la API:

```
http://aci-entregable4b.westeurope.azurecontainer.io:8000/health
http://aci-entregable4b.westeurope.azurecontainer.io:8000/docs
```

Comprobar desde PowerShell:

```powershell
$URL = "http://$DNS_LABEL.$LOCATION.azurecontainer.io:$PORT"
Invoke-RestMethod "$URL/health"
Invoke-RestMethod -Method Post "$URL/predict" -ContentType "application/json" -Body '{"sepal_length":5.1,"sepal_width":3.5,"petal_length":1.4,"petal_width":0.2}'
```

Ver imágenes subidas al ACR:

```powershell
az acr repository show-tags `
  --name $ACR_NAME `
  --repository $IMAGE_NAME `
  --output table
```

Ver estado del contenedor ACI:

```powershell
az container show `
  --resource-group $RG `
  --name $CONTAINER_NAME `
  --query "{estado:instanceView.state, ip:ipAddress.ip, fqdn:ipAddress.fqdn}" `
  --output table
```

Ver logs del contenedor ACI:

```powershell
az container logs `
  --resource-group $RG `
  --name $CONTAINER_NAME
```

---

## 12. Gestionar el contenedor ACI

Parar y arrancar el contenedor evita consumir crédito cuando no se usa. La URL pública no cambia al reiniciarlo.

```powershell
# Parar (deja de facturar compute)
az container stop --resource-group $RG --name $CONTAINER_NAME

# Arrancar (tarda 30-60 segundos en estar disponible)
az container start --resource-group $RG --name $CONTAINER_NAME

# Ver estado
az container show `
  --resource-group $RG `
  --name $CONTAINER_NAME `
  --query "{estado:instanceView.state, fqdn:ipAddress.fqdn}" `
  --output table
```

---

## 13. Desarrollo local

```powershell
# Instalar dependencias
pip install -r app/requirements.txt

# Entrenar el modelo (solo la primera vez o si cambias train_model.py)
python app/train_model.py

# Arrancar la API
uvicorn app.main:app --reload --port 8000

# Ejecutar tests
python -m pytest -q
```
