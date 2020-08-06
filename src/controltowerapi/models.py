#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os

from pynamodb.models import Model
from pynamodb.attributes import UnicodeAttribute, UTCDateTimeAttribute

ACCOUNT_TABLE = os.environ["ACCOUNT_TABLE"]


class AccountModel(Model):
    class Meta:
        table_name = ACCOUNT_TABLE

    account_name = UnicodeAttribute(hash_key=True)
    account_id = UnicodeAttribute()
    record_id = UnicodeAttribute()
    ou_name = UnicodeAttribute()
    ou_id = UnicodeAttribute()
    state = UnicodeAttribute()
    callback_url = UnicodeAttribute()
    callback_secret = UnicodeAttribute()
    created_at = UTCDateTimeAttribute()
