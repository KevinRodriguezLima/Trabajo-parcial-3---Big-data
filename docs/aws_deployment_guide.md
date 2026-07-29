# Guía de Despliegue en AWS: Plataforma de Procesamiento Flink en Tiempo Real

Este documento describe la arquitectura de producción y el procedimiento paso a paso para desplegar el job de procesamiento PyFlink (Parte C), Kafka (Parte B) y la base de datos de persistencia en la nube de **Amazon Web Services (AWS)**.

---

## 1. Arquitectura de Despliegue en AWS

```text
[ Simulador / Agente Digital ]
             │ (HTTPS / Producer API)
             ▼
[ Amazon MSK (Managed Streaming for Kafka) ]
  ├── user-events (4 partitions)
  ├── purchase-events (2 partitions)
  ├── iot-events (2 partitions)
  └── system-events (1 partition)
             │
             ▼
[ AWS Managed Service for Apache Flink (Kinesis Data Analytics) ]
   OR [ Amazon EKS + Flink K8s Operator ]
  ├── PyFlink Stream Execution (Watermarks + Windows)
  ├── State Backend: Amazon S3 (Checkpoints & Savepoints)
             │
             ├─────────────────────────────────────────┐
             ▼                                         ▼
[ Amazon MSK Output Topics ]             [ Amazon RDS PostgreSQL / Aurora ]
  ├── metrics.*                             ├── flink_metrics
  ├── audiences.classifications             ├── audience_classifications
  └── alerts.anomalies                      └── alerts_anomalies
             │                                         │
             └────────────────────┬────────────────────┘
                                  ▼
                     [ Parte D: Dashboard Service ]
                     (AWS App Runner / ECS Fargate)
```

---

## 2. Componentes y Servicios AWS Utilizados

| Componente | Servicio AWS recomendado | Configuración / Descripción |
|---|---|---|
| **Broker de Ingesta & Salida** | **Amazon MSK** | Kafka 3.x / 4.x administrado con KRaft o ZooKeeper en 3 AZs. |
| **Motor de Stream Processing** | **Amazon Managed Service for Apache Flink** | Entorno serverless administrado para PyFlink 2.3+ |
| **Almacenamiento de Estado** | **Amazon S3** | Bucket S3 para guardar checkpoints y savepoints de Flink. |
| **Persistencia Relacional** | **Amazon RDS PostgreSQL** o **Aurora Serverless v2** | Almacena las tablas de `init-db.sql` con alta disponibilidad. |
| **Secretos & Conexiones** | **AWS Secrets Manager** | Guarda credenciales de base de datos y VPC endpoints de MSK. |
| **Monitorización** | **Amazon CloudWatch** | Logs, métricas de CPU/RAM, throughput y alarmas. |

---

## 3. Guía de Despliegue Paso a Paso

### Paso 1: Configurar la VPC y Seguridad

1. Crear una **VPC dedicada** con:
   - 3 subredes privadas (para MSK y Flink)
   - 2 subredes públicas (para NAT Gateway / ALB)
2. Crear un Security Group `sg-flink-processor` que permita:
   - Salida e ingreso al puerto `9092` / `9096` (MSK)
   - Salida al puerto `5432` (RDS PostgreSQL)

---

### Paso 2: Desplegar Amazon MSK (Kafka)

1. En la consola de AWS MSK, crear un cluster con las siguientes características:
   - **Nombre del cluster**: `audiencias-msk-cluster`
   - **Broker Type**: `kafka.m5.large` (o `kafka.t3.small` para pruebas).
   - **Número de brokers**: 3 (uno por AZ).
2. Crear los topics requeridos según `contracts/topics.yaml`:

```bash
# Conectarse a una instancia EC2 Bastion en la VPC y ejecutar:
export BS="b-1.audiencias-msk...:9092,b-2.audiencias-msk...:9092"

# Topics de Ingesta
kafka-topics.sh --bootstrap-server $BS --create --topic user-events --partitions 4 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --create --topic purchase-events --partitions 2 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --create --topic iot-events --partitions 2 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --create --topic system-events --partitions 1 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --create --topic dead-letter --partitions 1 --replication-factor 3

# Topics de Salida C -> D
kafka-topics.sh --bootstrap-server $BS --create --topic metrics.throughput --partitions 1 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --create --topic metrics.active-users --partitions 1 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --create --topic metrics.events-by-type --partitions 1 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --create --topic metrics.top-products-viewed --partitions 1 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --create --topic metrics.top-products-purchased --partitions 1 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --create --topic metrics.purchases-by-region --partitions 1 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --create --topic metrics.conversion --partitions 1 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --create --topic metrics.trends --partitions 1 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --create --topic audiences.classifications --partitions 2 --replication-factor 3
kafka-topics.sh --bootstrap-server $BS --create --topic alerts.anomalies --partitions 1 --replication-factor 3
```

---

### Paso 3: Crear la Base de Datos Amazon RDS PostgreSQL

