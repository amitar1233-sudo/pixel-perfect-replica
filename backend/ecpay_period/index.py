"""flight-ecpay-period — POST /ecpay-period (ECPay PeriodReturnURL, 2nd charge onward).

Success: keep active and extend current_period_end by one period.
Failure: count it; ECPay retries and ends the series after 6 consecutive
failures, so only then flip to expired. When the last scheduled charge
(TotalSuccessTimes == ExecTimes) succeeds the series is over, so the row moves
to cancelled and the parser expires it once the paid period ends.
"""
import ecpay
import substore

MAX_FAILURES = 6


def handler(event, context):
    p = ecpay.parse_form(event)
    trade = p.get("MerchantTradeNo", "")
    bad = ecpay.verify_callback(p)
    if bad:
        print(f"REJECT {trade}: {bad}")
        return ecpay.text(400, f"0|{bad}")
    print(f"period {trade} RtnCode={p.get('RtnCode')} RtnMsg={p.get('RtnMsg')} "
          f"SimulatePaid={p.get('SimulatePaid')} TotalSuccessTimes={p.get('TotalSuccessTimes')} "
          f"ExecTimes={p.get('ExecTimes')}")

    if p.get("SimulatePaid") == "1":
        print(f"{trade}: SimulatePaid=1 acknowledged, no bookkeeping")
        return ecpay.text(200, "1|OK")

    row = substore.find_row(p)
    if not row:
        print(f"{trade}: no subscription row found")
        return ecpay.text(200, "1|OK")
    key = {"email": row["email"], "route": row["route"]}
    now = ecpay.now_utc()
    errors = substore.table.meta.client.exceptions

    if p.get("RtnCode") == "1":
        successes = int(p.get("TotalSuccessTimes") or 0)
        start = max(now, ecpay.parse_ts(row["current_period_end"])) if row.get("current_period_end") else now
        end = ecpay.next_period_end(start, p.get("PeriodType", row.get("period_type", "M")),
                                    p.get("Frequency", "1"))
        series_done = bool(p.get("ExecTimes")) and successes >= int(p["ExecTimes"])
        status = "cancelled" if series_done else "active"
        try:
            substore.table.update_item(
                Key=key,
                UpdateExpression=(
                    "SET subscription_status = :s, current_period_end = :e, current_period_end_date = :ed, "
                    "last_charged_at = :n, total_success_times = :c, failed_attempts = :zero, updated_at = :n"
                ),
                # Idempotent per charge: ignore a resend of a charge we already counted.
                ConditionExpression="attribute_not_exists(total_success_times) OR total_success_times < :c",
                ExpressionAttributeValues={":s": status, ":e": ecpay.fmt(end), ":ed": ecpay.tw_date(end),
                                           ":n": ecpay.fmt(now), ":c": successes, ":zero": 0},
            )
        except errors.ConditionalCheckFailedException:
            print(f"{trade}: charge #{successes} already recorded, acking")
            return ecpay.text(200, "1|OK")
        print(f"{key} renewal #{successes} ok -> {status} until {ecpay.fmt(end)}")
        return ecpay.text(200, "1|OK")

    failures = int(row.get("failed_attempts") or 0) + 1
    status = "expired" if failures >= MAX_FAILURES else row.get("subscription_status", "active")
    substore.table.update_item(
        Key=key,
        UpdateExpression="SET failed_attempts = :f, subscription_status = :s, last_failed_at = :n, updated_at = :n",
        ExpressionAttributeValues={":f": failures, ":s": status, ":n": ecpay.fmt(now)},
    )
    print(f"{key} renewal failed ({failures}/{MAX_FAILURES}) -> {status}")
    return ecpay.text(200, "1|OK")
