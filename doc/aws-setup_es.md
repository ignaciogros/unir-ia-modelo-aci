# Guía de configuración AWS — iris-api

Esta guía te lleva desde cero hasta tener el pipeline de CI/CD funcionando con **ECR** (registro de imágenes, equivalente a ACR) y **ECS Fargate** (ejecución de contenedores sin servidor, equivalente a ACI).  
Todos los comandos usan **PowerShell** y **AWS CLI v2**.

> **¿Usas AWS Academy Learner Lab?** Esta guía es para cuentas AWS estándar. Si trabajas con un Learner Lab (credenciales temporales, sin IAM, solo `us-east-1`), usa `awsacademy-setup_es.md`.

---

## 1. Requisitos previos

- [AWS CLI v2](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) instalado
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado y en ejecución
- Cuenta AWS activa con permisos de administrador (o equivalente)
- Repositorio en GitHub con este código

---

## 2. Variables de entorno local

Define estas variables antes de ejecutar los comandos de los pasos siguientes. Deben coincidir **exactamente** con los valores `env:` del workflow.

> **CloudShell vs PowerShell:** AWS CloudShell usa bash. La sintaxis de asignación es diferente a PowerShell: sin `$` al asignar, sin espacios alrededor de `=`, y `\` para continuar líneas (no `` ` ``).

**Bash (CloudShell / Linux / macOS):**

```bash
REGION="eu-west-1"
ECR_REPO="iris-api"
ECS_CLUSTER="cluster-entregable4b"
ECS_SERVICE="svc-entregable4b"
TASK_FAMILY="task-entregable4b"
CONTAINER_NAME="iris-api"
PORT=8000
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
```

**PowerShell (Windows local):**

```powershell
$REGION         = "eu-west-1"
$ECR_REPO       = "iris-api"
$ECS_CLUSTER    = "cluster-entregable4b"
$ECS_SERVICE    = "svc-entregable4b"
$TASK_FAMILY    = "task-entregable4b"
$CONTAINER_NAME = "iris-api"
$PORT           = 8000
$AWS_ACCOUNT_ID = aws sts get-caller-identity --query Account --output text
```

---

## 3. Iniciar sesión en AWS

```powershell
aws configure
```

Introduce cuando se pida:

| Campo | Valor |
|---|---|
| AWS Access Key ID | Tu clave de acceso (IAM → Users → Security credentials) |
| AWS Secret Access Key | Tu clave secreta |
| Default region name | `eu-west-1` |
| Default output format | `json` |

Verificar que la sesión funciona:

```powershell
aws sts get-caller-identity
```

---

## 4. Crear el repositorio ECR

A diferencia de ACR (un registro con múltiples imágenes), ECR crea un repositorio por imagen.

```powershell
aws ecr create-repository `
  --repository-name $ECR_REPO `
  --region $REGION
```

El resultado incluye `repositoryUri`. Anótalo — lo usarás como prefijo de imagen en el workflow:

```
123456789012.dkr.ecr.eu-west-1.amazonaws.com/iris-api
```

---

## 5. Crear el cluster ECS

```powershell
aws ecs create-cluster `
  --cluster-name $ECS_CLUSTER `
  --region $REGION
```

---

## 6. Crear el rol de ejecución de tareas

Fargate necesita un rol IAM para descargar imágenes de ECR y escribir logs en CloudWatch. Este rol se crea **una sola vez por cuenta**.

**6.1 — Crear el rol con la política de confianza de ECS:**

```powershell
aws iam create-role `
  --role-name ecsTaskExecutionRole `
  --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{
      "Effect":"Allow",
      "Principal":{"Service":"ecs-tasks.amazonaws.com"},
      "Action":"sts:AssumeRole"
    }]
  }'
```

**6.2 — Adjuntar la política gestionada por AWS:**

```powershell
aws iam attach-role-policy `
  --role-name ecsTaskExecutionRole `
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

---

## 7. Crear el grupo de logs en CloudWatch

```powershell
aws logs create-log-group `
  --log-group-name "/ecs/$TASK_FAMILY" `
  --region $REGION
```

---

## 8. Configurar la red

**8.1 — Obtener la VPC por defecto:**

```powershell
$VPC_ID = aws ec2 describe-vpcs `
  --filters "Name=isDefault,Values=true" `
  --query "Vpcs[0].VpcId" `
  --output text `
  --region $REGION

$VPC_ID
```

**8.2 — Obtener las subredes públicas:**

```powershell
$SUBNET_IDS = aws ec2 describe-subnets `
  --filters "Name=vpc-id,Values=$VPC_ID" `
  --query "Subnets[*].SubnetId" `
  --output text `
  --region $REGION

$SUBNET_IDS
```

Anota los IDs (p. ej. `subnet-aabbccdd subnet-eeff0011`). Se necesitan uno o más.

**8.3 — Crear un grupo de seguridad:**

```powershell
$SG_ID = aws ec2 create-security-group `
  --group-name "iris-api-sg" `
  --description "Acceso HTTP a iris-api" `
  --vpc-id $VPC_ID `
  --query "GroupId" `
  --output text `
  --region $REGION

