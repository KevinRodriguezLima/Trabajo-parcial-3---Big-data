#!/usr/bin/env python3
"""Crea una EC2 todo-en-uno para probar la plataforma de audiencias digitales.

Usa boto3, user-data y el instance profile del laboratorio para automatizar:
Docker Compose, Kafka, Postgres, Flink local, procesador C, backend realtime y
dashboard.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

try:
    from config import (  # type: ignore
        AMI_ID,
        INSTANCE_PROFILE,
        KEY_NAME,
        REGION,
        SECURITY_GROUP_ID,
        SUBNET_ID,
        TIPO_INSTANCIA,
    )
except ImportError:
    AMI_ID = None
    INSTANCE_PROFILE = "LabInstanceProfile"
    KEY_NAME = "cluster"
    REGION = "us-east-1"
    SECURITY_GROUP_ID = None
    SUBNET_ID = None
    TIPO_INSTANCIA = "t3.small"

PROJECT_TAG = "Audiencias-BigData-Proyecto03"
USER_DATA_PATH = Path(__file__).resolve().parent / "user_data_all_in_one.sh"


def client(region: str):
    return boto3.client("ec2", region_name=region)


def resource(region: str):
    return boto3.resource("ec2", region_name=region)


def tags_base(name: str, run_id: str) -> list[dict[str, str]]:
    return [
        {"Key": "Name", "Value": name},
        {"Key": "Proyecto", "Value": PROJECT_TAG},
        {"Key": "Rol", "Value": "AllInOne"},
        {"Key": "ClusterRun", "Value": run_id},
    ]


def default_vpc_id(ec2_client) -> str:
    response = ec2_client.describe_vpcs(Filters=[{"Name": "is-default", "Values": ["true"]}])
    vpcs = response.get("Vpcs", [])
    if not vpcs:
        raise SystemExit("No se encontro VPC default. Pasa --vpc-id o --subnet-id.")
    return vpcs[0]["VpcId"]


def vpc_from_subnet(ec2_client, subnet_id: str) -> str:
    response = ec2_client.describe_subnets(SubnetIds=[subnet_id])
    return response["Subnets"][0]["VpcId"]


def ensure_security_group(ec2_client, *, vpc_id: str, ssh_cidr: str) -> str:
    name = "audiencias-proyecto03-sg"
    existing = ec2_client.describe_security_groups(
        Filters=[
            {"Name": "group-name", "Values": [name]},
            {"Name": "vpc-id", "Values": [vpc_id]},
        ]
    ).get("SecurityGroups", [])
    if existing:
        return existing[0]["GroupId"]

    response = ec2_client.create_security_group(
        GroupName=name,
        Description="Proyecto 03 Big Data: dashboard, backend y UIs",
        VpcId=vpc_id,
        TagSpecifications=[
            {
                "ResourceType": "security-group",
                "Tags": [
                    {"Key": "Name", "Value": name},
                    {"Key": "Proyecto", "Value": PROJECT_TAG},
                ],
            }
        ],
    )
    sg_id = response["GroupId"]
    permissions = [
        {"IpProtocol": "tcp", "FromPort": 22, "ToPort": 22, "IpRanges": [{"CidrIp": ssh_cidr, "Description": "SSH"}]},
        {"IpProtocol": "tcp", "FromPort": 3000, "ToPort": 3000, "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "Dashboard"}]},
        {"IpProtocol": "tcp", "FromPort": 8000, "ToPort": 8000, "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "Backend realtime"}]},
        {"IpProtocol": "tcp", "FromPort": 8080, "ToPort": 8081, "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "Kafka/Flink UI"}]},
    ]
    try:
        ec2_client.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=permissions)
    except ClientError as exc:
        if "InvalidPermission.Duplicate" not in str(exc):
            raise
    return sg_id


def ensure_project_ingress(ec2_client, sg_id: str) -> None:
    permissions = [
        {"IpProtocol": "tcp", "FromPort": 3000, "ToPort": 3000, "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "Dashboard"}]},
        {"IpProtocol": "tcp", "FromPort": 8000, "ToPort": 8000, "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "Backend realtime"}]},
        {"IpProtocol": "tcp", "FromPort": 8081, "ToPort": 8081, "IpRanges": [{"CidrIp": "0.0.0.0/0", "Description": "Flink UI"}]},
    ]
    for permission in permissions:
        port = permission["FromPort"]
        try:
            ec2_client.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=[permission])
            print(f"Puerto publico abierto: {port}")
        except ClientError as exc:
            if "InvalidPermission.Duplicate" in str(exc):
                print(f"Puerto publico ya abierto: {port}")
                continue
            raise


def latest_amazon_linux_2023(ec2_client) -> str:
    images = ec2_client.describe_images(
        Owners=["amazon"],
        Filters=[
            {"Name": "name", "Values": ["al2023-ami-2023*-x86_64"]},
            {"Name": "architecture", "Values": ["x86_64"]},
            {"Name": "virtualization-type", "Values": ["hvm"]},
            {"Name": "root-device-type", "Values": ["ebs"]},
        ],
    )["Images"]
    if not images:
        raise SystemExit("No se encontro AMI Amazon Linux 2023; pasa --ami-id.")
    images.sort(key=lambda img: img["CreationDate"], reverse=True)
    return images[0]["ImageId"]


def render_user_data(repo_url: str, branch: str) -> str:
    template = USER_DATA_PATH.read_text(encoding="utf-8")
    return template.replace("__REPO_URL__", repo_url).replace("__BRANCH__", branch)


def listar(region: str) -> list[Any]:
    ec2 = resource(region)
    return list(
        ec2.instances.filter(
            Filters=[
                {"Name": "tag:Proyecto", "Values": [PROJECT_TAG]},
                {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]},
            ]
        )
    )


def crear(args: argparse.Namespace) -> None:
    ec2_client = client(args.region)
    ec2_resource = resource(args.region)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    ami_id = args.ami_id or latest_amazon_linux_2023(ec2_client)

    if args.security_group_id:
        sg_id = args.security_group_id
    else:
        vpc_id = args.vpc_id
        if args.subnet_id:
            vpc_id = vpc_from_subnet(ec2_client, args.subnet_id)
        if not vpc_id:
            vpc_id = default_vpc_id(ec2_client)
        sg_id = ensure_security_group(ec2_client, vpc_id=vpc_id, ssh_cidr=args.ssh_cidr)
    ensure_project_ingress(ec2_client, sg_id)
    name = f"Audiencias-Proyecto03-{run_id}"
    print(f"Creando EC2 {name} en {args.region}")
    print(f"AMI={ami_id} tipo={args.instance_type} SG={sg_id} subnet={args.subnet_id or '(default)'}")

    params: dict[str, Any] = {
        "ImageId": ami_id,
        "MinCount": 1,
        "MaxCount": 1,
        "InstanceType": args.instance_type,
        "SecurityGroupIds": [sg_id],
        "UserData": render_user_data(args.repo_url, args.branch),
        "IamInstanceProfile": {"Name": args.instance_profile},
        "BlockDeviceMappings": [
            {
                "DeviceName": "/dev/xvda",
                "Ebs": {
                    "VolumeSize": args.volume_size,
                    "VolumeType": "gp3",
                    "DeleteOnTermination": True,
                },
            }
        ],
        "TagSpecifications": [
            {"ResourceType": "instance", "Tags": tags_base(name, run_id)},
        ],
    }
    if args.key_name:
        params["KeyName"] = args.key_name
    if args.subnet_id:
        params["SubnetId"] = args.subnet_id

    inst = ec2_resource.create_instances(**params)[0]
    inst.wait_until_running()
    inst.reload()

    print("\nInstancia creada.")
    print(f"ID: {inst.id}")
    print(f"IP publica: {inst.public_ip_address}")
    print(f"DNS publico: {inst.public_dns_name}")
    print(f"IP privada: {inst.private_ip_address}")
    print("\nEspera 8-15 minutos y revisa:")
    print(f"  ssh -i ~/.ssh/{args.key_name}.pem ec2-user@{inst.public_dns_name}")
    print("  sudo tail -f /var/log/audiencias-bootstrap.log")
    print("\nURLs:")
    print(f"  Dashboard: http://{inst.public_dns_name}:3000")
    print(f"  Backend:   http://{inst.public_dns_name}:8000/health")
    print(f"  Snapshot:  http://{inst.public_dns_name}:8000/api/dashboard/snapshot")
    print(f"  Flink UI:  http://{inst.public_dns_name}:8081")
    print("\nPara listar o borrar:")
    print("  python infra/aws/levantar_audiencias_ec2.py --check")
    print("  python infra/aws/levantar_audiencias_ec2.py --delete")


def verificar(region: str) -> None:
    instancias = listar(region)
    if not instancias:
        print("No hay instancias de este proyecto.")
        return
    for inst in instancias:
        inst.reload()
        tags = {tag["Key"]: tag["Value"] for tag in inst.tags or []}
        print(
            f"{inst.id} | {tags.get('Name', 'SinName')} | {inst.state['Name']} | "
            f"publica={inst.public_dns_name} | privada={inst.private_ip_address}"
        )


def borrar(region: str) -> None:
    instancias = listar(region)
    ids = [inst.id for inst in instancias]
    if not ids:
        print("No hay instancias para terminar.")
        return
    print(f"Terminando: {' '.join(ids)}")
    resource(region).instances.filter(InstanceIds=ids).terminate()


def main() -> None:
    parser = argparse.ArgumentParser(description="Automatiza el despliegue EC2 del Proyecto 03 Big Data")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", action="store_true", help="Crea una EC2 todo-en-uno")
    group.add_argument("--check", action="store_true", help="Lista instancias creadas por este script")
    group.add_argument("--delete", action="store_true", help="Termina instancias creadas por este script")

    parser.add_argument("--region", default=REGION)
    parser.add_argument("--ami-id", default=AMI_ID, help="AMI; si se omite usa Amazon Linux 2023 reciente")
    parser.add_argument("--instance-type", default=TIPO_INSTANCIA)
    parser.add_argument("--volume-size", type=int, default=50)
    parser.add_argument("--key-name", default=KEY_NAME, help="KeyPair EC2, sin .pem")
    parser.add_argument("--security-group-id", default=SECURITY_GROUP_ID, help="Usa un SG existente")
    parser.add_argument("--subnet-id", default=SUBNET_ID)
    parser.add_argument("--vpc-id", default=None)
    parser.add_argument("--ssh-cidr", default="0.0.0.0/0", help="CIDR permitido para SSH si se crea SG")
    parser.add_argument("--instance-profile", default=INSTANCE_PROFILE)
    parser.add_argument("--repo-url", default="https://github.com/KevinRodriguezLima/Trabajo-parcial-3---Big-data.git")
    parser.add_argument("--branch", default="main")

    args = parser.parse_args()
    if args.start:
        crear(args)
    elif args.check:
        verificar(args.region)
    elif args.delete:
        borrar(args.region)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
