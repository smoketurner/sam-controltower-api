#!/usr/bin/env python
# -*- coding: utf-8 -*-

import warnings

from aws_lambda_powertools import Logger, Metrics, Tracer
from crhelper import CfnResource

from controltowerapi.organizations import Organizations
from controltowerapi.guardduty import GuardDuty
from controltowerapi.macie import Macie
from controltowerapi.servicecatalog import ServiceCatalog
from controltowerapi.ram import RAM


warnings.filterwarnings("ignore", "No metrics to publish*")

tracer = Tracer()
logger = Logger()
metrics = Metrics()

helper = CfnResource(json_logging=True, log_level="INFO", boto_level="INFO")
organizations = Organizations()

SERVICE_ACCESS_PRINCIPALS = [
    "backup.amazonaws.com",
    "config.amazonaws.com",
    "config-multiaccountsetup.amazonaws.com",
    "guardduty.amazonaws.com",
    "macie.amazonaws.com",
]

DELEGATED_ADMINISTRATOR_PRINCIPALS = [
    "access-analyzer.amazonaws.com",
    "config-multiaccountsetup.amazonaws.com",
]


@tracer.capture_method
@helper.create
@helper.update
def create(event, context):
    logger.info("Got Create or Update")

    properties = event.get("ResourceProperties", {})
    regions = properties.get("Regions", [])

    # enable all organizational policy types
    organizations.enable_all_policy_types()

    # attach an AI service opt-out policy
    organizations.attach_ai_optout_policy()

    # enable Service Catalog access to the organization
    ServiceCatalog().enable_aws_organizations_access()

    # enable various AWS service principal access to the organization
    organizations.enable_aws_service_access(SERVICE_ACCESS_PRINCIPALS)

    # enable RAM sharing to the organization
    RAM().enable_sharing_with_aws_organization()

    audit_account_id = organizations.get_audit_account_id()
    if not audit_account_id:
        logger.error("Unable to find Control Tower Audit account")
        return context.invoked_function_arn

    for region in regions:
        guardduty = GuardDuty(region)

        # delegate GuardDuty administration to the Control Tower Audit account
        guardduty.enable_organization_admin_account(audit_account_id)

        # update the GuartDuty organization configuration to register new accounts automatically
        guardduty.update_organization_configuration(audit_account_id)

        # delegate Macie administration to the Control Tower Audit account
        Macie(region).enable_organization_admin_account(audit_account_id)

    # Register the Control Tower Audit account as a delegated administer on AWS services
    organizations.register_delegated_administrator(
        audit_account_id, DELEGATED_ADMINISTRATOR_PRINCIPALS
    )

    return context.invoked_function_arn


@tracer.capture_method
@helper.delete
def delete(event, context):
    logger.info("Got Delete")


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    helper(event, context)
