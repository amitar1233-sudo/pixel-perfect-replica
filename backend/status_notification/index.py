"""flight-status-notification — single SQS consumer for flight-status-queue.

Routes on message["event_type"]: "welcome" (first payment) or "cancel"
(subscription cancelled; service continues until current_period_end_date).
Same Resend failure classes as flight-fare-notification: 429/5xx retry,
other 4xx drop.
"""
import html
import json
import urllib.error
import urllib.request

import boto3

UA = "Mozilla/5.0 (compatible; flight-notifier/1.0)"
CITY = {"TPE": "台北", "TYO": "東京", "SEL": "首爾", "LON": "倫敦"}
SITE = "https://pixel-perfect-replica-agey.vercel.app/app"

_secrets = boto3.client("secretsmanager")
_resend = None


class Transient(Exception):
    pass


def _cfg():
    global _resend
    if _resend is None:
        _resend = json.loads(_secrets.get_secret_value(SecretId="flight/resend")["SecretString"])
    return _resend


def _route_label(route):
    o, _, d = route.partition("-")
    return f"{CITY.get(o, o)} → {CITY.get(d, d)}"


def render(msg):
    label = _route_label(msg["route"])
    until = msg.get("current_period_end_date") or ""
    if msg["event_type"] == "welcome":
        subj = f"✅ 訂閱成功：{label} 機票降價通知已啟用"
        lines = [f"感謝訂閱！{label} 的降價通知已啟用。",
                 f"本期有效至 {until}，之後每月自動續訂。" if until else "之後每月自動續訂。",
                 "票價達到你的目標價時，我們會寄信通知你。"]
    elif msg["event_type"] == "cancel":
        subj = f"已取消訂閱：{label} 機票降價通知"
        lines = [f"你已取消 {label} 的訂閱，之後不會再扣款。",
                 f"在 {until} 之前你仍會收到降價通知。" if until else "目前這一期結束前你仍會收到降價通知。",
                 "隨時可以回來重新訂閱。"]
    else:
        raise ValueError(f"unknown event_type {msg['event_type']!r}")
    text = "\n".join(lines + ["", f"管理訂閱：{SITE}"])
    body = "".join(f'<p style="margin:0 0 12px">{html.escape(l)}</p>' for l in lines)
    html_body = (
        '<!doctype html><html><body style="margin:0;padding:24px;font-family:-apple-system,Segoe UI,'
        "Helvetica,Arial,'Noto Sans TC',sans-serif;color:#222;background:#fff\">"
        f'<div style="max-width:480px;margin:0 auto"><h2 style="margin:0 0 16px">{html.escape(subj)}</h2>{body}'
        f'<p style="margin:24px 0"><a href="{SITE}" style="display:inline-block;padding:12px 20px;'
        'background:#222;color:#fff;text-decoration:none;border-radius:6px;font-weight:600">管理訂閱</a></p>'
        "</div></body></html>"
    )
    return subj, html_body, text


def send(to, subj, html_body, text_body):
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


def handler(event, context):
    failures = []
    for rec in event.get("Records", []):
        try:
            msg = json.loads(rec["body"])
            status, body = send(msg["email"], *render(msg))
            tag = "RESEND_OK" if 200 <= status < 300 else "dropped: permanent Resend error"
            print(f"{msg['event_type']} {msg['email']} {msg['route']} -> {tag} {status} {body}")
        except Transient as ex:
            print("transient, will retry:", ex)
            failures.append({"itemIdentifier": rec["messageId"]})
        except (ValueError, KeyError, TypeError) as ex:
            print("malformed message dropped:", ex, rec.get("body"))
    return {"batchItemFailures": failures}
