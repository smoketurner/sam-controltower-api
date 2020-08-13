#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

# see https://github.com/awslabs/aws-deployment-framework/blob/master/src/lambda_codebase/initial_commit/bootstrap_repository/adf-build/provisioner/src/vpc.py

from concurrent.futures import ThreadPoolExecutor
import warnings
import time

from aws_lambda_powertools import Logger, Metrics, Tracer
import boto3
import botocore

warnings.filterwarnings("ignore", "No metrics to publish*")

tracer = Tracer()
logger = Logger()
metrics = Metrics()


def vpc_cleanup(vpcid, session, region):
    if not vpcid:
        return

    ec2 = session.resource("ec2", region_name=region)
    ec2client = ec2.meta.client
    vpc = ec2.Vpc(vpcid)

    # detach and delete all gateways associated with the vpc
    for gw in vpc.internet_gateways.all():
        vpc.detach_internet_gateway(InternetGatewayId=gw.id)
        gw.delete()

    # Route table associations
    for rt in vpc.route_tables.all():
        for rta in rt.associations:
            if not rta.main:
                rta.delete()

    # Security Group
    for sg in vpc.security_groups.all():
        if sg.group_name != "default":
            sg.delete()

    # Network interfaces
    for subnet in vpc.subnets.all():
        for interface in subnet.network_interfaces.all():
            interface.delete()
        subnet.delete()

    # Delete vpc
    ec2client.delete_vpc(VpcId=vpcid)
    logger.info(f"VPC {vpcid} and associated resources has been deleted.")


def delete_default_vpc(client, account_id, region, session):
    default_vpc_id = None
    max_retry_seconds = 360
    while True:
        try:
            vpc_response = client.describe_vpcs()
            break
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] == "OptInRequired":
                logger.warning(
                    f"Passing on region {client.meta.region_name} as Opt-in is required."
                )
                return
        except BaseException as error:
            logger.warning(
                f"Could not retrieve VPCs: {error}. Sleeping for 2 seconds before trying again."
            )
            max_retry_seconds = +2
            time.sleep(2)
            if max_retry_seconds <= 0:
                raise Exception("Could not describe VPCs within retry limit.")

    for vpc in vpc_response["Vpcs"]:
        if vpc["IsDefault"] is True:
            default_vpc_id = vpc["VpcId"]
            break

    if default_vpc_id is None:
        logger.debug(
            f"No default VPC found in account {account_id} in the {region} region"
        )
        return

    logger.info(f"Found default VPC Id {default_vpc_id} in the {region} region")
    vpc_cleanup(default_vpc_id, session, region)


def schedule_delete_default_vpc(account_id, region, credentials):
    session = boto3.session.Session(
        aws_access_key_id=credentials["AccessKeyId"],
        aws_secret_access_key=credentials["SecretAccessKey"],
        aws_session_token=credentials["SessionToken"],
    )
    ec2_client = session.client("ec2", region_name=region)
    delete_default_vpc(ec2_client, account_id, region, session)


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event, context):

    account_id = event.get("account", {}).get("accountId")
    if not account_id:
        raise Exception("Account ID not found in event")

    ec2 = boto3.client("ec2")

    all_regions = [
        region["RegionName"]
        for region in ec2.describe_regions(
            Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required"]}],
            AllRegions=False,
        )["Regions"]
    ]

    sts = boto3.client("sts")

    role_arn = f"arn:aws:iam::{account_id}:role/AWSControlTowerExecution"
    credentials = sts.assume_role(
        RoleArn=role_arn, RoleSessionName="delete_default_vpc"
    )["Credentials"]

    args = ((account_id, region, credentials) for region in all_regions)

    with ThreadPoolExecutor(max_workers=10) as executor:
        for _ in executor.map(lambda f: schedule_delete_default_vpc(*f), args):
            pass