$SG_ID
```

**8.4 — Abrir el puerto de la API:**

```powershell
aws ec2 authorize-security-group-ingress `
  --group-id $SG_ID `
  --protocol tcp `
  --port $PORT `
  --cidr 0.0.0.0/0 `
  --region $REGION
```

---

## 9. Crear el archivo de definición de tarea

Crea el archivo `aws/task-definition.json` en el repositorio. Deja `AWS_ACCOUNT_ID` y `REGION` como texto literal — el workflow los sustituirá en cada ejecución derivando el número de cuenta automáticamente, así no quedan expuestos en el repositorio:

```json
{
  "family": "task-entregable4b",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::AWS_ACCOUNT_ID:role/ecsTaskExecutionRole",
  "containerDefinitions": [
    {
      "name": "iris-api",
      "image": "AWS_ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/iris-api:latest",
      "portMappings": [{ "containerPort": 8000, "protocol": "tcp" }],
      "environment": [
        { "name": "API_KEY", "value": "PLACEHOLDER" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/task-entregable4b",
          "awslogs-region": "REGION",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "essential": true
    }
  ]
}
```

> `API_KEY` y `AWS_ACCOUNT_ID` son placeholders. El workflow los reemplaza en cada despliegue antes de registrar la nueva revisión de la tarea.

Registra la definición en ECS (crea la revisión inicial). El comando sustituye los placeholders usando los valores reales de tu sesión actual:

```powershell
$AWS_ACCOUNT = aws sts get-caller-identity --query Account --output text
(Get-Content aws\task-definition.json) `
  -creplace 'AWS_ACCOUNT_ID', $AWS_ACCOUNT `
  -creplace 'REGION', $REGION |
  Set-Content aws\task-definition-resolved.json

aws ecs register-task-definition `
  --cli-input-json file://aws/task-definition-resolved.json `
  --region $REGION
```

Añade el archivo con los placeholders al repositorio (no el resuelto):

```powershell
git add aws/task-definition.json
git commit -m "Añadir definición de tarea ECS para despliegue en Fargate"
```

> No hagas `git push` todavía — el pipeline se dispararía antes de que el servicio ECS exista (paso 10) y fallaría en el despliegue. Haz el push una vez completado el paso 10.

---

## 10. Crear el servicio ECS Fargate

El servicio mantiene una réplica de la tarea en ejecución y la reemplaza si falla. `assignPublicIp=ENABLED` da IP pública a la tarea sin necesitar un balanceador de carga.

```powershell
$SUBNETS = ($SUBNET_IDS -split "\s+") -join ","

aws ecs create-service `
  --cluster $ECS_CLUSTER `
  --service-name $ECS_SERVICE `
  --task-definition $TASK_FAMILY `
  --desired-count 1 `
  --launch-type FARGATE `
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" `
  --region $REGION
```

> La tarea puede fallar al arrancar porque la imagen aún contiene el tag `latest` sin imagen real. Es normal — el primer `push` a `main` desplegará una imagen válida y el servicio se estabilizará.

---

## 11. Crear usuario IAM para GitHub Actions

**11.1 — Crear el usuario:**

```powershell
aws iam create-user --user-name github-actions-iris
```

**11.2 — Adjuntar política con los permisos mínimos necesarios:**

```powershell
$POLICY = @'
{
  "Version":"2012-10-17",
  "Statement":[
    {
      "Effect":"Allow",
      "Action":[
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload",
        "ecr:PutImage"
      ],
      "Resource":"*"
    },
    {
      "Effect":"Allow",
      "Action":[
        "ecs:RegisterTaskDefinition",
        "ecs:DescribeTaskDefinition",
        "ecs:DescribeServices",
        "ecs:UpdateService",
        "ecs:DescribeTasks",
        "ecs:ListTasks"
      ],
      "Resource":"*"
    },
    {
      "Effect":"Allow",
      "Action":"iam:PassRole",
      "Resource":"arn:aws:iam::*:role/ecsTaskExecutionRole"
    }
  ]
}
'@

aws iam put-user-policy `
  --user-name github-actions-iris `
  --policy-name GithubActionsIrisPolicy `
  --policy-document $POLICY
```

**11.3 — Crear las credenciales de acceso:**

```powershell
aws iam create-access-key --user-name github-actions-iris
```

El comando devuelve `AccessKeyId` y `SecretAccessKey`. **Copia ambos valores ahora** — la clave secreta no se puede recuperar después.

---

## 12. Añadir los secrets en GitHub

En el repositorio de GitHub:  
**Settings → Secrets and variables → Actions → New repository secret**

| Nombre | Valor |
|---|---|
| `AWS_ACCESS_KEY_ID` | `AccessKeyId` del paso anterior |
| `AWS_SECRET_ACCESS_KEY` | `SecretAccessKey` del paso anterior |
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

