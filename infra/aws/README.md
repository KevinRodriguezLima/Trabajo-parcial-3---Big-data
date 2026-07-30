# Despliegue EC2 Automatizado

Este directorio automatiza una EC2 todo-en-uno para probar el Proyecto 03:

```text
EC2 -> Docker Compose -> Kafka + PostgreSQL + Flink UI
    -> stream-c -> backend realtime -> dashboard
```

El script usa `boto3`, `user-data` y el instance profile del laboratorio
`LabInstanceProfile`. Al crear la instancia tambien verifica que el Security
Group tenga abiertos los puertos `3000`, `8000` y `8081`.

## Requisitos

Ejecutar desde una maquina con credenciales AWS disponibles, por ejemplo una
instancia controladora del laboratorio con `LabInstanceProfile`.

```bash
pip3 install boto3 botocore
```

Antes de crear la EC2, sube los cambios actuales a GitHub, porque la instancia
clona el repositorio desde `origin/main`.

## Crear

### Opcion todo-en-uno

```bash
python3 infra/aws/levantar_audiencias_ec2.py --start \
  --key-name cluster \
  --instance-profile LabInstanceProfile
```

El script lee por defecto `infra/aws/config.py`, que ya contiene:

```python
REGION = "us-east-1"
AMI_ID = "ami-03f4fd1e8233bd64d"
KEY_NAME = "cluster"
SECURITY_GROUP_ID = "sg-00c82fc157b6a0478"
SUBNET_ID = "subnet-0346fd19f61aafdcd"
TIPO_INSTANCIA = "t3.large"
INSTANCE_PROFILE = "LabInstanceProfile"
```

Con esa configuracion, basta:

```bash
python3 infra/aws/levantar_audiencias_ec2.py --start
```

### Opcion distribuida

El despliegue distribuido crea 3 instancias:

```text
DATA     -> Kafka + PostgreSQL + Kafka UI
APP      -> event-store + procesamiento streaming + backend + dashboard
PRODUCER -> simulador + productores Kafka continuos
```

```bash
python3 infra/aws/levantar_audiencias_distribuido.py --start
```

Por defecto usa `t3.large` para `DATA` y `APP`, y `t3.small` para `PRODUCER`.
El productor publica lotes de 20000 eventos a 200 eventos/s en bucle, asi que
el dashboard sigue recibiendo snapshots en tiempo real por SSE.

Para ajustar la tasa:

```bash
python3 infra/aws/levantar_audiencias_distribuido.py --start \
  --producer-rate 200 \
  --producer-limit 20000
```

Si quieres sobrescribir subnet o security group del laboratorio:

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

Para el modo distribuido:

```bash
python3 infra/aws/levantar_audiencias_distribuido.py --check
```

En la EC2:

```bash
sudo tail -f /var/log/audiencias-bootstrap.log
systemctl status audiencias-stream
systemctl status audiencias-backend
systemctl status audiencias-dashboard
```

En el modo distribuido:

```bash
# DATA
sudo tail -f /var/log/audiencias-data-bootstrap.log

# APP
sudo tail -f /var/log/audiencias-app-bootstrap.log
systemctl status audiencias-event-store audiencias-stream audiencias-backend audiencias-dashboard

# PRODUCER
sudo tail -f /var/log/audiencias-producer-bootstrap.log
systemctl status audiencias-producer
```

## URLs

Cuando el bootstrap termine:

```text
http://DNS_PUBLICO:3000
http://DNS_PUBLICO:8000/health
http://DNS_PUBLICO:8000/api/dashboard/snapshot
http://DNS_PUBLICO:8081
```

El dashboard queda configurado automaticamente con el DNS/IP publico de EC2 para
conectarse al backend realtime por SSE.

## Borrar

```bash
python3 infra/aws/levantar_audiencias_ec2.py --delete
```

Para borrar solo las instancias distribuidas:

```bash
python3 infra/aws/levantar_audiencias_distribuido.py --delete
```
