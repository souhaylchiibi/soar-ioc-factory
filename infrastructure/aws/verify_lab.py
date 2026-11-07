"""Read-only AWS Learner Lab verification (NO resource is ever created).

Covers the checks mandated by the project rules §8:
  1. identity/account of the temporary credentials
  2. existing resources (EC2/EBS/S3) — detects a pre-existing instance
  3. default VPC / network exposure basics
  4. regions allowed for this session
  5. anything that would cost money is REPORTED, never created

Run with temporary lab credentials in the environment.
Exit code 0 = checks completed (findings are informational).
"""
from __future__ import annotations

import json
import sys

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

RESULTS: list[tuple[str, str, str]] = []   # (check, status, detail)


def add(check: str, status: str, detail: str) -> None:
    RESULTS.append((check, status, detail))
    print(f"[{status:>6}] {check}: {detail}")


def main() -> int:
    # ---------------------------------------------------------- identity ---
    try:
        sts = boto3.client("sts")
        ident = sts.get_caller_identity()
        add("IDENTITY", "OK",
            f"arn={ident['Arn']} account={ident['Account']}")
    except NoCredentialsError:
        add("IDENTITY", "FAIL", "aucune credential AWS dans l'environnement")
        return 2
    except ClientError as exc:
        add("IDENTITY", "FAIL", f"{exc.response['Error']['Code']}: {exc.response['Error']['Message']}")
        return 2
    except EndpointConnectionError as exc:
        add("IDENTITY", "FAIL", f"endpoint injoignable: {exc}")
        return 2

    region = boto3.session.Session().region_name or "us-east-1"
    add("REGION", "INFO", f"region du client: {region}")

    # ---------------------------------------------- EC2 existing resources
    ec2 = boto3.client("ec2", region_name=region)
    try:
        instances = ec2.describe_instances()
        running = []
        for res in instances.get("Reservations", []):
            for inst in res.get("Instances", []):
                running.append(
                    f"{inst['InstanceId']} {inst['State']['Name']} {inst.get('InstanceType','?')} "
                    f"pub={inst.get('PublicIpAddress','-')}"
                )
        if running:
            add("EC2", "FOUND", f"{len(running)} instance(s): " + " | ".join(running))
        else:
            add("EC2", "NONE", "aucune instance EC2 dans cette region")
    except ClientError as exc:
        add("EC2", "DENIED", f"{exc.response['Error']['Code']}")

    try:
        volumes = ec2.describe_volumes().get("Volumes", [])
        add("EBS", "INFO", f"{len(volumes)} volume(s) existant(s)")
    except ClientError as exc:
        add("EBS", "DENIED", exc.response["Error"]["Code"])

    # ------------------------------------------------------------- network --
    try:
        vpcs = ec2.describe_vpcs()["Vpcs"]
        default = [v for v in vpcs if v.get("IsDefault")]
        add("VPC", "INFO",
            f"{len(vpcs)} VPC(s), default={default[0]['VpcId'] if default else 'aucun'}")
        if default:
            subs = ec2.describe_subnets(
                Filters=[{"Name": "vpc-id", "Values": [default[0]["VpcId"]]}]
            )["Subnets"]
            public = [s["SubnetId"] for s in subs if s.get("MapPublicIpOnLaunch")]
            add("SUBNETS", "INFO",
                f"{len(subs)} subnet(s), {len(public)} public(s) (auto-IP public)")
    except ClientError as exc:
        add("VPC", "DENIED", exc.response["Error"]["Code"])

    # Security groups with world-open ports (cost/exposure risk indicator)
    try:
        sgs = ec2.describe_security_groups()["SecurityGroups"]
        exposed = []
        for sg in sgs:
            for perm in sg.get("IpPermissions", []):
                for rng in perm.get("IpRanges", []):
                    if rng.get("CidrIp") == "0.0.0.0/0":
                        exposed.append(f"{sg['GroupId']}/{perm.get('FromPort','*')}")
        add("SECURITY_GROUPS", "WARN" if exposed else "OK",
            f"ouverts 0.0.0.0/0: {', '.join(exposed) if exposed else 'aucun'}")
    except ClientError as exc:
        add("SECURITY_GROUPS", "DENIED", exc.response["Error"]["Code"])

    # --------------------------------------------------------------- S3 -----
    try:
        s3 = boto3.client("s3", region_name=region)
        buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
        add("S3", "INFO", f"{len(buckets)} bucket(s): {', '.join(buckets[:8]) or 'aucun'}")
    except ClientError as exc:
        add("S3", "DENIED", exc.response["Error"]["Code"])

    # ------------------------------------------------- region/service allowlist
    try:
        regions = [r["RegionName"] for r in ec2.describe_regions()["Regions"]]
        add("REGIONS", "INFO", f"{len(regions)} region(s) accessibles: {', '.join(regions[:6])}…")
    except ClientError as exc:
        add("REGIONS", "DENIED", exc.response["Error"]["Code"])

    # -------------------------------------------------------------- summary --
    print("\n== RESUME (aucune ressource creee) ==")
    counts: dict[str, int] = {}
    for _, status, _ in RESULTS:
        counts[status] = counts.get(status, 0) + 1
    print(json.dumps(counts))
    print("COUT ENGAGE: 0.00 USD (verifications lecture seule uniquement)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
