"""flight-fare-notification — SQS consumer that emails a fare alert via Resend.

Per message: dedup against notification_history, render NT$ email (+ optional
約 US$ line), POST to Resend, and write history only after a 2xx.
Failure classes: 429/5xx -> raise (SQS redelivers that message);
403/422/other 4xx -> log and drop (permanent, don't loop).
"""
import html
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"
FLOOR_HOURS = float(os.environ.get("NOTIFY_FLOOR_HOURS", "24"))
REALERT_PCT = float(os.environ.get("REALERT_PCT", "20"))
REALERT_ABS_TWD = float(os.environ.get("REALERT_ABS_TWD", "2000"))

CITY = {"TPE": "台北", "TYO": "東京", "SEL": "首爾", "LON": "倫敦"}

_secrets = boto3.client("secretsmanager")
_history = boto3.resource("dynamodb").Table("notification_history")
_resend = None


class Transient(Exception):
    """Retryable failure: let SQS redeliver the message."""


def _cfg():
    global _resend
    if _resend is None:
        _resend = json.loads(_secrets.get_secret_value(SecretId="flight/resend")["SecretString"])
    return _resend


# ---------- rendering ----------

def _nt(n):
    return f"NT${int(n):,}"


def _date(iso):
    return (iso or "")[:10]


def _ddmm(iso):
    d = _date(iso)
    return f"{d[8:10]}{d[5:7]}" if len(d) == 10 else ""


def _cities(route):
    o, _, d = route.partition("-")
    return CITY.get(o, o), CITY.get(d, d), o, d


def booking_url(fare, route, marker=None):
    _, _, o, d = _cities(route)
    path = f"{o}{_ddmm(fare.get('depart_date'))}{d}{_ddmm(fare.get('return_date'))}"
    url = f"https://www.aviasales.com/search/{path}"
    return f"{url}?marker={marker}" if marker else url


def subject(fare, route):
    oc, dc, _, _ = _cities(route)
    return f"✈️ {oc} → {dc} 降價通知！{_nt(fare['price'])} 已達標"


def render_html(fare, route, target_price, marker=None, usd_price=None):
    oc, dc, _, _ = _cities(route)
    e = html.escape
    usd = f'<p style="margin:4px 0 0;color:#555;font-size:14px">約 US${int(usd_price):,}</p>' if usd_price else ""
    ret = f" → 回程 {e(_date(fare.get('return_date')))}" if fare.get("return_date") else ""
    return f"""<!doctype html><html><body style="margin:0;padding:24px;font-family:-apple-system,Segoe UI,Helvetica,Arial,'Noto Sans TC',sans-serif;color:#222;background:#fff">
<div style="max-width:480px;margin:0 auto">
<p style="margin:0 0 8px;font-size:14px;color:#555">{e(oc)} → {e(dc)} 下個月最低票價</p>
<p style="margin:0;font-size:32px;font-weight:700">{e(_nt(fare['price']))}</p>
{usd}
<p style="margin:16px 0 0;font-size:14px">你的目標價：{e(_nt(target_price))} ✅ 已達標</p>
<p style="margin:4px 0 0;font-size:14px;color:#555">航空公司 {e(str(fare.get('airline') or '-'))} · 去程 {e(_date(fare.get('depart_date')))}{ret}</p>
<p style="margin:24px 0"><a href="{e(booking_url(fare, route, marker))}" style="display:inline-block;padding:12px 20px;background:#222;color:#fff;text-decoration:none;border-radius:6px;font-weight:600">立即訂購</a></p>
<p style="margin:0;font-size:12px;color:#888">票價隨時變動，以訂購頁面為準。你收到這封信是因為你在 Flight Price Notifier 訂閱了這條航線。</p>
</div></body></html>"""


def render_text(fare, route, target_price, marker=None, usd_price=None):
    oc, dc, _, _ = _cities(route)
    lines = [f"{oc} → {dc} 下個月最低票價：{_nt(fare['price'])}"]
    if usd_price:
        lines.append(f"約 US${int(usd_price):,}")
    lines += [
        f"你的目標價：{_nt(target_price)}（已達標）",
        f"航空公司 {fare.get('airline') or '-'} · 去程 {_date(fare.get('depart_date'))}"
        + (f" → 回程 {_date(fare.get('return_date'))}" if fare.get("return_date") else ""),
        "",
        f"立即訂購：{booking_url(fare, route, marker)}",
        "",
        "票價隨時變動，以訂購頁面為準。",
    ]
    return "\n".join(lines)


# ---------- dedup ----------

def should_send(pk, new_price, now):
    items = _history.query(KeyConditionExpression=Key("pk").eq(pk),
                           ScanIndexForward=False, Limit=1).get("Items", [])
    if not items:
        return True, "first alert"
    last = items[0]
    last_at = datetime.fromisoformat(last["sent_at"])
    if now - last_at >= timedelta(hours=FLOOR_HOURS):
        return True, f"last alert {last['sent_at']} is older than {FLOOR_HOURS:g}h"
    last_price = float(last.get("price", 0))
    if new_price <= last_price * (1 - REALERT_PCT / 100) or (last_price - new_price) >= REALERT_ABS_TWD:
        return True, f"big drop {last_price:g} -> {new_price:g}"
    return False, f"last alert {last['sent_at']} at {last_price:g} within {FLOOR_HOURS:g}h"


# ---------- send ----------

def send_email(to, subj, html_body, text_body):
    cfg = _cfg()
    payload = {"from": cfg["from"], "to": to, "subject": subj, "html": html_body, "text": text_body}
    req = urllib.request.Request(
        "https://api.resend.com/emails", data=json.dumps(payload).encode(), method="POST",
        headers={"Authorization": "Bearer " + cfg["api_key"], "Content-Type": "application/json",
                 "User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as ex:
        body = ex.read().decode(errors="replace")
        if ex.code == 429 or ex.code >= 500:
            raise Transient(f"resend {ex.code}: {body}")
        return ex.code, body
    except (urllib.error.URLError, TimeoutError) as ex:
        raise Transient(f"resend network error: {ex}")


def process(msg):
    email, route = msg["email"], msg["route"]
    fare = msg["cheapest"]
    price = float(fare["price"])
    pk = f"{email}#{route}"
    now = datetime.now(timezone.utc)

    ok, why = should_send(pk, price, now)
    if not ok:
        print(f"{pk} skipped (deduped): {why}")
        return
    usd = (msg.get("cheapest_usd") or {}).get("price")
    marker = _cfg().get("marker")  # optional affiliate marker; usually absent
    status, body = send_email(
        email, subject(fare, route),
        render_html(fare, route, msg["target_price"], marker=marker, usd_price=usd),
        render_text(fare, route, msg["target_price"], marker=marker, usd_price=usd),
    )
    if 200 <= status < 300:
        _history.put_item(Item={
            "pk": pk, "sent_at": now.isoformat(), "email": email, "route": route,
            "price": Decimal(str(fare["price"])), "currency": "TWD",
        })
        print(f"{pk} sent ({why}) {int(price)} TWD -> RESEND_OK {status} {body}")
    else:
        print(f"{pk} dropped: permanent Resend error {status} {body}")


def handler(event, context):
    failures = []
    for rec in event.get("Records", []):
        try:
            process(json.loads(rec["body"]))
        except Transient as ex:
            print("transient, will retry:", ex)
            failures.append({"itemIdentifier": rec["messageId"]})
        except (ValueError, KeyError, TypeError) as ex:
            print("malformed message dropped:", ex, rec.get("body"))
    return {"batchItemFailures": failures}
