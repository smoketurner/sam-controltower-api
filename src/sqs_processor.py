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


def parse_datetime(timestamp: str) -> datetime:
    """
    Parse a string value from an AWS response as "2020-09-21 01:53:07.692000+00:00" into a datetime

    Parameters
    ----------
    timestamp: str
        A timestamp to be parsed
    """
    return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S.%f%z")


@tracer.capture_method
def check_active() -> None:
    """
    Raise an exception if there are any accounts being created
    """
    for status in ACTIVE_STATUSES:
        logger.debug(f"Checking if any accounts in status {status}")
        try:
            count = AccountModel.status_index.count(status, limit=1)
        except pynamodb.exceptions.QueryError as error:
            logger.exception("Unable to query account status index")
            raise error

        if count > 0:
            logger.warn(
                f"Found {count} accounts in {status} status, leaving message in queue"
            )
            raise Exception()


@tracer.capture_method
def create_account(account: AccountModel) -> None:
    """
    Provision a new account through Service Catalog

    Parameters
    ----------
    account: AccountModel
        An account to create through Service Catalog
    """

    parameters = {
        "AccountName": account.account_name,
        "AccountEmail": account.account_email,
        "ManagedOrganizationalUnit": account.ou_name,
        "SSOUserEmail": account.sso_user_email,
        "SSOUserFirstName": account.sso_user_first_name,
        "SSOUserLastName": account.sso_user_last_name,
    }

    try:
        product = servicecatalog.provision_product(CT_PRODUCT, parameters)
    except Exception as error:
        logger.exception("Unable to provision product")
        raise error

    try:
        account.update(
            actions=[
                AccountModel.record_id.set(product["RecordId"]),
                AccountModel.created_at.set(parse_datetime(product["CreatedTime"])),
                AccountModel.updated_at.set(parse_datetime(product["UpdatedTime"])),
                AccountModel.status.set(product["Status"]),
            ],
            condition=(AccountModel.status == "QUEUED"),
        )
    except pynamodb.exceptions.UpdateError as error:
        logger.exception("Unable to update account")
        raise error


@tracer.capture_method
def update_status(account: AccountModel) -> Optional[str]:
    """
    Update the DynamoDB item with the latest ServiceCatalog status

    Parameters
    ----------
    account: AccountModel
        An account to retrieve the latest ServiceCatalog status for
    """

    if not account.record_id:
        return None

    response = servicecatalog.describe_record(account.record_id)
    logger.debug(response)

    status = response.get("RecordDetail", {}).get("Status")
    updated_at = response.get("RecordDetail", {}).get("UpdatedTime")
    outputs = {
        output["OutputKey"]: output["OutputValue"]
        for output in response.get("RecordOutputs", {})
    }

    actions = [
        AccountModel.status.set(status),
        AccountModel.updated_at.set(parse_datetime(updated_at)),
    ]
    if "AccountId" in outputs:
        actions.append(AccountModel.account_id.set(outputs["AccountId"]))

    try:
        account.update(actions=actions)
    except pynamodb.exceptions.UpdateError as error:
        logger.exception("Unable to update account")
        raise error
    return status


@tracer.capture_method
def record_handler(record: Dict[str, str]) -> None:
    """
    Process an individual record. To keep the message in the queue, this function must throw an exception.
    """
    # logger.debug(record)

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

    logger.debug(f"Account {account.account_name} has status {account.status}")

    if account.status == "QUEUED":
        # throw an exception if an item is active so this message is retried
        check_active()

        logger.info(
            f"No accounts in progress, creating account '{account.account_name}'"
        )

        try:
            create_account(account)
        except Exception as error:
            logger.exception("Unable to create account")
            if isinstance(error, botocore.exceptions.ClientError):
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
                        raise error
                else:
                    raise error
            else:
                raise error

    if not account.record_id:
        logger.warn(
            f"Account {account.account_name} has status {account.status} and no record_id, deleting message"
        )
        return

    status = update_status(account)
    if status in FINISH_STATUSES:
        logger.info(
            f"Account '{account.account_name}' reached {status}, deleting message"
        )


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
@sqs_batch_processor(record_handler=record_handler)
def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> None:
    return {"statusCode": 200}
