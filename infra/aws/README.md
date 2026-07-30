# Despliegue EC2 Automatizado

Este directorio automatiza una EC2 todo-en-uno para probar el Proyecto 03:

```text
EC2 -> Docker Compose -> Kafka + PostgreSQL + Flink UI
    -> stream-c -> backend realtime -> dashboard
```

El script usa `boto3`, `user-data` y el instance profile del laboratorio
`LabInstanceProfile`.

## Requisitos

Ejecutar desde una maquina con credenciales AWS disponibles, por ejemplo una
instancia controladora del laboratorio con `LabInstanceProfile`.

```bash
pip3 install boto3 botocore
```

Antes de crear la EC2, sube los cambios actuales a GitHub, porque la instancia
clona el repositorio desde `origin/main`.

## Crear

```bash
python3 infra/aws/levantar_audiencias_ec2.py --start \
  --key-name cluster \
  --instance-profile LabInstanceProfile
```

Si ya tienes subnet o security group del laboratorio:

```bash
python3 infra/aws/levantar_audiencias_ec2.py --start \
  --key-name cluster \
  --subnet-id subnet-xxxxxxxx \
  --security-group-id sg-xxxxxxxx \
  --instance-profile LabInstanceProfile
```

## Revisar

```bash
python3 infra/aws/levantar_audiencias_ec2.py --check
```

En la EC2:

```bash
sudo tail -f /var/log/audiencias-bootstrap.log
systemctl status audiencias-stream
systemctl status audiencias-backend
systemctl status audiencias-dashboard
```

## URLs

Cuando el bootstrap termine:

```text
http://DNS_PUBLICO:3000
http://DNS_PUBLICO:8000/health
http://DNS_PUBLICO:8000/api/dashboard/snapshot
http://DNS_PUBLICO:8081
```

## Borrar

```bash
python3 infra/aws/levantar_audiencias_ec2.py --delete
```
