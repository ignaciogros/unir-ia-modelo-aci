# Guía de configuración AWS Academy — iris-api

Esta guía es específica para **AWS Academy Learner Labs**. Para una cuenta AWS estándar, usa `aws-setup_es.md`.

---

## Restricciones del Learner Lab

Antes de elegir cómo integrar el lab con GitHub Actions, conviene conocer sus limitaciones:

- **No se pueden crear usuarios IAM ni access keys permanentes** — el lab no permite este tipo de operaciones.
- **Las credenciales son temporales** — expiran al cerrar la sesión (~4 horas).
- **Solo está disponible `us-east-1`** — sustituye cualquier referencia a `eu-west-1` por `us-east-1`.
- **El rol de ejecución de tareas (`LabRole`) ya existe** — no hay que crearlo.

---

## Opciones de CI/CD con las restricciones del lab

### Opción A — Despliegue manual desde la sesión del lab

El workflow de GitHub Actions se encarga de CI (tests, build, smoke test), pero el despliegue en AWS se ejecuta manualmente desde la terminal del lab con los comandos de los pasos 8–9 de esta guía.

| | |
|---|---|
| **Ventajas** | No depende de credenciales persistentes; funciona con cualquier restricción IAM |
| **Inconvenientes** | Sin automatización del despliegue; hay que abrir el lab y ejecutar comandos a mano en cada entrega |

### Opción B — Credenciales de sesión renovadas antes de cada ejecución ✓ Recomendada

El pipeline de GitHub Actions se ejecuta completo, pero las credenciales del lab (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`) se actualizan manualmente en los secrets de GitHub al inicio de cada sesión.

| | |
|---|---|
| **Ventajas** | Pipeline de CI/CD completo en GitHub Actions; despliegue automático en Fargate |
| **Inconvenientes** | Credenciales expiran en ~4 horas; hay que actualizar tres secrets al inicio de cada sesión |

### Opción C — AWS CodePipeline (descartada)

CodePipeline + CodeBuild corre dentro de AWS y usa el `LabRole` sin credenciales persistentes, eliminando el problema de la expiración. Se descarta porque exige reemplazar GitHub Actions con infraestructura de CI/CD propia de AWS, lo que cambia sustancialmente la arquitectura del proyecto.

---

**Esta guía implementa la Opción B.** Todos los comandos usan **bash** (AWS CloudShell).

---

## 1. Credenciales

En el Learner Lab **no se usa `aws configure`**. Las credenciales son temporales y se obtienen del panel del lab.

### CloudShell (recomendado)

AWS CloudShell ya tiene las credenciales del lab configuradas automáticamente. Ábrelo desde la consola de AWS (icono de terminal en la barra superior) y verifica:

```bash
aws sts get-caller-identity
```

### Terminal local

Si prefieres ejecutar los comandos desde tu máquina, copia los valores del panel del lab (**AWS Details → AWS CLI**) y expórtalos:

```bash
export AWS_ACCESS_KEY_ID="ASIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_SESSION_TOKEN="..."
export AWS_DEFAULT_REGION="us-east-1"
```

Verifica la sesión:

```bash
aws sts get-caller-identity
```

---

## 2. Variables de entorno

Define estas variables en la misma sesión de terminal. Deben coincidir **exactamente** con los valores `env:` del workflow.

```bash
REGION="us-east-1"
ECR_REPO="iris-api"
ECS_CLUSTER="cluster-entregable4b"
ECS_SERVICE="svc-entregable4b"
TASK_FAMILY="task-entregable4b"
CONTAINER_NAME="iris-api"
PORT=8000
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
```

> El lab solo permite `us-east-1`. Usa esa región aunque la guía estándar use `eu-west-1`.

---

## 3. Crear el repositorio ECR

```bash
aws ecr create-repository \
  --repository-name $ECR_REPO \
  --region $REGION
```

El resultado incluye `repositoryUri`. Anótalo — lo usarás como prefijo de imagen en el workflow:

```
123456789012.dkr.ecr.us-east-1.amazonaws.com/iris-api
```

---

## 4. Crear el cluster ECS

```bash
aws ecs create-cluster \
  --cluster-name $ECS_CLUSTER \
  --region $REGION
```

---

## 5. Rol de ejecución de tareas

En el Learner Lab **no se puede crear un rol IAM**. El lab proporciona un rol preexistente llamado `LabRole`. 

El ARN de un rol (Amazon Resource Name) es el identificador único global de ese rol dentro de AWS.

Obtén su ARN:

```bash
aws iam get-role --role-name LabRole --query "Role.Arn" --output text
```

Anota el ARN (lo necesitarás en el paso 7):

```
arn:aws:iam::123456789012:role/LabRole
```

---

## 6. Crear el grupo de logs en CloudWatch

```bash
aws logs create-log-group \
  --log-group-name "/ecs/$TASK_FAMILY" \
  --region $REGION
```

---

## 7. Configurar la red

**7.1 — Obtener la VPC por defecto:**

```bash
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=isDefault,Values=true" \
  --query "Vpcs[0].VpcId" \
  --output text \
  --region $REGION)

echo $VPC_ID
```

**7.2 — Obtener las subredes públicas:**

```bash
SUBNET_IDS=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query "Subnets[*].SubnetId" \
  --output text \
  --region $REGION)

