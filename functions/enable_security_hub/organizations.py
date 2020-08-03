#!/usr/bin/env python
# -*- coding: utf-8 -*-

import boto3

CT_AUDIT_ACCOUNT_NAME = "Audit"


class Organizations:
    def __init__(self) -> None:
        self.client = boto3.client("organizations")

    def get_audit_account_id(self) -> str:
        """
        Return the Control Tower Audit account
        """
        paginator = self.client.get_paginator("list_accounts")
        page_iterator = paginator.paginate()
        for page in page_iterator:
            for account in page.get("Accounts", []):
                if account.get("Name") == CT_AUDIT_ACCOUNT_NAME:
                    return account["Id"]
        return None

    def get_account_email(self, account_id) -> str:
        """
        Return the email address for an account
        """
        response = self.client.describe_account(AccountId=account_id)
        return response.get("Account", {}).get("Email")
