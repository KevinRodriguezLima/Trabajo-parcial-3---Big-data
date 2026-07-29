# Despliegue en AWS — Parte C (Flink Jobs)

Para la guía detallada paso a paso del despliegue en un cluster de AWS (Amazon MSK, Managed Service for Apache Flink / EKS, Amazon RDS y Amazon S3), por favor consulta la documentación completa en:

👉 **[docs/aws_deployment_guide.md](Trabajo-parcial-3---Big-data/docs/aws_deployment_guide.md)**

## Resumen Ejecutivo del Despliegue AWS:

1. **Broker Managed Kafka**: **Amazon MSK** (Cluster en 3 subredes privadas con replicación en 3 AZs).
2. **Motor PyFlink**: **AWS Managed Service for Apache Flink** (o Flink Operator sobre **Amazon EKS**).
3. **Persistencia de Métricas/Audiencias**: **Amazon RDS PostgreSQL** (o Aurora Serverless v2).
4. **State Backend (Checkpoints/Savepoints)**: **Amazon S3**.
5. **Configuración de Variables de Entorno**:
   - `KAFKA_BOOTSTRAP_INTERNAL`: Endpoints de Amazon MSK.
   - `POSTGRES_HOST`: Endpoint del cluster RDS/Aurora.
   - `WIN_*_SEC` & `AUD_*`: Parámetros de ventanas y umbrales parametrizables.