echo $SUBNET_IDS
```

**7.3 — Crear un grupo de seguridad:**

```bash
SG_ID=$(aws ec2 create-security-group \
  --group-name "iris-api-sg" \
  --description "Acceso HTTP a iris-api" \
  --vpc-id $VPC_ID \
  --query "GroupId" \
  --output text \
  --region $REGION)

echo $SG_ID
```

**7.4 — Abrir el puerto de la API:**

```bash
aws ec2 authorize-security-group-ingress \
  --group-id $SG_ID \
  --protocol tcp \
  --port $PORT \
  --cidr 0.0.0.0/0 \
  --region $REGION
```

---

## 8. Crear el archivo de definición de tarea

El archivo necesita existir en dos sitios con contenidos distintos:

- **En el repositorio:** con `AWS_ACCOUNT_ID` como texto literal (placeholder). El workflow lo sustituirá en cada ejecución, así el número de cuenta nunca queda expuesto en el repo.
- **En CloudShell:** con el número de cuenta real, para poder hacer el registro inicial de la tarea.

**8.1 — Crear y registrar el archivo en CloudShell:**

```bash
mkdir -p aws
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)

cat > aws/task-definition.json << EOF
{
  "family": "task-entregable4b",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT}:role/LabRole",
  "containerDefinitions": [
    {
      "name": "iris-api",
      "image": "${AWS_ACCOUNT}.dkr.ecr.us-east-1.amazonaws.com/iris-api:latest",
      "portMappings": [{ "containerPort": 8000, "protocol": "tcp" }],
      "environment": [
        { "name": "API_KEY", "value": "PLACEHOLDER" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/task-entregable4b",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "essential": true
    }
  ]
}
EOF

aws ecs register-task-definition \
  --cli-input-json file://aws/task-definition.json \
  --region $REGION
```

**8.2 — Añadir el archivo con placeholder al repositorio:**

Desde tu máquina local (o desde el editor web de GitHub en **Add file → Create new file**), crea `aws/task-definition.json` con el contenido siguiente. Deja `AWS_ACCOUNT_ID` tal cual — el workflow lo reemplaza en cada despliegue:

```json
{
  "family": "task-entregable4b",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "arn:aws:iam::AWS_ACCOUNT_ID:role/LabRole",
  "containerDefinitions": [
    {
      "name": "iris-api",
      "image": "AWS_ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/iris-api:latest",
      "portMappings": [{ "containerPort": 8000, "protocol": "tcp" }],
      "environment": [
        { "name": "API_KEY", "value": "PLACEHOLDER" }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/task-entregable4b",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "essential": true
    }
  ]
}
```

```bash
git add aws/task-definition.json
git commit -m "Añadir definición de tarea ECS para despliegue en Fargate"
```

> No hagas `git push` todavía — el pipeline se dispararía antes de que el servicio ECS exista (paso 9) y fallaría en el despliegue. Haz el push una vez completado el paso 9.

---

## 9. Crear el servicio ECS Fargate

```bash
SUBNETS=$(echo $SUBNET_IDS | tr ' ' ',')

aws ecs create-service \
  --cluster $ECS_CLUSTER \
  --service-name $ECS_SERVICE \
  --task-definition $TASK_FAMILY \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNETS],securityGroups=[$SG_ID],assignPublicIp=ENABLED}" \
  --region $REGION
```

> La tarea puede fallar al arrancar porque aún no hay imagen válida en ECR. Es normal — el primer `push` a `main` desplegará la imagen y el servicio se estabilizará.

---

## 10. Añadir los secrets en GitHub

En el repositorio de GitHub:  
**Settings → Secrets and variables → Actions → New repository secret**

| Nombre | Valor |
|---|---|
| `AWS_ACCESS_KEY_ID` | Del panel del lab (AWS Details → AWS CLI) |
| `AWS_SECRET_ACCESS_KEY` | Del panel del lab |
| `AWS_SESSION_TOKEN` | Del panel del lab |
| `API_KEY` | Clave aleatoria para proteger `/predict` |

Generar la `API_KEY`:

```bash
openssl rand -hex 32
```

> **Las tres credenciales AWS expiran en ~4 horas.** Antes de cada ejecución del pipeline hay que actualizarlas — ver paso 14.

---

## 11. Configurar el workflow para el token de sesión

El workflow debe pasar el `AWS_SESSION_TOKEN` a la acción de credenciales. En `.github/workflows/aws.yml`, el paso de configuración debe incluir:

```yaml
- uses: aws-actions/configure-aws-credentials@v4
  with:
    aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
    aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    aws-session-token: ${{ secrets.AWS_SESSION_TOKEN }}
    aws-region: ${{ env.AWS_REGION }}
