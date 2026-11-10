"""Shared ECPay helpers, bundled into each Lambda zip by backend/deploy.py.

stdlib + boto3 only. CheckMacValue follows ECPay's SHA256 algorithm and is
checked against .claude/skills/ecpay/test-vectors/checkmacvalue.json.
"""
import base64
import calendar
import hashlib
import hmac
import json
import urllib.parse
from datetime import datetime, timedelta, timezone

import boto3

CASHIER = {
    "stage": "https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5",
    "prod": "https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5",
}
PERIOD_ACTION = {
    "stage": "https://payment-stage.ecpay.com.tw/Cashier/CreditCardPeriodAction",
    "prod": "https://payment.ecpay.com.tw/Cashier/CreditCardPeriodAction",
}
TS_FMT = "%Y-%m-%dT%H:%M:%SZ"
TW = timezone(timedelta(hours=8))

_cfg = None


def config():
    global _cfg
    if _cfg is None:
        raw = boto3.client("secretsmanager").get_secret_value(SecretId="flight/ecpay")["SecretString"]
        _cfg = json.loads(raw)
    return _cfg


# ---------- CheckMacValue ----------

def ecpay_url_encode(s):
    e = urllib.parse.quote_plus(str(s)).replace("~", "%7E").lower()
    for old, new in (("%2d", "-"), ("%5f", "_"), ("%2e", "."), ("%21", "!"),
                     ("%2a", "*"), ("%28", "("), ("%29", ")")):
        e = e.replace(old, new)
    return e


def gen_cmv(params, hash_key, hash_iv):
    items = {k: v for k, v in params.items() if k != "CheckMacValue"}
    body = "&".join(f"{k}={items[k]}" for k in sorted(items, key=str.lower))
    raw = ecpay_url_encode(f"HashKey={hash_key}&{body}&HashIV={hash_iv}")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()


def verify_cmv(params, hash_key, hash_iv):
    got = str(params.get("CheckMacValue", ""))
    return bool(got) and hmac.compare_digest(gen_cmv(params, hash_key, hash_iv), got.upper())


# ---------- callback plumbing ----------

def parse_form(event):
    """Form-urlencoded body -> flat dict. Keeps empty fields (they are signed)."""
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    return {k: v[0] for k, v in urllib.parse.parse_qs(body, keep_blank_values=True).items()}


def text(status, body):
    return {"statusCode": status, "headers": {"Content-Type": "text/plain; charset=utf-8"}, "body": body}


def verify_callback(params):
    """Return None if the callback is authentic, else a short reason."""
    cfg = config()
    if not verify_cmv(params, cfg["hash_key"], cfg["hash_iv"]):
        return "CheckMacValue Error"
    if params.get("MerchantID") != cfg["merchant_id"]:
        return "MerchantID Error"
    return None


# ---------- dates ----------

def now_utc():
    return datetime.now(timezone.utc).replace(microsecond=0)


def fmt(dt):
    return dt.astimezone(timezone.utc).strftime(TS_FMT)


def parse_ts(s):
    return datetime.strptime(s, TS_FMT).replace(tzinfo=timezone.utc)


def add_months(dt, n=1):
    m = dt.month - 1 + n
    y, m = dt.year + m // 12, m % 12 + 1
    return dt.replace(year=y, month=m, day=min(dt.day, calendar.monthrange(y, m)[1]))


def next_period_end(start, period_type="M", frequency=1):
    f = int(frequency or 1)
    if period_type == "D":
        return start + timedelta(days=f)
    if period_type == "Y":
        return add_months(start, 12 * f)
    return add_months(start, f)


def tw_date(dt):
    return dt.astimezone(TW).strftime("%Y-%m-%d")
