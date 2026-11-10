"""flight-ecpay-result — ANY /ecpay-result (ECPay OrderResultURL, browser POST).

UX only: turns ECPay's browser POST into a 302 back to the SPA (a static host
would 405 on the POST). Never activates anything; ReturnURL does that.
"""
import os

import ecpay

SITE_URL = os.environ.get("SITE_URL", "https://pixel-perfect-replica-agey.vercel.app").strip().rstrip("/")


def handler(event, context):
    p = ecpay.parse_form(event) if event.get("body") else {}
    ok = p.get("RtnCode", "1") == "1"
    return {"statusCode": 302,
            "headers": {"Location": f"{SITE_URL}/app?purchase={'success' if ok else 'failed'}"},
            "body": ""}