## 13. Ajustar el workflow AWS

**13.1 — Eliminar el token de sesión** (no necesario con credenciales permanentes IAM):

En `.github/workflows/aws.yml`, elimina la línea `aws-session-token` del paso de credenciales:

```yaml
- uses: aws-actions/configure-aws-credentials@v4
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-region: ${{ env.AWS_REGION }}
```

**13.2 — Ajustar los valores `env:`** con tus valores reales:

```yaml
env:
  AWS_REGION: eu-west-1
  ECR_REPOSITORY: iris-api
  ECS_CLUSTER: cluster-entregable4b
  ECS_SERVICE: svc-entregable4b
  TASK_DEFINITION: aws/task-definition.json
  CONTAINER_NAME: iris-api
  PORT: 8000
```

---

## 14. Lanzar el pipeline

Haz un `push` a `main` o dispara el workflow manualmente desde **Actions → Run workflow**.

El pipeline ejecuta estos pasos en orden:
1. Instala dependencias Python
2. Entrena el modelo y comprueba que el `.joblib` existe
3. Ejecuta `pytest`
4. Configura credenciales AWS (`aws-actions/configure-aws-credentials`)
5. Login en ECR (`aws ecr get-login-password | docker login`)
6. Construye la imagen Docker
7. Smoke test del contenedor local (`/health`)
8. Sube la imagen a ECR con el SHA del commit como tag
9. Inyecta la `API_KEY` del secret de GitHub en la definición de tarea (reemplaza `PLACEHOLDER` con `jq`)
10. Registra la nueva revisión de la definición de tarea en ECS
11. Actualiza el servicio ECS para usar la nueva revisión
12. Espera a que el servicio estabilice (`aws ecs wait services-stable`)
13. Obtiene la IP pública de la tarea y verifica que `/health` responde

---

## 15. Verificar el resultado

Obtener la IP pública de la tarea en ejecución:

```powershell
$TASK_ARN = aws ecs list-tasks `
  --cluster $ECS_CLUSTER `
  --service-name $ECS_SERVICE `
  --query "taskArns[0]" `
  --output text `
  --region $REGION

$ENI_ID = aws ecs describe-tasks `
  --cluster $ECS_CLUSTER `
  --tasks $TASK_ARN `
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value | [0]" `
  --output text `
  --region $REGION

$PUBLIC_IP = aws ec2 describe-network-interfaces `
  --network-interface-ids $ENI_ID `
  --query "NetworkInterfaces[0].Association.PublicIp" `
  --output text `
  --region $REGION

Write-Host "URL pública: http://$PUBLIC_IP`:$PORT"
```

Comprobar endpoints:

```powershell
Invoke-RestMethod "http://$PUBLIC_IP`:$PORT/health"
Invoke-RestMethod -Method Post "http://$PUBLIC_IP`:$PORT/predict" `
  -ContentType "application/json" `
  -Body '{"sepal_length":5.1,"sepal_width":3.5,"petal_length":1.4,"petal_width":0.2}'
```

Ver imágenes subidas a ECR:

```powershell
aws ecr describe-images `
  --repository-name $ECR_REPO `
  --region $REGION `
  --query "imageDetails[*].{tag:imageTags[0],pushed:imagePushedAt}" `
  --output table
```

Ver estado del servicio ECS:

```powershell
aws ecs describe-services `
  --cluster $ECS_CLUSTER `
  --services $ECS_SERVICE `
  --region $REGION `
  --query "services[0].{estado:status,deseadas:desiredCount,ejecutando:runningCount,pendientes:pendingCount}" `
  --output table
```

Ver logs de la tarea:

```powershell
aws logs tail "/ecs/$TASK_FAMILY" --follow --region $REGION
```

> **Diferencia con ACI:** la IP pública de Fargate cambia en cada despliegue porque la tarea se reemplaza. Para una URL estable, añade un [Application Load Balancer](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/introduction.html) al servicio ECS (añade coste mensual).

---

## 16. Gestionar el servicio Fargate

Fargate no tiene un equivalente directo a `az container stop/start`. Para evitar costes cuando no se usa, reduce el número de réplicas deseadas a cero.

```powershell
# Parar (0 réplicas — deja de facturar compute)
aws ecs update-service `
  --cluster $ECS_CLUSTER `
  --service $ECS_SERVICE `
  --desired-count 0 `
  --region $REGION

# Arrancar (1 réplica — tarda 30-60 segundos en estar disponible)
aws ecs update-service `
  --cluster $ECS_CLUSTER `
  --service $ECS_SERVICE `
  --desired-count 1 `
  --region $REGION

# Ver estado
aws ecs describe-services `
  --cluster $ECS_CLUSTER `
  --services $ECS_SERVICE `
  --region $REGION `
  --query "services[0].{estado:status,deseadas:desiredCount,ejecutando:runningCount}" `
  --output table
```

---

## 17. Desarrollo local

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
