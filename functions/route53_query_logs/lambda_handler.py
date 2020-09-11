#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
from typing import Dict, Any
import warnings

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from .sts import STS

warnings.filterwarnings("ignore", "No metrics to publish*")

tracer = Tracer()
logger = Logger()
metrics = Metrics()


@metrics.log_metrics(capture_cold_start_metric=True)
@tracer.capture_lambda_handler
@logger.inject_lambda_context(log_event=True)
def handler(event: Dict[str, Any], context: LambdaContext) -> None:

    account_id = event.get("account", {}).get("accountId")
    if not account_id:
        raise Exception("Account ID not found in event")

    sts = STS()

    role_arn = f"arn:aws:iam::{account_id}:role/AWSControlTowerExecution"
    role = sts.assume_role(role_arn, "route53_resource_policy")

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

    client = role.client("logs")
    client.put_resource_policy(
        policyName="AWSServiceRoleForRoute53", policyDocument=json.dumps(policy)
    )
