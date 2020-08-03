#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

from aws_lambda_powertools import Logger
import boto3
import botocore


boto3.set_stream_logger("", logging.INFO)
logger = Logger()


class Macie:
    def __init__(self, region: str) -> None:
        self.client = boto3.client("macie2", region_name=region)
        self.region = region

    def enable_organization_admin_account(self, account_id):
        logger.info(
            f"Enabling account {account_id} to be Macie admin account in {self.region}"
        )
        try:
            self.client.enable_organization_admin_account(adminAccountId=account_id)
            logger.debug(
                f"Enabled account {account_id} to be Macie admin account in {self.region}"
            )
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "ConflictException":
                logger.exception(
                    f"Unable to enable account {account_id} to be Macie admin account in {self.region}"
                )
                raise error