1. Crear una instancia de **Amazon RDS PostgreSQL 15+** o **Aurora Serverless v2**.
2. Ejecutar el script `infra/init-db.sql` para inicializar el esquema:

```bash
psql -h audiencias-db.xxxxxx.us-east-1.rds.amazonaws.com -U audiencias -d audiencias -f infra/init-db.sql
```

---

### Paso 4: Empaquetar el Proyecto PyFlink para AWS

1. Crear un Bucket de Amazon S3: `s3://audiencias-flink-artifacts-production`
2. Empaquetar los archivos de la Parte C en un archivo `.zip`:

```bash
cd flink-jobs
zip -r flink-job-app.zip src/ requirements.txt README.md
aws s3 cp flink-job-app.zip s3://audiencias-flink-artifacts-production/code/flink-job-app.zip
```

---

### Paso 5: Desplegar en Amazon Managed Service for Apache Flink

1. Ir a **Amazon Kinesis Data Analytics / Managed Apache Flink**.
2. Crear una nueva aplicación PyFlink:
   - **Runtime**: `Apache Flink 1.18` / `2.0` (Python 3.11).
   - **Service Execution Role**: Rol IAM con políticas `AmazonMSKFullAccess`, `AmazonS3FullAccess` para el bucket de checkpoints, y acceso VPC.
   - **Application Code**: Apuntar a `s3://audiencias-flink-artifacts-production/code/flink-job-app.zip` y como entrypoint `src/main.py`.
3. Configurar **Variables de Entorno de la Aplicación**:

| Clave | Valor Ejemplo |
|---|---|
| `KAFKA_BOOTSTRAP_INTERNAL` | `b-1.audiencias-msk...:9092,b-2.audiencias-msk...:9092` |
| `POSTGRES_HOST` | `audiencias-db.xxxxxx.us-east-1.rds.amazonaws.com` |
| `POSTGRES_PORT` | `5432` |
| `POSTGRES_DB` | `audiencias` |
| `POSTGRES_USER` | `audiencias` |
| `POSTGRES_PASSWORD` | `{{resolve:secretsmanager:audiencias-db-secret:SecretString:password}}` |
| `WIN_THROUGHPUT_SEC` | `10` |
| `WIN_ACTIVE_USERS_SEC` | `60` |

4. Activar **Checkpointing Automático**:
   - Checkpoint Interval: `10000 ms` (10 segundos).
   - Checkpointing Path: `s3://audiencias-flink-artifacts-production/checkpoints/`
   - Savepoint Path: `s3://audiencias-flink-artifacts-production/savepoints/`

5. Hacer clic en **Run / Start Application**.

---

## 4. Estrategia Alternativa: Despliegue en Amazon EKS (Kubernetes)

Si la organización prefiere Kubernetes:

1. Instalar el **Flink Kubernetes Operator** en EKS via Helm:
   ```bash
   helm repo add flink-operator-repo https://downloads.apache.org/flink/flink-kubernetes-operator-1.8.0/
   helm install flink-kubernetes-operator flink-operator-repo/flink-kubernetes-operator
   ```
2. Aplicar el Manifiesto `FlinkDeployment`:

```yaml
apiVersion: flink.apache.org/v1beta1
kind: FlinkDeployment
metadata:
  name: audiencias-flink-pipeline
spec:
  image: apache/flink:2.3.0-scala_2.12-java17
  flinkVersion: v1_18
  flinkConfiguration:
    taskmanager.numberOfTaskSlots: "4"
    state.checkpoints.dir: s3://audiencias-flink-artifacts-production/checkpoints
  serviceAccount: flink
  jobManager:
    resource:
      memory: "2048m"
      cpu: 1
  taskManager:
    resource:
      memory: "4096m"
      cpu: 2
  job:
    jarURI: local:///opt/flink/opt/flink-python_2.12-2.3.0.jar
    entryClass: "org.apache.flink.client.python.PythonDriver"
    args: ["-py", "/opt/flink/jobs/src/main.py"]
    parallelism: 2
    upgradeMode: statemaximum
```

---

## 5. Alta Disponibilidad, Escalado y Operaciones

1. **Auto-Escalado (Parallelism & TaskSlots)**:
   - Para un volumen alto de eventos (ej. 10,000 ev/s en escenario Cyber Monday), incrementar la KPU (Kinesis Processing Unit) o el número de TaskManagers a 4 o 8.
   - Aumentar las particiones del topic Kafka `user-events` a 8.

2. **Savepoints antes de Cambios de Código**:
   - Ejecutar un savepoint manual en S3 antes de realizar upgrades:
     ```bash
     aws kinesisanalyticsv2 create-application-snapshot --application-name audiencias-flink --snapshot-name release-v1.1
     ```

3. **Monitoreo con Amazon CloudWatch**:
   - Monitorear `fullRestarts`, `numRecordsInPerSecond`, `numRecordsOutPerSecond` y `lastCheckpointDuration`.
   - Configurar una alarma CloudWatch si `fullRestarts > 0` o si la latencia excede los 30 segundos.
