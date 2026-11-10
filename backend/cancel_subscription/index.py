"""flight-cancel-subscription — POST /cancel {email, route}.

Stops future ECPay charges with CreditCardPeriodAction Action=Cancel, then
sets subscription_status=cancelled while keeping current_period_end (grace:
the parser keeps alerting until that date, then flips the row to expired).

Security note: like GET /subscriptions this trusts the client-supplied email
(no auth guard in this course); production should verify the Supabase JWT.
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

import ecpay
import substore

UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"
NOT_FOUND = "90100150"  # stage: order never existed at ECPay (e.g. synthetic test rows)


def _json(status, body):
    return {"statusCode": status, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body, ensure_ascii=False)}


def ecpay_cancel(trade_no):
    cfg = ecpay.config()
    params = {"MerchantID": cfg["merchant_id"], "MerchantTradeNo": trade_no,
              "Action": "Cancel", "TimeStamp": str(int(time.time()))}
    params["CheckMacValue"] = ecpay.gen_cmv(params, cfg["hash_key"], cfg["hash_iv"])
    url = ecpay.PERIOD_ACTION.get(cfg.get("env", "stage"), ecpay.PERIOD_ACTION["stage"])
    req = urllib.request.Request(url, data=urllib.parse.urlencode(params).encode(), method="POST",
                                 headers={"Content-Type": "application/x-www-form-urlencoded",
                                          "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read().decode("utf-8", errors="replace")
    return {k: v[0] for k, v in urllib.parse.parse_qs(raw, keep_blank_values=True).items()}, raw


def handler(event, context):
    try:
        data = json.loads(event.get("body") or "{}")
    except (TypeError, ValueError):
        return _json(400, {"error": "invalid JSON body"})
    email = str(data.get("email", "")).strip().lower()
    route = str(data.get("route", "")).strip()
    if "@" not in email or not route:
        return _json(400, {"error": "email and route are required"})

    key = {"email": email, "route": route}
    row = substore.table.get_item(Key=key).get("Item")
    if not row:
        return _json(404, {"error": "subscription not found"})
    status = row.get("subscription_status")
    if status == "cancelled":
        return _json(200, {"ok": True, "subscription": _plain(row)})
    if status != "active":
        return _json(409, {"error": f"only an active subscription can be cancelled (is {status or 'unpaid'})"})

    trade = row.get("merchant_trade_no")
    if trade:
        try:
            res, raw = ecpay_cancel(trade)
        except (urllib.error.URLError, TimeoutError) as ex:
            print(f"{trade}: CreditCardPeriodAction network error {ex}")
            return _json(502, {"error": "payment provider unreachable, please retry"})
        print(f"{trade}: CreditCardPeriodAction -> {raw}")
        code = res.get("RtnCode")
        if code != "1" and code != NOT_FOUND:
            return _json(502, {"error": f"ECPay cancel failed: {res.get('RtnMsg') or raw}"})
        if code == NOT_FOUND:
            print(f"{trade}: {NOT_FOUND} order not found at ECPay (expected for synthetic rows), cancelling locally")

    now = ecpay.now_utc()
    end_s = row.get("current_period_end") or ecpay.fmt(ecpay.add_months(now, 1))  # migration fallback
    end = ecpay.parse_ts(end_s)
    new = substore.table.update_item(
        Key=key,
        UpdateExpression=("SET subscription_status = :c, current_period_end = :e, "
                          "current_period_end_date = :ed, cancelled_at = :n, updated_at = :n"),
        ExpressionAttributeValues={":c": "cancelled", ":e": end_s, ":ed": ecpay.tw_date(end),
                                   ":n": ecpay.fmt(now)},
        ReturnValues="ALL_NEW",
    )["Attributes"]
    substore.enqueue_status("cancel", new, current_period_end_date=ecpay.tw_date(end))
    print(f"{key} -> cancelled, service until {end_s}")
    return _json(200, {"ok": True, "subscription": _plain(new)})


def _plain(row):
    return {k: (int(v) if hasattr(v, "to_integral_value") else v) for k, v in row.items()}
