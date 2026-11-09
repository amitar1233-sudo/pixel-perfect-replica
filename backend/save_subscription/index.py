"""flight-save-subscription — POST /subscribe {email, plan_name, target_price}.

M1: no payment guard, so there is no subscription_status field.
"""
import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import boto3

PLANS = {
    "tokyo": {"origin": "TPE", "destination": "TYO"},
    "seoul": {"origin": "TPE", "destination": "SEL"},
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
table = boto3.resource("dynamodb").Table("subscriptions")


def _resp(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


def handler(event, context):
    try:
        data = json.loads(event.get("body") or "{}")
    except (TypeError, ValueError):
        return _resp(400, {"error": "invalid JSON body"})

    email = str(data.get("email", "")).strip().lower()
    plan_name = str(data.get("plan_name", "")).strip().lower()
    if not EMAIL_RE.match(email):
        return _resp(400, {"error": "invalid email"})
    if plan_name not in PLANS:
        return _resp(400, {"error": "plan_name must be tokyo or seoul"})
    try:
        target = Decimal(str(data.get("target_price")))
    except (InvalidOperation, TypeError):
        return _resp(400, {"error": "target_price must be a number"})
    if not target.is_finite() or target <= 0 or target > 1000000:
        return _resp(400, {"error": "target_price must be between 1 and 1,000,000 TWD"})
    target = target.quantize(Decimal("1"))

    plan = PLANS[plan_name]
    route = f"{plan['origin']}-{plan['destination']}"
    now = datetime.now(timezone.utc).isoformat()

    # Keep created_at on updates; refresh everything else.
    table.update_item(
        Key={"email": email, "route": route},
        UpdateExpression=(
            "SET plan_name = :p, origin = :o, destination = :d, target_price = :t, "
            "currency = :c, updated_at = :n, created_at = if_not_exists(created_at, :n)"
        ),
        ExpressionAttributeValues={
            ":p": plan_name,
            ":o": plan["origin"],
            ":d": plan["destination"],
            ":t": target,
            ":c": "TWD",
            ":n": now,
        },
    )
    return _resp(200, {
        "ok": True,
        "subscription": {
            "email": email, "route": route, "plan_name": plan_name,
            "target_price": int(target), "currency": "TWD", "updated_at": now,
        },
    })
