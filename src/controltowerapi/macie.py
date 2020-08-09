#!/usr/bin/env python
# -*- coding: utf-8 -*-

from aws_lambda_powertools import Logger
import boto3
import botocore

logger = Logger()

__all__ = ["Macie"]


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

    def update_organization_configuration(self, account_id):
        """
        Update the organization configuration to auto-enroll new accounts in Macie
        """
        sts = boto3.client("sts")

        role_arn = f"arn:aws:iam::{account_id}:role/AWSControlTowerExecution"
        response = sts.assume_role(RoleArn=role_arn, RoleSessionName="macie_org_config")

        session = boto3.session.Session(
            aws_access_key_id=response["Credentials"]["AccessKeyId"],
            aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
            aws_session_token=response["Credentials"]["SessionToken"],
        )

        client = session.client("macie2", region_name=self.region)
        client.update_organization_configuration(autoEnable=True)

