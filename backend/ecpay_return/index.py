"""flight-ecpay-return — POST /ecpay-return (ECPay ReturnURL, first 定期定額 charge).

Source of truth for activation: verify CheckMacValue + MerchantID, then flip
the row to active and set current_period_end. Idempotent on MerchantTradeNo.
Always reply plain-text 1|OK for authentic callbacks (else ECPay resends).
"""
import ecpay
import substore


def handler(event, context):
    p = ecpay.parse_form(event)
    trade = p.get("MerchantTradeNo", "")
    bad = ecpay.verify_callback(p)
    if bad:
        print(f"REJECT {trade}: {bad}")
        return ecpay.text(400, f"0|{bad}")
    print(f"return {trade} RtnCode={p.get('RtnCode')} RtnMsg={p.get('RtnMsg')} "
          f"SimulatePaid={p.get('SimulatePaid')} TotalSuccessTimes={p.get('TotalSuccessTimes')}")

    if p.get("SimulatePaid") == "1":
        print(f"{trade}: SimulatePaid=1 acknowledged, not activating")
        return ecpay.text(200, "1|OK")
    if p.get("RtnCode") != "1":
        print(f"{trade}: first authorization failed, row stays pending_payment")
        return ecpay.text(200, "1|OK")

    row = substore.find_row(p)
    if not row:
        print(f"{trade}: no subscription row for {p.get('CustomField1')} {p.get('CustomField2')}")
        return ecpay.text(200, "1|OK")

    now = ecpay.now_utc()
    end = ecpay.next_period_end(now, p.get("PeriodType", "M"), p.get("Frequency", "1"))
    try:
        substore.table.update_item(
            Key={"email": row["email"], "route": row["route"]},
            UpdateExpression=(
                "SET subscription_status = :a, merchant_trade_no = :m, current_period_end = :e, "
                "current_period_end_date = :ed, activated_at = :n, last_charged_at = :n, "
                "total_success_times = :one, failed_attempts = :zero, period_type = :pt, updated_at = :n"
            ),
            # Idempotent: a resend for the same trade no after activation is a no-op.
            ConditionExpression="NOT (subscription_status = :a AND merchant_trade_no = :m)",
            ExpressionAttributeValues={
                ":a": "active", ":m": trade, ":e": ecpay.fmt(end), ":ed": ecpay.tw_date(end),
                ":n": ecpay.fmt(now), ":one": 1, ":zero": 0, ":pt": p.get("PeriodType", "M"),
            },
        )
    except substore.table.meta.client.exceptions.ConditionalCheckFailedException:
        print(f"{trade}: already active (duplicate callback), acking")
        return ecpay.text(200, "1|OK")

    print(f"{row['email']} {row['route']} -> active until {ecpay.fmt(end)}")
    substore.enqueue_status("welcome", row, current_period_end_date=ecpay.tw_date(end))
    return ecpay.text(200, "1|OK")