```

---

## 12. Ajustar los valores `env:` del workflow

Edita el bloque `env:` del workflow con tus valores reales:

```yaml
env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: iris-api
  ECS_CLUSTER: cluster-entregable4b
  ECS_SERVICE: svc-entregable4b
  TASK_DEFINITION: aws/task-definition.json
  CONTAINER_NAME: iris-api
  PORT: 8000
```

---

## 13. Lanzar el pipeline

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

## 14. Renovar credenciales antes de cada sesión

Las credenciales del lab expiran en ~4 horas. Al inicio de cada nueva sesión de lab:

1. Abre el lab y haz clic en **AWS Details → AWS CLI**
2. Copia los tres valores (`aws_access_key_id`, `aws_secret_access_key`, `aws_session_token`)
3. En GitHub: **Settings → Secrets and variables → Actions**
4. Actualiza los tres secrets: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`

Solo entonces lanza el pipeline — si los secrets han expirado, el workflow fallará en el paso de autenticación con AWS.

---

## 15. Verificar el resultado

**No hay URL estática.** A diferencia de Azure ACI (que asigna un FQDN fijo como `iris-api.westeurope.azurecontainer.io`), Fargate asigna una IP pública nueva en cada despliegue porque la tarea se reemplaza. Para una URL estable se necesitaría un Application Load Balancer, que tiene coste mensual.

La URL se obtiene de dos formas:

**Automática** — el pipeline la imprime al final de cada ejecución exitosa. En GitHub: **Actions → último run → paso "Verificar endpoint ECS desplegado"**:
```
API desplegada correctamente en http://1.2.3.4:8000
```

**Manual** — ejecuta en CloudShell (requiere tener las variables del paso 2 definidas):

```bash
TASK_ARN=$(aws ecs list-tasks \
  --cluster $ECS_CLUSTER \
  --service-name $ECS_SERVICE \
  --query "taskArns[0]" \
  --output text \
  --region $REGION)

ENI_ID=$(aws ecs describe-tasks \
  --cluster $ECS_CLUSTER \
  --tasks $TASK_ARN \
  --query "tasks[0].attachments[0].details[?name=='networkInterfaceId'].value | [0]" \
  --output text \
  --region $REGION)

PUBLIC_IP=$(aws ec2 describe-network-interfaces \
  --network-interface-ids $ENI_ID \
  --query "NetworkInterfaces[0].Association.PublicIp" \
  --output text \
  --region $REGION)

echo "URL pública: http://$PUBLIC_IP:$PORT"
```

Comprobar endpoints:

```bash
curl "http://$PUBLIC_IP:$PORT/health"
curl -X POST "http://$PUBLIC_IP:$PORT/predict" \
  -H "Content-Type: application/json" \
  -d '{"sepal_length":5.1,"sepal_width":3.5,"petal_length":1.4,"petal_width":0.2}'
```

---

## 16. Gestionar el servicio Fargate

Parar el servicio evita consumir crédito cuando no se usa. A diferencia de ACI, **la IP pública cambia al reiniciarlo** — Fargate crea una tarea nueva con una IP nueva. Obtén la URL actualizada desde los logs del pipeline o con los comandos del paso 15.

```bash
# Parar (0 réplicas — deja de facturar compute)
aws ecs update-service \
  --cluster $ECS_CLUSTER \
  --service $ECS_SERVICE \
  --desired-count 0 \
  --region $REGION

# Arrancar (1 réplica — tarda 30-60 segundos en estar disponible)
aws ecs update-service \
  --cluster $ECS_CLUSTER \
  --service $ECS_SERVICE \
  --desired-count 1 \
  --region $REGION

# Ver estado
aws ecs describe-services \
  --cluster $ECS_CLUSTER \
  --services $ECS_SERVICE \
  --region $REGION \
  --query "services[0].{estado:status,deseadas:desiredCount,ejecutando:runningCount}" \
  --output table
```

Ver logs:

```bash
aws logs tail "/ecs/$TASK_FAMILY" --follow --region $REGION
```
