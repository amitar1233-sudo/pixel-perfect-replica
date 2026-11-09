"""flight-list-subscriptions — GET /subscriptions?email=...

Security note: this trusts a client-supplied email with no auth. That is
acceptable for this course's no-guard M1; production should verify the
Supabase JWT here before querying.
"""
import json
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

table = boto3.resource("dynamodb").Table("subscriptions")


def _plain(v):
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    return v


def handler(event, context):
    params = event.get("queryStringParameters") or {}
    email = str(params.get("email", "")).strip().lower()
    if "@" not in email:
        return {"statusCode": 400, "headers": {"Content-Type": "application/json"},
                "body": json.dumps({"error": "email query parameter required"})}
    items = table.query(KeyConditionExpression=Key("email").eq(email)).get("Items", [])
    rows = [{k: _plain(v) for k, v in it.items()} for it in items]
    return {"statusCode": 200, "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"subscriptions": rows}, ensure_ascii=False)}
