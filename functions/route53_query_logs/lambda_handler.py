#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import logging
import warnings

from aws_lambda_powertools import Logger, Metrics, Tracer
import boto3

boto3.set_stream_logger("", logging.INFO)
warnings.filterwarnings("ignore", "No metrics to publish*")

tracer = Tracer()
logger = Logger()
metrics = Metrics()

sts = boto3.client("sts")


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event, context):

    account_id = event.get("account", {}).get("accountId")
    if not account_id:
        logger.error("Account ID not found in event")
        return

    role_arn = f"arn:aws:iam::{account_id}:role/AWSControlTowerExecution"
    response = sts.assume_role(
        RoleArn=role_arn, RoleSessionName="route53_resource_policy"
    )

    session = boto3.session.Session(
        aws_access_key_id=response["Credentials"]["AccessKeyId"],
        aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
        aws_session_token=response["Credentials"]["SessionToken"],
    )

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "Route53LogsToCloudWatchLogs",
                "Effect": "Allow",
                "Principal": {"Service": "route53.amazonaws.com"},
                "Action": ["logs:CreateLogStream", "logs:PutLogEvents"],
                "Resource": f"arn:aws:logs:us-east-1:{account_id}:log-group:/aws/route53/*",  # log-group must be in us-east-1
            }
        ],
    }

    client = session.client("logs")
    client.put_resource_policy(
        policyName="AWSServiceRoleForRoute53", policyDocument=json.dumps(policy)
    )
