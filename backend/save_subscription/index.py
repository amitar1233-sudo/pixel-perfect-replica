"""flight-save-subscription — POST /subscribe {email, plan_name, target_price}.

M2: a new (or unpaid / expired) subscription is written as
subscription_status=pending_payment and the response is an auto-submit HTML
form that sends the browser to ECPay's 定期定額 cashier. The ECPay callbacks
(flight-ecpay-return / -period) are the only writers of `active`.

A row that is still entitled (active, or cancelled but inside its paid period)
only gets its target price updated in place, and the response is JSON.
"""
import html
import json
import os
import re
import secrets as pysecrets
from decimal import Decimal, InvalidOperation

import boto3

import ecpay

PLANS = {
    "tokyo": {"origin": "TPE", "destination": "TYO", "label": "台北-東京"},
    "seoul": {"origin": "TPE", "destination": "SEL", "label": "台北-首爾"},
    "london": {"origin": "TPE", "destination": "LON", "label": "台北-倫敦"},
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
API_BASE = os.environ.get("API_BASE", "").strip().rstrip("/")
# M = monthly (production). Set PERIOD_TYPE=D to test the renewal callback the next day.
PERIOD_TYPE = os.environ.get("PERIOD_TYPE", "M").strip() or "M"
table = boto3.resource("dynamodb").Table("subscriptions")


def _json(status, body):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, ensure_ascii=False)}


def _entitled(row, now):
    status = row.get("subscription_status")
    if status == "active":
        return True
    if status == "cancelled" and row.get("current_period_end"):
        return ecpay.parse_ts(row["current_period_end"]) >= now
    return False


def _trade_no(now):
    # <=20 chars, alphanumeric, unique: FP + yymmddHHMMSS + 4 hex = 18
    return "FP" + now.astimezone(ecpay.TW).strftime("%y%m%d%H%M%S") + pysecrets.token_hex(2).upper()


def checkout_form(email, route, plan, trade_no, now):
    cfg = ecpay.config()
    amount = str(int(cfg["amount"]))
    daily = PERIOD_TYPE == "D"
    params = {
        "MerchantID": cfg["merchant_id"],
        "MerchantTradeNo": trade_no,
        "MerchantTradeDate": now.astimezone(ecpay.TW).strftime("%Y/%m/%d %H:%M:%S"),
        "PaymentType": "aio",
        "TotalAmount": amount,
        "TradeDesc": "Flight Price Notifier monthly subscription",
        "ItemName": f"Flight Price Notifier {plan['label']} 月訂閱",
        "ReturnURL": f"{API_BASE}/ecpay-return",
        "OrderResultURL": f"{API_BASE}/ecpay-result",
        "ChoosePayment": "Credit",
        "EncryptType": "1",
        "PeriodAmount": amount,
        "PeriodType": "D" if daily else "M",
        "Frequency": "1",
        "ExecTimes": "2" if daily else "999",
        "PeriodReturnURL": f"{API_BASE}/ecpay-period",
        "CustomField1": email,
        "CustomField2": route,
    }
    params["CheckMacValue"] = ecpay.gen_cmv(params, cfg["hash_key"], cfg["hash_iv"])
    action = ecpay.CASHIER.get(cfg.get("env", "stage"), ecpay.CASHIER["stage"])
    e = html.escape
    inputs = "\n".join(f'<input type="hidden" name="{e(k)}" value="{e(v)}">' for k, v in params.items())
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>前往綠界付款…</title></head>
<body><p style="font-family:sans-serif">正在前往綠界付款頁面… Redirecting to ECPay…</p>
<form id="ecpay" action="{e(action)}" method="post">
{inputs}
<noscript><button type="submit">前往付款 / Continue to payment</button></noscript>
</form>
<script>document.forms[0].submit()</script></body></html>"""


def handler(event, context):
    try:
        data = json.loads(event.get("body") or "{}")
    except (TypeError, ValueError):
        return _json(400, {"error": "invalid JSON body"})

    email = str(data.get("email", "")).strip().lower()
    plan_name = str(data.get("plan_name", "")).strip().lower()
    if not EMAIL_RE.match(email):
        return _json(400, {"error": "invalid email"})
    if plan_name not in PLANS:
        return _json(400, {"error": "plan_name must be one of: " + ", ".join(PLANS)})
    try:
        target = Decimal(str(data.get("target_price")))
    except (InvalidOperation, TypeError):
        return _json(400, {"error": "target_price must be a number"})
    if not target.is_finite() or target <= 0 or target > 1000000:
        return _json(400, {"error": "target_price must be between 1 and 1,000,000 TWD"})
    target = target.quantize(Decimal("1"))

    plan = PLANS[plan_name]
    route = f"{plan['origin']}-{plan['destination']}"
    now = ecpay.now_utc()
    now_s = ecpay.fmt(now)
    key = {"email": email, "route": route}
    common = {":p": plan_name, ":o": plan["origin"], ":d": plan["destination"],
              ":t": target, ":c": "TWD", ":n": now_s}
    base_set = ("plan_name = :p, origin = :o, destination = :d, target_price = :t, "
                "currency = :c, updated_at = :n, created_at = if_not_exists(created_at, :n)")

    row = table.get_item(Key=key).get("Item")
    if row and _entitled(row, now):
        # Paid (or in grace): just update the target, never knock status back.
        new = table.update_item(Key=key, UpdateExpression="SET " + base_set,
                                ExpressionAttributeValues=common, ReturnValues="ALL_NEW")["Attributes"]
        return _json(200, {"ok": True, "subscription": {
            k: (int(v) if isinstance(v, Decimal) else v) for k, v in new.items()}})

    if not API_BASE:
        return _json(500, {"error": "API_BASE not configured"})
    trade_no = _trade_no(now)
    try:
        # Only overwrite when the row is not active (guards a concurrent ReturnURL activation).
        table.update_item(
            Key=key,
            UpdateExpression="SET " + base_set + ", subscription_status = :s, merchant_trade_no = :m",
            ConditionExpression="attribute_not_exists(subscription_status) OR subscription_status <> :a",
            ExpressionAttributeValues={**common, ":s": "pending_payment", ":m": trade_no, ":a": "active"},
        )
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        return _json(409, {"error": "subscription is already active; reload the page"})
    print(f"{email} {route} pending_payment trade_no={trade_no} period={PERIOD_TYPE}")
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "body": checkout_form(email, route, plan, trade_no, now),
    }
