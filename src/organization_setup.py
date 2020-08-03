#!/usr/bin/env python
# -*- coding: utf-8 -*-

import warnings

from aws_lambda_powertools import Logger, Metrics, Tracer
from crhelper import CfnResource

from controltowerapi.organizations import Organizations
from controltowerapi.guardduty import GuardDuty
from controltowerapi.macie import Macie
from controltowerapi.servicecatalog import ServiceCatalog


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
    create_policies = properties.get("CreatePolicies", "false") == "true"

    organizations.enable_all_policy_types()

    if create_policies:
        organizations.attach_ai_optout_policy()

    ServiceCatalog().enable_aws_organizations_access()

    organizations.enable_aws_service_access(SERVICE_ACCESS_PRINCIPALS)

    audit_account_id = organizations.get_audit_account_id()
    if not audit_account_id:
        logger.error("Unable to find Control Tower Audit account")
        return context.invoked_function_arn

    for region in regions:
        guardduty = GuardDuty(region)
        guardduty.enable_organization_admin_account(audit_account_id)
        guardduty.update_organization_configuration(audit_account_id)

        Macie(region).enable_organization_admin_account(audit_account_id)

    organizations.register_delegated_administrator(
        audit_account_id, DELEGATED_ADMINISTRATOR_PRINCIPALS
    )

    return context.invoked_function_arn


@tracer.capture_method
@helper.delete
def delete(event, context):
    logger.info("Got Delete")

    properties = event.get("ResourceProperties", {})
    regions = properties.get("Regions", [])

    organizations.delete_ai_optout_policy()
    ServiceCatalog().disable_aws_organizations_access()

    audit_account_id = organizations.get_audit_account_id()
    if audit_account_id:
        for region in regions:
            GuardDuty(region).disable_organization_admin_account(audit_account_id)
            Macie(region).disable_organization_admin_account(audit_account_id)

        organizations.deregister_delegated_administrator(
            audit_account_id, DELEGATED_ADMINISTRATOR_PRINCIPALS
        )

    organizations.disable_aws_service_access(SERVICE_ACCESS_PRINCIPALS)

    return context.invoked_function_arn


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    helper(event, context)
