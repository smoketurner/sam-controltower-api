#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import warnings

from aws_lambda_powertools import Logger, Metrics, Tracer
import boto3

from .organizations import Organizations
from .sts import STS
from .securityhub import SecurityHub

warnings.filterwarnings("ignore", "No metrics to publish*")

SECURITY_HUB_REGIONS = os.environ.get("REGIONS", "").split(",")
tracer = Tracer()
logger = Logger()
metrics = Metrics()
organizations = Organizations()
sts = STS()


@tracer.capture_method
def get_regions() -> list:
    """
    Return the list of regions
    """
    if SECURITY_HUB_REGIONS:
        regions = SECURITY_HUB_REGIONS
    else:
        logger.warn("SECURITY_HUB_REGIONS not defined, using all regions")
        ec2 = boto3.client("ec2")
        regions = [
            region["RegionName"]
            for region in ec2.describe_regions(
                Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required"]}],
                AllRegions=False,
            )["Regions"]
        ]
    return regions


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event, context):

    account_id = event.get("account", {}).get("accountId")
    if not account_id:
        logger.error("Account ID not found in event")
        return

    audit_account_id = organizations.get_audit_account_id()
    if not audit_account_id:
        logger.error("Control Tower Audit account not found")
        return

    regions = get_regions()
    if not regions:
        logger.error("No regions found to enable Security Hub")
        return

    # 1. Assume role in new account and enable Security Hub

    logger.info(f"Enabling Security Hub in {account_id} in: {regions}")

    role_arn = f"arn:aws:iam::{account_id}:role/AWSControlTowerExecution"
    role = sts.assume_role(role_arn, "enable_security_hub")

    failed_regions = []

    for region in regions:
        securityhub = SecurityHub(role, region, account_id)
        try:
            securityhub.enable_security_hub()
        except Exception:
            failed_regions.append(region)

    if len(failed_regions) == len(regions):
        logger.error(
            f"Failed to enable Security Hub in {account_id} in all regions: {regions}"
        )
        return
    elif failed_regions:
        logger.warn(
            f"Failed to enable Security Hub in {account_id} in regions: {failed_regions}"
        )

    account_email = organizations.get_account_email(account_id)

    # 2. Assume role into Audit account and enable Security Hub, create and invite the new account

    logger.info(f"Enabling Security Hub in {audit_account_id} in: {regions}")

    role_arn = f"arn:aws:iam::{audit_account_id}:role/AWSControlTowerExecution"
    role = sts.assume_role(role_arn, "enable_security_hub")

    for region in regions:
        if region in failed_regions:
            continue

        securityhub = SecurityHub(role, region, audit_account_id)

        try:
            securityhub.enable_security_hub()
            securityhub.create_member(account_id, account_email)
            securityhub.invite_member(account_id)
        except Exception:
            continue

    # 3. Assume role in new account to accept invitation from Audit account

    logger.info(f"Accepting Security Hub invitations in {account_id} in: {regions}")

    role_arn = f"arn:aws:iam::{account_id}:role/AWSControlTowerExecution"
    role = sts.assume_role(role_arn, "accept_invitation")

    for region in regions:
        if region in failed_regions:
            continue

        securityhub = SecurityHub(role, region, account_id)
        securityhub.accept_invitations(audit_account_id)
