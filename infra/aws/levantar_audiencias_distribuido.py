#!/usr/bin/env python3
"""Crea un despliegue distribuido EC2 para el Proyecto 03 Big Data.

Topologia:
- DATA: Kafka + PostgreSQL + Kafka UI.
- APP: consumidor event-store + procesador streaming + backend realtime + dashboard.
- PRODUCER: simulador y producers Kafka en bucle continuo.
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
    TIPO_INSTANCIA = "t3.large"


PROJECT_TAG = "Audiencias-BigData-Proyecto03"
DISTRIBUTED_TAG = "Distributed"
TEMPLATE_DIR = Path(__file__).resolve().parent
ROLE_TEMPLATES = {
    "data": TEMPLATE_DIR / "user_data_distributed_data.sh",
    "app": TEMPLATE_DIR / "user_data_distributed_app.sh",
    "producer": TEMPLATE_DIR / "user_data_distributed_producer.sh",
}


def client(region: str):
    return boto3.client("ec2", region_name=region)


def resource(region: str):
    return boto3.resource("ec2", region_name=region)


def tags_base(name: str, run_id: str, role: str) -> list[dict[str, str]]:
    return [
        {"Key": "Name", "Value": name},
        {"Key": "Proyecto", "Value": PROJECT_TAG},
        {"Key": "Modo", "Value": DISTRIBUTED_TAG},
        {"Key": "Rol", "Value": role},
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
    name = "audiencias-proyecto03-distribuido-sg"
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
        Description="Proyecto 03 Big Data distribuido",
        VpcId=vpc_id,
        TagSpecifications=[
            {
                "ResourceType": "security-group",
                "Tags": [
                    {"Key": "Name", "Value": name},
                    {"Key": "Proyecto", "Value": PROJECT_TAG},
                    {"Key": "Modo", "Value": DISTRIBUTED_TAG},
                ],
            }
        ],
    )
    sg_id = response["GroupId"]
    ensure_distributed_ingress(ec2_client, sg_id=sg_id, ssh_cidr=ssh_cidr)
    return sg_id


def allow_ingress(ec2_client, sg_id: str, permission: dict[str, Any], label: str) -> None:
    try:
        ec2_client.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=[permission])
        print(f"Regla abierta: {label}")
    except ClientError as exc:
        if "InvalidPermission.Duplicate" in str(exc):
            print(f"Regla ya existia: {label}")
            return
        raise


def ensure_distributed_ingress(ec2_client, *, sg_id: str, ssh_cidr: str) -> None:
    public_ports = [
        (22, ssh_cidr, "SSH"),
        (3000, "0.0.0.0/0", "Dashboard"),
        (8000, "0.0.0.0/0", "Backend realtime"),
        (8080, "0.0.0.0/0", "Kafka UI"),
        (8081, "0.0.0.0/0", "Flink UI"),
    ]
    for port, cidr, description in public_ports:
        allow_ingress(
            ec2_client,
            sg_id,
            {
                "IpProtocol": "tcp",
                "FromPort": port,
                "ToPort": port,
                "IpRanges": [{"CidrIp": cidr, "Description": description}],
            },
            f"{description} {port} desde {cidr}",
        )

    internal_ports = [
        (29092, "Kafka entre instancias"),
        (5432, "PostgreSQL entre instancias"),
    ]
    for port, description in internal_ports:
        allow_ingress(
            ec2_client,
            sg_id,
            {
                "IpProtocol": "tcp",
                "FromPort": port,
                "ToPort": port,
                "UserIdGroupPairs": [{"GroupId": sg_id, "Description": description}],
            },
            f"{description} {port} desde el mismo SG",
        )


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


def render_user_data(role: str, replacements: dict[str, str]) -> str:
    template = ROLE_TEMPLATES[role].read_text(encoding="utf-8")
    for key, value in replacements.items():
        template = template.replace(f"__{key}__", value)
    return template


def create_instance(
    *,
    ec2_resource,
    args: argparse.Namespace,
    ami_id: str,
    sg_id: str,
    run_id: str,
    role: str,
    user_data: str,
    instance_type: str,
) -> Any:
    name = f"Audiencias-{role}-{run_id}"
    params: dict[str, Any] = {
        "ImageId": ami_id,
        "MinCount": 1,
        "MaxCount": 1,
        "InstanceType": instance_type,
        "SecurityGroupIds": [sg_id],
        "UserData": user_data,
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
            {"ResourceType": "instance", "Tags": tags_base(name, run_id, role)},
        ],
    }
    if args.key_name:
        params["KeyName"] = args.key_name
    if args.subnet_id:
        params["SubnetId"] = args.subnet_id

    inst = ec2_resource.create_instances(**params)[0]
    print(f"Creando {role}: {inst.id}")
    inst.wait_until_running()
    inst.reload()
    return inst


def crear(args: argparse.Namespace) -> None:
    ec2_client = client(args.region)
    ec2_resource = resource(args.region)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    ami_id = args.ami_id or latest_amazon_linux_2023(ec2_client)

    if args.security_group_id:
        sg_id = args.security_group_id
        ensure_distributed_ingress(ec2_client, sg_id=sg_id, ssh_cidr=args.ssh_cidr)
    else:
        vpc_id = args.vpc_id
        if args.subnet_id:
            vpc_id = vpc_from_subnet(ec2_client, args.subnet_id)
        if not vpc_id:
            vpc_id = default_vpc_id(ec2_client)
        sg_id = ensure_security_group(ec2_client, vpc_id=vpc_id, ssh_cidr=args.ssh_cidr)

    common = {
        "REPO_URL": args.repo_url,
        "BRANCH": args.branch,
    }

    print(f"Creando cluster distribuido en {args.region}")
    print(f"AMI={ami_id} SG={sg_id} subnet={args.subnet_id or '(default)'} run={run_id}")

    data = create_instance(
        ec2_resource=ec2_resource,
        args=args,
        ami_id=ami_id,
        sg_id=sg_id,
        run_id=run_id,
        role="data",
        user_data=render_user_data("data", common),
        instance_type=args.data_instance_type,
    )
    data_private_ip = data.private_ip_address
    if not data_private_ip:
        raise SystemExit("La instancia DATA no devolvio IP privada.")

    app = create_instance(
        ec2_resource=ec2_resource,
        args=args,
        ami_id=ami_id,
        sg_id=sg_id,
        run_id=run_id,
        role="app",
        user_data=render_user_data("app", common | {"DATA_PRIVATE_IP": data_private_ip}),
        instance_type=args.app_instance_type,
    )
    producer = create_instance(
        ec2_resource=ec2_resource,
        args=args,
        ami_id=ami_id,
        sg_id=sg_id,
        run_id=run_id,
        role="producer",
        user_data=render_user_data(
            "producer",
            common
            | {
                "DATA_PRIVATE_IP": data_private_ip,
                "PRODUCER_RATE": str(args.producer_rate),
                "PRODUCER_LIMIT": str(args.producer_limit),
            },
        ),
        instance_type=args.producer_instance_type,
    )

    print("\nCluster distribuido creado.")
    print(f"Run: {run_id}")
    print(f"DATA     {data.id} | privada={data.private_ip_address} | publica={data.public_dns_name}")
    print(f"APP      {app.id} | privada={app.private_ip_address} | publica={app.public_dns_name}")
    print(f"PRODUCER {producer.id} | privada={producer.private_ip_address} | publica={producer.public_dns_name}")
    print("\nURLs:")
    print(f"  Dashboard: http://{app.public_dns_name}:3000")
    print(f"  Backend:   http://{app.public_dns_name}:8000/health")
    print(f"  Snapshot:  http://{app.public_dns_name}:8000/api/dashboard/snapshot")
    print(f"  Kafka UI:  http://{data.public_dns_name}:8080")
    print("\nLogs utiles:")
    print("  DATA:     sudo tail -f /var/log/audiencias-data-bootstrap.log")
    print("  APP:      sudo tail -f /var/log/audiencias-app-bootstrap.log")
    print("  PRODUCER: sudo tail -f /var/log/audiencias-producer-bootstrap.log")
    print("\nServicios:")
    print("  APP:      systemctl status audiencias-event-store audiencias-stream audiencias-backend audiencias-dashboard")
    print("  PRODUCER: systemctl status audiencias-producer")


def listar(region: str) -> list[Any]:
    ec2 = resource(region)
    return list(
        ec2.instances.filter(
            Filters=[
                {"Name": "tag:Proyecto", "Values": [PROJECT_TAG]},
                {"Name": "tag:Modo", "Values": [DISTRIBUTED_TAG]},
                {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]},
            ]
        )
    )


def verificar(region: str) -> None:
    instancias = listar(region)
    if not instancias:
        print("No hay instancias distribuidas de este proyecto.")
        return
    for inst in sorted(instancias, key=lambda item: item.launch_time):
        inst.reload()
        tags = {tag["Key"]: tag["Value"] for tag in inst.tags or []}
        print(
            f"{inst.id} | {tags.get('Rol', '?'):>8} | {inst.state['Name']} | "
            f"publica={inst.public_dns_name} | privada={inst.private_ip_address}"
        )


def borrar(region: str) -> None:
    instancias = listar(region)
    ids = [inst.id for inst in instancias]
    if not ids:
        print("No hay instancias distribuidas para terminar.")
        return
    print(f"Terminando: {' '.join(ids)}")
    resource(region).instances.filter(InstanceIds=ids).terminate()


def main() -> None:
    parser = argparse.ArgumentParser(description="Automatiza el despliegue EC2 distribuido del Proyecto 03 Big Data")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--start", action="store_true", help="Crea DATA, APP y PRODUCER")
    group.add_argument("--check", action="store_true", help="Lista instancias distribuidas")
    group.add_argument("--delete", action="store_true", help="Termina instancias distribuidas")

    parser.add_argument("--region", default=REGION)
    parser.add_argument("--ami-id", default=AMI_ID)
    parser.add_argument("--key-name", default=KEY_NAME)
    parser.add_argument("--security-group-id", default=SECURITY_GROUP_ID)
    parser.add_argument("--subnet-id", default=SUBNET_ID)
    parser.add_argument("--vpc-id", default=None)
    parser.add_argument("--ssh-cidr", default="0.0.0.0/0")
    parser.add_argument("--instance-profile", default=INSTANCE_PROFILE)
    parser.add_argument("--volume-size", type=int, default=50)
    parser.add_argument("--data-instance-type", default=TIPO_INSTANCIA)
    parser.add_argument("--app-instance-type", default=TIPO_INSTANCIA)
    parser.add_argument("--producer-instance-type", default="t3.small")
    parser.add_argument("--producer-rate", type=int, default=200)
    parser.add_argument("--producer-limit", type=int, default=5000)
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
