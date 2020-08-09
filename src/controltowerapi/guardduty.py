#!/usr/bin/env python
# -*- coding: utf-8 -*-

from aws_lambda_powertools import Logger
import boto3
import botocore

logger = Logger()

__all__ = ["GuardDuty"]


class GuardDuty:
    def __init__(self, region) -> None:
        self.client = boto3.client("guardduty", region_name=region)
        self.region = region

    def enable_organization_admin_account(self, account_id: str) -> None:
        logger.info(
            f"Enabling account {account_id} to be GuardDuty admin account in {self.region}"
        )
        try:
            self.client.enable_organization_admin_account(AdminAccountId=account_id)
            logger.debug(
                f"Enabled account {account_id} to be GuardDuty admin account in {self.region}"
            )
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "BadRequestException":
                logger.exception(
                    f"Unable to enable account {account_id} to be GuardDuty admin account in {self.region}"
                )
                raise error

    def update_organization_configuration(self, account_id) -> None:
        """
        Update the organization configuration to auto-enroll new accounts in GuardDuty
        """
        sts = boto3.client("sts")

        role_arn = f"arn:aws:iam::{account_id}:role/AWSControlTowerExecution"
        response = sts.assume_role(
            RoleArn=role_arn, RoleSessionName="guardduty_org_config"
        )

        session = boto3.session.Session(
            aws_access_key_id=response["Credentials"]["AccessKeyId"],
            aws_secret_access_key=response["Credentials"]["SecretAccessKey"],
            aws_session_token=response["Credentials"]["SessionToken"],
        )

        client = session.client("guardduty", region_name=self.region)

        detector_ids = []

        paginator = client.get_paginator("list_detectors")
        page_iterator = paginator.paginate()
        for page in page_iterator:
            detector_ids.extend(page.get("DetectorIds", []))

        if not detector_ids:
            response = client.create_detector(
                Enable=True,
                DataSources={"S3Logs": {"Enable": True}},
                FindingPublishingFrequency="SIX_HOURS",
            )
            detector_ids.append(response["DetectorId"])

        for detector_id in detector_ids:
            client.update_organization_configuration(
                DetectorId=detector_id,
                AutoEnable=True,
                DataSources={"S3Logs": {"AutoEnable": True}},
            )
