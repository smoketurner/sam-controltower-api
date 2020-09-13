#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime, timezone
import json
import os
from typing import Dict, Any, Optional
import warnings

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.batch import sqs_batch_processor
from aws_lambda_powertools.utilities.typing import LambdaContext
import botocore
import pynamodb

from controltowerapi.servicecatalog import ServiceCatalog
from controltowerapi.models import AccountModel

warnings.filterwarnings("ignore", "No metrics to publish*")

tracer = Tracer()
logger = Logger()
metrics = Metrics()
servicecatalog = ServiceCatalog()

CT_PORTFOLIO_ID = servicecatalog.get_ct_portfolio_id()
servicecatalog.associate_principal(CT_PORTFOLIO_ID, os.environ["LAMBDA_ROLE_ARN"])
CT_PRODUCT = servicecatalog.get_ct_product()

ACTIVE_STATUSES = {"CREATED", "IN_PROGRESS", "IN_PROGRESS_IN_ERROR"}
FINISH_STATUSES = {"FAILED", "SUCCEEDED"}


@tracer.capture_method
def check_active() -> None:
    """
    Check if there are any accounts being created
    """
    for status in ACTIVE_STATUSES:
        count = AccountModel.status_index.count(status, limit=1)
        if count > 0:
            raise Exception(
                f"Found {count} accounts in {status} status, leaving message in queue"
            )


@tracer.capture_method
def create_account(account: AccountModel) -> None:
    """
    Provision a new account through Service Catalog
    """

    parameters = {
        "AccountName": account.account_name,
        "AccountEmail": account.account_email,
        "ManagedOrganizationalUnit": account.ou_name,
        "SSOUserEmail": account.sso_user_email,
        "SSOUserFirstName": account.sso_user_first_name,
        "SSOUserLastName": account.sso_user_last_name,
    }

    product = servicecatalog.provision_product(CT_PRODUCT, parameters)

    try:
        account.update(
            actions=[
                AccountModel.record_id.set(product["RecordId"]),
                AccountModel.created_at.set(product["CreatedTime"]),
                AccountModel.updated_at.set(product["UpdatedTime"]),
                AccountModel.status.set(product["Status"]),
            ],
            condition=(AccountModel.status == "QUEUED"),
        )
    except pynamodb.exceptions.UpdateError as error:
        if isinstance(error.cause, botocore.exceptions.ClientError):
            if (
                error.cause.response["Error"]["Code"]
                == "ConditionalCheckFailedException"
            ):
                logger.warn("Account status was not QUEUED")
        else:
            logger.exception("Unable to update account")
        raise error


@tracer.capture_method
def update_status(account: AccountModel) -> Optional[str]:
    """
    Update the DynamoDB item with the latest ServiceCatalog status
    """
    if not account.record_id:
        return None

    response = servicecatalog.describe_record(account.record_id)

    status = response.get("RecordDetail", {}).get("Status")
    if status != account.status:
        try:
            account.update(
                actions=[
                    AccountModel.status.set(status),
                    AccountModel.updated_at.set(datetime.now(timezone.utc)),
                ],
                condition=(AccountModel.status == account.status),
            )
        except pynamodb.exceptions.UpdateError as error:
            logger.exception("Unable to update account")
            if isinstance(error.cause, botocore.exceptions.ClientError):
                if (
                    error.cause.response["Error"]["Code"]
                    == "ConditionalCheckFailedException"
                ):
                    logger.warn(f"Account status was not {account.status}")
                else:
                    raise error.cause
            else:
                raise error
    return status


@tracer.capture_method
def record_handler(record: Dict[str, str]) -> None:
    """
    Process an individual record. To keep the message in the queue, this function must throw an exception.
    """
    try:
        body = json.loads(record.get("body"))
    except json.decoder.JSONDecodeError as error:
        logger.error(f"Invalid JSON body, deleting message: {error}")
        return

    account_name = body.get("AccountName")

    try:
        account = AccountModel.get(account_name)
    except AccountModel.DoesNotExist:
        logger.warn(f"Account '{account_name}' does not exist, deleting message")
        return

    if account.status != "QUEUED":
        status = update_status(account)
        if status is None:
            logger.warn(
                f"Account {account.account_name} has status {account.status} and no record_id, deleting message"
            )
            return

        elif status in FINISH_STATUSES:
            logger.info(
                f"Account '{account.account_name}' reached {status}, deleting message"
            )
            return

    # throw an exception if an item is active so this message is retried
    check_active()

    logger.info(f"No accounts in progress, creating account '{account.account_name}'")

    try:
        create_account(account)
    except botocore.exceptions.ClientError as error:
        logger.exception("Unable to create account")
        if error.response["Error"]["Code"] == "InvalidParametersException":
            logger.error(
                f"Invalid parameters in account '{account_name}', deleting message"
            )

            # update status to FAILED
            try:
                account.update(
                    actions=[
                        AccountModel.status.set("FAILED"),
                        AccountModel.status_message.set(error.message),
                        AccountModel.updated_at.set(datetime.now(timezone.utc)),
                    ],
                    condition=(AccountModel.status == "QUEUED"),
                )
            except pynamodb.exceptions.UpdateError as error:
                logger.exception("Unable to update account")
                if isinstance(error.cause, botocore.exceptions.ClientError):
                    if (
                        error.cause.response["Error"]["Code"]
                        == "ConditionalCheckFailedException"
                    ):
                        logger.warn("Account status was not QUEUED")
                    else:
                        raise error.cause
                else:
                    raise error
        else:
            raise error


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@sqs_batch_processor(record_handler=record_handler)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> None:
    return {"statusCode": 200}
