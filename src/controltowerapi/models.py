#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, UTCDateTimeAttribute
from pynamodb.indexes import GlobalSecondaryIndex, KeysOnlyProjection

ACCOUNT_TABLE = os.environ["ACCOUNT_TABLE"]


class StatusIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "AccountStatus"
        read_capacity_units = 0
        write_capacity_units = 0
        projection = KeysOnlyProjection()

    status = UnicodeAttribute(hash_key=True)
    account_name = UnicodeAttribute(range_key=True)


class AccountModel(Model):
    class Meta:
        table_name = ACCOUNT_TABLE

    account_name = UnicodeAttribute(hash_key=True)
    account_email = UnicodeAttribute()
    account_id = UnicodeAttribute()
    sso_user_email = UnicodeAttribute()
    sso_user_first_name = UnicodeAttribute()
    sso_user_last_name = UnicodeAttribute()
    record_id = UnicodeAttribute()
    ou_name = UnicodeAttribute()
    ou_id = UnicodeAttribute()

    # QUEUED, CREATED, IN_PROGRESS, IN_PROGRESS_IN_ERROR, SUCCEEDED, FAILED
    status = UnicodeAttribute()
    status_message = UnicodeAttribute()
    status_index = StatusIndex()

    callback_url = UnicodeAttribute()
    callback_secret = UnicodeAttribute()

    queued_at = UTCDateTimeAttribute()
    created_at = UTCDateTimeAttribute()
    updated_at = UTCDateTimeAttribute()
