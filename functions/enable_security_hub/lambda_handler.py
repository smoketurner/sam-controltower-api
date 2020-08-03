#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import logging
import warnings

from aws_lambda_powertools import Logger, Metrics, Tracer
import boto3
import botocore

boto3.set_stream_logger("", logging.INFO)
warnings.filterwarnings("ignore", "No metrics to publish*")

CT_AUDIT_ACCOUNT_NAME = "Audit"
SECURITY_HUB_REGIONS = os.environ.get("REGIONS", "").split(",")

tracer = Tracer()
logger = Logger()
metrics = Metrics()

organizations = boto3.client("organizations")
sts = boto3.client("sts")


def get_audit_account_id() -> str:
    """
    Return the Control Tower Audit account
    """
    paginator = organizations.get_paginator("list_accounts")
    page_iterator = paginator.paginate()
    for page in page_iterator:
        for account in page.get("Accounts", []):
            if account.get("Name") == CT_AUDIT_ACCOUNT_NAME:
                return account["Id"]
    return None


def get_account_email(account_id) -> str:
    """
    Return the email address for an account
    """
    response = organizations.describe_account(AccountId=account_id)
    return response.get("Account", {}).get("Email")


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event, context):

    account_id = event.get("account", {}).get("accountId")
    if not account_id:
        logger.error("Account ID not found in event")
        return

    audit_account_id = get_audit_account_id()
    if not audit_account_id:
        logger.error("Control Tower Audit account not found")
        return

    if not SECURITY_HUB_REGIONS:
        logger.error("No regions defined to enable Security Hub")
        return

    logger.info(
        f"Enabling Security Hub in {audit_account_id} in: {SECURITY_HUB_REGIONS}"
    )

    # 1. Assume role in new account and enable Security Hub

    role_arn = f"arn:aws:iam::{account_id}:role/AWSControlTowerExecution"
    response = sts.assume_role(RoleArn=role_arn, RoleSessionName="enable_security_hub")

    session = boto3.session.Session(
        aws_access_key_id=response["Credentials"]["AccessKeyId"],
        aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
        aws_session_token=response["Credentials"]["SessionToken"],
    )

    failed_regions = []

    for region in SECURITY_HUB_REGIONS:
        client = session.client("securityhub", region_name=region)
        logger.info(f"Enabling Security Hub in {account_id} in {region}")
        try:
            client.enable_security_hub()
            logger.debug(f"Enabled Security Hub in {account_id} in {region}")
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "ResourceConflictException":
                logger.exception(
                    f"Unable to enable Security Hub in {account_id} in {region}"
                )
                failed_regions.append(region)

    if len(failed_regions) == len(SECURITY_HUB_REGIONS):
        logger.error(
            f"Failed to enable Security Hub in all regions: {SECURITY_HUB_REGIONS}"
        )
        return

    account_email = get_account_email(account_id)

    # 2. Assume role into Audit account and enable Security Hub, create and invite the new account

    role_arn = f"arn:aws:iam::{audit_account_id}:role/AWSControlTowerExecution"
    response = sts.assume_role(RoleArn=role_arn, RoleSessionName="enable_security_hub")

    session = boto3.session.Session(
        aws_access_key_id=response["Credentials"]["AccessKeyId"],
        aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
        aws_session_token=response["Credentials"]["SessionToken"],
    )

    for region in SECURITY_HUB_REGIONS:
        if region in failed_regions:
            continue

        client = session.client("securityhub", region_name=region)

        logger.info(f"Enabling Security Hub in {audit_account_id} in {region}")
        try:
            client.enable_security_hub()
            logger.debug(f"Enabled Security Hub in {audit_account_id} in {region}")
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "ResourceConflictException":
                logger.exception(
                    f"Unable to enable Security Hub in {audit_account_id} in {region}"
                )
                continue

        logger.info(
            f"Creating member {account_id} to Security Hub in {audit_account_id} in {region}"
        )
        try:
            client.create_members(
                AccountDetails=[{"AccountId": account_id, "Email": account_email}]
            )
            logger.debug(
                f"Created member {account_id} to Security Hub in {audit_account_id} in {region}"
            )
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "ResourceConflictException":
                logger.exception(
                    f"Unable to create member {account_id} to Security Hub in {region}"
                )
                continue

        logger.info(
            f"Inviting member {account_id} to Security Hub in {audit_account_id} in {region}"
        )
        try:
            client.invite_members(AccountIds=[account_id])
            logger.debug(
                f"Invited member {account_id} to Security Hub in {audit_account_id} in {region}"
            )
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "ResourceConflictException":
                logger.exception(
                    f"Unable to invite member {account_id} to Security Hub in {region}"
                )

    # 3. Assume role in new account to accept invitation from Audit account

    role_arn = f"arn:aws:iam::{account_id}:role/AWSControlTowerExecution"
    response = sts.assume_role(RoleArn=role_arn, RoleSessionName="accept_invitation")

    session = boto3.session.Session(
        aws_access_key_id=response["Credentials"]["AccessKeyId"],
        aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
        aws_session_token=response["Credentials"]["SessionToken"],
    )

    for region in SECURITY_HUB_REGIONS:
        if region in failed_regions:
            continue

        client = session.client("securityhub", region_name=region)

        paginator = client.get_paginator("list_invitations")
        page_iterator = paginator.paginate()
        for page in page_iterator:
            for invitation in page.get("Invitations", []):
                logger.info(
                    f"Accepting invitation for {account_id} from {audit_account_id} in {region}"
                )
                client.accept_invitation(
                    MasterId=audit_account_id, InvitationId=invitation["InvitationId"]
                )
                logger.debug(
                    f"Accepted invitation for {account_id} from {audit_account_id} in {region}"
                )
