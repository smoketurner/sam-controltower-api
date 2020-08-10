#!/usr/bin/env python
# -*- coding: utf-8 -*-

import warnings

from aws_lambda_powertools import Logger, Metrics, Tracer

from .sts import STS

warnings.filterwarnings("ignore", "No metrics to publish*")

tracer = Tracer()
logger = Logger()
metrics = Metrics()


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event, context):

    account_id = event.get("account", {}).get("accountId")
    if not account_id:
        raise Exception("Account ID not found in event")

    sts = STS()

    role_arn = f"arn:aws:iam::{account_id}:role/AWSControlTowerExecution"
    role = sts.assume_role(role_arn, "s3_public_block")

    client = role.client("s3control")
    client.put_public_access_block(
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
        AccountId=account_id,
    )
