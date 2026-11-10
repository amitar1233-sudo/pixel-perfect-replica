import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  MONTHLY_PRICE,
  PLANS,
  cancelSubscription,
  listSubscriptions,
  subscribe,
  type PlanName,
  type Subscription,
  type SubscriptionStatus,
} from "@/lib/flightApi";

const nt = (n: number) => `NT$${n.toLocaleString("en-US")}`;

/** Effective status: a cancelled row past its paid period is already over. */
function statusOf(sub: Subscription | undefined): SubscriptionStatus | undefined {
  if (!sub) return undefined;
  const s = sub.subscription_status ?? "pending_payment";
  if (
    s === "cancelled" &&
    sub.current_period_end &&
    new Date(sub.current_period_end) < new Date()
  ) {
    return "expired";
  }
  return s;
}

const BADGE: Record<SubscriptionStatus, { text: string; cls: string }> = {
  active: { text: "已訂閱 Active", cls: "bg-primary text-primary-foreground" },
  pending_payment: { text: "未完成付款 Unpaid", cls: "bg-destructive/15 text-destructive" },
  cancelled: { text: "已取消 Cancelled", cls: "bg-muted text-foreground" },
  expired: { text: "已結束 Ended", cls: "bg-muted text-muted-foreground" },
};

function PlanCard({
  email,
  plan,
  sub,
  onSaved,
}: {
  email: string;
  plan: (typeof PLANS)[number];
  sub: Subscription | undefined;
  onSaved: (s: Subscription) => void;
}) {
  const status = statusOf(sub);
  const entitled = status === "active" || status === "cancelled";
  const [value, setValue] = useState(String(sub?.target_price ?? plan.hint + 1000));
  const [editing, setEditing] = useState(!entitled);
  const [busy, setBusy] = useState<null | "save" | "cancel">(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (sub) setValue(String(sub.target_price));
    setEditing(!entitled);
  }, [sub, entitled]);

  const save = async () => {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) {
      setError("請輸入有效的台幣金額 / Enter a valid TWD amount");
      return;
    }
    setBusy("save");
    setError(null);
    try {
      const r = await subscribe(email, plan.plan_name, Math.round(n));
      if (r === "redirecting") return; // the page is now ECPay's checkout form
      onSaved(r);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const cancel = async () => {
    if (!sub) return;
    const ok = window.confirm(
      `確定取消 ${plan.label} 的訂閱？之後不再扣款，目前這一期結束前仍會收到通知。\nCancel this subscription? You keep alerts until the current period ends.`,
    );
    if (!ok) return;
    setBusy("cancel");
    setError(null);
    try {
      onSaved(await cancelSubscription(email, sub.route));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const payLabel =
    status === "pending_payment"
      ? `完成付款 / Pay ${nt(MONTHLY_PRICE)}`
      : status === "expired"
        ? `重新訂閱 / Resubscribe ${nt(MONTHLY_PRICE)}/月`
        : `訂閱 ${nt(MONTHLY_PRICE)}/月 / Subscribe`;
  const inputId = `target-${plan.plan_name}`;

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-card backdrop-blur-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">{plan.label}</h2>
          <p className="mt-1 text-xs text-muted-foreground">{plan.route}</p>
        </div>
        {status && (
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${BADGE[status].cls}`}>
            {BADGE[status].text}
          </span>
        )}
      </div>

      {status === "active" && sub?.current_period_end_date && (
        <p className="mt-3 text-xs text-muted-foreground">
          每月自動續訂 · 下次扣款約 {sub.current_period_end_date} · Renews monthly
        </p>
      )}
      {status === "cancelled" && (
        <p className="mt-3 text-xs text-muted-foreground">
          有效至 {sub?.current_period_end_date ?? "本期結束"}（仍會通知到該日）· Alerts continue
          until then
        </p>
      )}
      {status === "pending_payment" && (
        <p className="mt-3 text-xs text-muted-foreground">
          完成付款後才會開始寄送降價通知 · Alerts start once payment completes
        </p>
      )}

      {sub && entitled && !editing ? (
        <div className="mt-6">
          <p className="text-sm text-muted-foreground">目前目標價 / Current target</p>
          <p className="mt-1 text-3xl font-bold">{nt(sub.target_price)}</p>
          <Button className="mt-6 w-full" variant="outline" onClick={() => setEditing(true)}>
            更新目標價 / Update target
          </Button>
          {status === "active" && (
            <Button
              className="mt-2 w-full"
              variant="ghost"
              onClick={cancel}
              disabled={busy !== null}
            >
              {busy === "cancel" ? "取消中…" : "取消訂閱 / Cancel subscription"}
            </Button>
          )}
        </div>
      ) : (
        <div className="mt-6">
          <Label htmlFor={inputId}>目標價（台幣）/ Target price (TWD)</Label>
          <Input
            id={inputId}
            type="number"
            inputMode="numeric"
            min={1}
            step={100}
            className="mt-2"
            value={value}
            onChange={(e) => setValue(e.target.value)}
          />
          <p className="mt-2 text-xs text-muted-foreground">
            近期最低價約 {nt(plan.hint)} · Recent cheapest ≈ {nt(plan.hint)}
          </p>
          <div className="mt-6 flex gap-2">
            <Button className="flex-1" onClick={save} disabled={busy !== null}>
              {busy === "save" ? "處理中…" : entitled ? "儲存 / Save" : payLabel}
            </Button>
            {entitled && (
              <Button variant="outline" onClick={() => setEditing(false)} disabled={busy !== null}>
                取消
              </Button>
            )}
          </div>
          {!entitled && (
            <p className="mt-2 text-xs text-muted-foreground">
              以綠界信用卡定期定額付款，每月 {nt(MONTHLY_PRICE)}，可隨時取消。
            </p>
          )}
        </div>
      )}
      {error && <p className="mt-3 text-sm text-destructive">{error}</p>}
    </div>
  );
}

export function PlanCards({ email }: { email: string }) {
  const [subs, setSubs] = useState<Partial<Record<PlanName, Subscription>>>({});
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [purchase] = useState(() => new URLSearchParams(window.location.search).get("purchase"));

  const load = useCallback(
    () =>
      listSubscriptions(email)
        .then((rows) => {
          setSubs(Object.fromEntries(rows.map((r) => [r.plan_name, r])));
          setLoadError(null);
        })
        .catch((e) => setLoadError(e instanceof Error ? e.message : String(e)))
        .finally(() => setLoaded(true)),
    [email],
  );

  useEffect(() => {
    load();
    // ECPay's server callback may land a moment after the browser returns: refresh a few times.
    if (purchase !== "success") return;
    const timers = [3000, 8000, 15000].map((ms) => window.setTimeout(load, ms));
    return () => timers.forEach(clearTimeout);
  }, [load, purchase]);

  return (
    <div className="mt-8">
      {purchase === "success" && (
        <p className="mb-4 rounded-lg border border-border bg-card p-3 text-sm">
          付款完成！訂閱狀態幾秒內會更新為「已訂閱」。 Payment received — your card will show Active
          in a few seconds.
        </p>
      )}
      {purchase === "failed" && (
        <p className="mb-4 rounded-lg border border-border bg-card p-3 text-sm text-destructive">
          付款未完成，請再試一次。 Payment didn't go through — please try again.
        </p>
      )}
      {loadError && (
        <p className="mb-4 text-sm text-destructive">
          無法載入訂閱 / Couldn't load subscriptions: {loadError}
        </p>
      )}
      <div className="grid gap-6 sm:grid-cols-2">
        {PLANS.map((plan) =>
          loaded ? (
            <PlanCard
              key={plan.plan_name}
              email={email}
              plan={plan}
              sub={subs[plan.plan_name]}
              onSaved={(s) => setSubs((prev) => ({ ...prev, [s.plan_name]: s }))}
            />
          ) : (
            <div
              key={plan.plan_name}
              className="h-64 animate-pulse rounded-xl border border-border bg-card"
            />
          ),
        )}
      </div>
      <p className="mt-6 text-sm text-muted-foreground">
        每 30 分鐘檢查一次下個月的最低票價，達到目標價時寄信給 {email}（僅限已付款的訂閱）。
        <br />
        We check next month's cheapest fare every 30 minutes and email {email} when it hits your
        target (paid subscriptions only).
      </p>
    </div>
  );
}
