import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  PLANS,
  listSubscriptions,
  subscribe,
  type PlanName,
  type Subscription,
} from "@/lib/flightApi";

const nt = (n: number) => `NT$${n.toLocaleString("en-US")}`;

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
  const [value, setValue] = useState(String(sub?.target_price ?? plan.hint + 1000));
  const [editing, setEditing] = useState(!sub);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (sub) {
      setValue(String(sub.target_price));
      setEditing(false);
    }
  }, [sub]);

  const save = async () => {
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) {
      setError("請輸入有效的台幣金額 / Enter a valid TWD amount");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      onSaved(await subscribe(email, plan.plan_name, Math.round(n)));
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const inputId = `target-${plan.plan_name}`;

  return (
    <div className="rounded-xl border border-border bg-card p-6 shadow-card backdrop-blur-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">{plan.label}</h2>
          <p className="mt-1 text-xs text-muted-foreground">{plan.route}</p>
        </div>
        {sub && (
          <span className="rounded-full bg-primary px-3 py-1 text-xs font-semibold text-primary-foreground">
            已訂閱 Subscribed
          </span>
        )}
      </div>

      {sub && !editing ? (
        <div className="mt-6">
          <p className="text-sm text-muted-foreground">目前目標價 / Current target</p>
          <p className="mt-1 text-3xl font-bold">{nt(sub.target_price)}</p>
          <Button className="mt-6 w-full" variant="outline" onClick={() => setEditing(true)}>
            更新目標價 / Update target
          </Button>
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
            <Button className="flex-1" onClick={save} disabled={saving}>
              {saving ? "儲存中…" : sub ? "儲存 / Save" : "開始追蹤 / Start tracking"}
            </Button>
            {sub && (
              <Button variant="outline" onClick={() => setEditing(false)} disabled={saving}>
                取消
              </Button>
            )}
          </div>
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

  useEffect(() => {
    let alive = true;
    listSubscriptions(email)
      .then((rows) => {
        if (!alive) return;
        setSubs(Object.fromEntries(rows.map((r) => [r.plan_name, r])));
      })
      .catch((e) => alive && setLoadError(e instanceof Error ? e.message : String(e)))
      .finally(() => alive && setLoaded(true));
    return () => {
      alive = false;
    };
  }, [email]);

  return (
    <div className="mt-8">
      {loadError && (
        <p className="mb-4 text-sm text-destructive">無法載入訂閱 / Couldn't load subscriptions: {loadError}</p>
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
            <div key={plan.plan_name} className="h-64 animate-pulse rounded-xl border border-border bg-card" />
          ),
        )}
      </div>
      <p className="mt-6 text-sm text-muted-foreground">
        每 30 分鐘檢查一次下個月的最低票價，達到目標價時寄信給 {email}。
        <br />
        We check next month's cheapest fare every 30 minutes and email {email} when it hits your target.
      </p>
    </div>
  );
}
