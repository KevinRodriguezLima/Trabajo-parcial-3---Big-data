# ==============================================================================
# config.py - Configuracion de Infraestructura AWS
# ==============================================================================

# IMPORTANTE: Reemplaza estos valores si cambias de laboratorio/cuenta AWS.
REGION = "us-east-1"
AMI_ID = "ami-03f4fd1e8233bd64d"              # Amazon Linux
KEY_NAME = "cluster"                          # Nombre de la llave .pem, sin .pem
SECURITY_GROUP_ID = "sg-00c82fc157b6a0478"    # Security Group del laboratorio
SUBNET_ID = "subnet-0346fd19f61aafdcd"        # Subred del laboratorio
TIPO_INSTANCIA = "t3.small"                   # Tipo de instancia usado en tu lab

# Usuario por defecto para Amazon Linux.
USUARIO_SSH = "ec2-user"

# Rol/perfil IAM del laboratorio.
INSTANCE_PROFILE = "LabInstanceProfile"
