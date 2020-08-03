#!/usr/bin/env python
# -*- coding: utf-8 -*-

from aws_lambda_powertools import Logger
import boto3
import botocore

logger = Logger()

__all__ = ["RAM"]


class RAM:
    def __init__(self) -> None:
        self.client = boto3.client("ram")

    def enable_sharing_with_aws_organization(self) -> None:
        logger.info("Enabling RAM sharing with organization")
        try:
            self.client.enable_sharing_with_aws_organization()
            logger.debug("Enabled RAM sharing with organization")
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "OperationNotPermittedException":
                logger.exception("Unable enable RAM sharing with organization")
                raise error
