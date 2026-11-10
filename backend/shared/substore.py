"""Shared DynamoDB + status-queue helpers for the M2 payment Lambdas."""
import json
import os

import boto3
from boto3.dynamodb.conditions import Attr

STATUS_QUEUE = os.environ.get("STATUS_QUEUE", "flight-status-queue")

table = boto3.resource("dynamodb").Table("subscriptions")
_sqs = boto3.client("sqs")
_qurl = None


def find_row(params):
    """Locate the row via CustomField1/2 (email/route), falling back to the trade no."""
    email = (params.get("CustomField1") or "").strip().lower()
    route = (params.get("CustomField2") or "").strip()
    if email and route:
        row = table.get_item(Key={"email": email, "route": route}).get("Item")
        if row:
            return row
    trade = params.get("MerchantTradeNo")
    if not trade:
        return None
    kwargs = {"FilterExpression": Attr("merchant_trade_no").eq(trade)}
    while True:
        page = table.scan(**kwargs)
        if page.get("Items"):
            return page["Items"][0]
        if "LastEvaluatedKey" not in page:
            return None
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def enqueue_status(event_type, row, **extra):
    global _qurl
    if _qurl is None:
        _qurl = _sqs.get_queue_url(QueueName=STATUS_QUEUE)["QueueUrl"]
    body = {"event_type": event_type, "email": row["email"], "route": row["route"],
            "plan_name": row.get("plan_name"), **extra}
    _sqs.send_message(QueueUrl=_qurl, MessageBody=json.dumps(body, ensure_ascii=False))
