"""flight-parser — one route per invocation.

Event: {"origin": "TPE", "destination": "TYO", "route": "TPE-TYO"}
Fetches next month's cheapest fare in TWD (the gate) and, best effort, USD
(supplementary). Every subscriber on the route whose target_price >= the TWD
fare gets a message on flight-fare-queue. M1: no subscription_status filter.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr

UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"
QUEUE_NAME = os.environ.get("QUEUE_NAME", "flight-fare-queue")

_secrets = boto3.client("secretsmanager")
_sqs = boto3.client("sqs")
_table = boto3.resource("dynamodb").Table("subscriptions")
_token = None
_qurl = None


def _get_token():
    global _token
    if _token is None:
        raw = _secrets.get_secret_value(SecretId="flight/travelpayouts")["SecretString"]
        try:
            _token = json.loads(raw)["token"]
        except (ValueError, KeyError, TypeError):
            _token = raw.strip()
    return _token


def _queue_url():
    global _qurl
    if _qurl is None:
        _qurl = _sqs.get_queue_url(QueueName=QUEUE_NAME)["QueueUrl"]
    return _qurl


def next_month(today=None):
    d = today or date.today()
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return f"{y:04d}-{m:02d}"


def fetch_cheapest(origin, destination, month, token, currency):
    q = urllib.parse.urlencode({
        "origin": origin, "destination": destination, "depart_date": month,
        "currency": currency, "token": token,
    })
    req = urllib.request.Request(
        f"https://api.travelpayouts.com/v1/prices/cheap?{q}",
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = json.loads(r.read())
    except urllib.error.HTTPError as ex:
        print(f"travelpayouts {currency} HTTP {ex.code} for {origin}-{destination}")
        return None
    except (urllib.error.URLError, TimeoutError, ValueError) as ex:
        print(f"travelpayouts {currency} error for {origin}-{destination}: {ex}")
        return None
    if not body.get("success") or not body.get("data"):
        return None
    offers = body["data"].get(destination, {})
    if not offers:
        return None
    best = min(offers.values(), key=lambda o: o["price"])
    return {
        "price": best["price"], "currency": currency.upper(), "airline": best.get("airline"),
        "depart_date": best.get("departure_at"), "return_date": best.get("return_at"),
    }


def _subscribers(route):
    kwargs = {"FilterExpression": Attr("route").eq(route)}
    while True:
        page = _table.scan(**kwargs)
        yield from page.get("Items", [])
        if "LastEvaluatedKey" not in page:
            return
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def handler(event, context):
    origin, destination = event["origin"], event["destination"]
    route = event.get("route") or f"{origin}-{destination}"
    month = event.get("month") or next_month()
    token = _get_token()

    tw = fetch_cheapest(origin, destination, month, token, "twd")
    if not tw:
        print("no TWD fare for", route, month, "(empty/429) - skipping")
        return {"ok": True, "route": route, "matched": 0}
    print(f"{route} {month} cheapest {tw['price']} TWD ({tw['airline']}, {tw['depart_date']})")

    us = fetch_cheapest(origin, destination, month, token, "usd")  # may be None; never block on it
    if us:
        print(f"{route} {month} cheapest {us['price']} USD (supplementary)")

    matched = 0
    for it in _subscribers(route):
        tp = it.get("target_price")
        if tp is None or Decimal(tp) < Decimal(str(tw["price"])):
            continue
        body = {
            "email": it["email"], "route": route, "plan_name": it.get("plan_name"),
            "target_price": int(tp),
            "cheapest": {"price": tw["price"], "currency": "TWD", "airline": tw["airline"],
                         "depart_date": tw["depart_date"], "return_date": tw["return_date"]},
        }
        if us:
            body["cheapest_usd"] = {"price": us["price"], "currency": "USD", "airline": us["airline"],
                                    "depart_date": us["depart_date"], "return_date": us["return_date"]}
        _sqs.send_message(QueueUrl=_queue_url(), MessageBody=json.dumps(body))
        matched += 1
    print(f"{route}: {matched} subscriber(s) matched at target >= {tw['price']} TWD")
    return {"ok": True, "route": route, "matched": matched, "cheapest_twd": tw["price"]}
