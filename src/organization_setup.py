#!/usr/bin/env python
# -*- coding: utf-8 -*-

import warnings

import boto3
import botocore
from aws_lambda_powertools import Logger, Metrics, Tracer
from crhelper import CfnResource

from controltowerapi.organizations import Organizations


warnings.filterwarnings("ignore", "No metrics to publish*")

tracer = Tracer()
logger = Logger()
metrics = Metrics()

helper = CfnResource(json_logging=True, log_level="INFO", boto_level="INFO")
organizations = Organizations()


def configure_audit(account_id) -> None:
    logger.info(f"Enabling Audit account ({account_id}) to be GuardDuty admin account")
    guardduty = boto3.client("guardduty")
    guardduty.enable_organization_admin_account(AdminAccountId=account_id)

    principals = [
        "config.amazonaws.com",
        "config-multiaccountsetup.amazonaws.com",
        "access-analyzer.amazonaws.com",
    ]
    for principal in principals:
        organizations.register_delegated_administrator(account_id, principal)

    logger.info(f"Enabling Audit account ({account_id}) to be Macie admin account")
    macie = boto3.client("macie2")
    try:
        macie.enable_organization_admin_account(adminAccountId=account_id)
        logger.debug(f"Enabled Audit account ({account_id}) to be Macie admin account")
    except botocore.exceptions.ClientError as error:
        if error.response["Error"]["Code"] != "ConflictException":
            logger.exception("Unable to enable Macie organization admin account")
            raise error


@tracer.capture_method
@helper.create
def create(event, context):
    logger.info("Got Create")

    properties = event.get("ResourceProperties", {})
    create_policies = properties.get("CreatePolicies", "false") == "true"

    logger.info("Enabling all policy types in organization")
    organizations.enable_all_policy_types()

    logger.info("Enabling organizational access for ServiceCatalog")
    servicecatalog = boto3.client("servicecatalog")
    try:
        servicecatalog.enable_aws_organizations_access()
        logger.debug("Enabled organizational access for ServiceCatalog")
    except botocore.exceptions.ClientError as error:
        if error.response["Error"]["Code"] != "InvalidStateException":
            logger.exception("Unable enable organization access for ServiceCatalog")
            raise error

    audit_account_id = organizations.get_audit_account_id()
    if audit_account_id:
        configure_audit(audit_account_id)
    else:
        logger.error("Unable to find Control Tower Audit account")

    if create_policies:
        organizations.attach_ai_optout_policy()

    return context.invoked_function_arn


@tracer.capture_method
@helper.update
def update(event, context):
    logger.info("Got Update")

    properties = event.get("ResourceProperties", {})
    create_policies = properties.get("CreatePolicies", "false") == "true"

    if create_policies:
        organizations.attach_ai_optout_policy()
    else:
        organizations.delete_ai_optout_policy()


@tracer.capture_method
@helper.delete
def delete(event, context):
    logger.info("Got Delete")

    organizations.delete_ai_optout_policy()


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    helper(event, context)
