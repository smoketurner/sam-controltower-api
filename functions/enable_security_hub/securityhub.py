#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

from aws_lambda_powertools import Logger
import boto3
import botocore


boto3.set_stream_logger("", logging.INFO)
logger = Logger()


class SecurityHub:
    def __init__(self, role, region: str, account_id: str = None) -> None:
        self.client = role.client("securityhub", region_name=region)
        self.account_id = account_id  # only used for logging
        self.region = region  # only used for logging

    def enable_security_hub(self) -> None:
        """
        Enable Security Hub
        """
        logger.info(f"Enabling Security Hub in {self.account_id} in {self.region}")
        try:
            self.client.enable_security_hub()
            logger.debug(f"Enabled Security Hub in {self.account_id} in {self.region}")
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "ResourceConflictException":
                logger.exception(
                    f"Unable to enable Security Hub in {self.account_id} in {self.region}"
                )
                raise error

    def create_member(self, account_id: str, account_email: str) -> None:
        """
        Create a Security Hub member
        """
        logger.info(
            f"Creating member {account_id} in Security Hub in {self.account_id} in {self.region}"
        )
        try:
            self.client.create_members(
                AccountDetails=[{"AccountId": account_id, "Email": account_email}]
            )
            logger.debug(
                f"Created member {account_id} in Security Hub in {self.account_id} in {self.region}"
            )
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "ResourceConflictException":
                logger.exception(
                    f"Unable to create member {account_id} in Security Hub in {self.account_id} in {self.region}"
                )
                raise error

    def invite_member(self, account_id: str) -> None:
        """
        Invite a Security Hub member
        """
        logger.info(
            f"Inviting member {account_id} in Security Hub in {self.account_id} in {self.region}"
        )
        try:
            self.client.invite_members(AccountIds=[account_id])
            logger.debug(
                f"Invited member {account_id} in Security Hub in {self.account_id} in {self.region}"
            )
        except botocore.exceptions.ClientError as error:
            if error.response["Error"]["Code"] != "ResourceConflictException":
                logger.exception(
                    f"Unable to invite member {account_id} in Security Hub in {self.account_id} in {self.region}"
                )
                raise error

    def accept_invitations(self, audit_account_id: str) -> None:
        """
        Accept Security Hub invitations
        """
        paginator = self.client.get_paginator("list_invitations")
        page_iterator = paginator.paginate()
        for page in page_iterator:
            for invitation in page.get("Invitations", []):
                logger.info(
                    f"Accepting invitation for {self.account_id} from {audit_account_id} in {self.region}"
                )
                self.client.accept_invitation(
                    MasterId=audit_account_id, InvitationId=invitation["InvitationId"]
                )
                logger.debug(
                    f"Accepted invitation for {self.account_id} from {audit_account_id} in {self.region}"
                )
