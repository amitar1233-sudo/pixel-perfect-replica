// Public HTTP API (API Gateway → Lambda). The browser holds no AWS credentials.
export const FLIGHT_API_URL: string =
  (import.meta.env["VITE_FLIGHT_API_URL"] as string | undefined) ??
  "https://9dkymr2plf.execute-api.us-east-1.amazonaws.com";

export type PlanName = "tokyo" | "seoul" | "london";

export type Subscription = {
  email: string;
  route: string;
  plan_name: PlanName;
  target_price: number;
  currency: "TWD";
  updated_at?: string;
  subscription_status?: SubscriptionStatus;
  current_period_end?: string;
  current_period_end_date?: string;
};

export type SubscriptionStatus = "pending_payment" | "active" | "cancelled" | "expired";

/** NT$ per month, mirrors the `amount` in the flight/ecpay secret (display only). */
export const MONTHLY_PRICE = 300;

export const PLANS: {
  plan_name: PlanName;
  label: string;
  route: string;
  hint: number;
}[] = [
  { plan_name: "tokyo", label: "台北 ✈ 東京", route: "TPE-TYO", hint: 9325 },
  { plan_name: "seoul", label: "台北 ✈ 首爾", route: "TPE-SEL", hint: 5989 },
  { plan_name: "london", label: "台北 ✈ 倫敦", route: "TPE-LON", hint: 24765 },
];

async function readJson(res: Response) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data?.error ?? `HTTP ${res.status}`);
  return data;
}

export async function listSubscriptions(email: string): Promise<Subscription[]> {
  const res = await fetch(`${FLIGHT_API_URL}/subscriptions?email=${encodeURIComponent(email)}`);
  const data = await readJson(res);
  return data.subscriptions ?? [];
}

/**
 * POST /subscribe. For a new or unpaid subscription the API answers with an
 * auto-submit HTML form; we hand the whole page to it so the browser goes to
 * ECPay's cashier (returns "redirecting"). For an already-paid subscription it
 * answers JSON and we return the updated row.
 */
export async function subscribe(
  email: string,
  plan_name: PlanName,
  target_price: number,
): Promise<Subscription | "redirecting"> {
  const res = await fetch(`${FLIGHT_API_URL}/subscribe`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, plan_name, target_price }),
  });
  if (res.ok && (res.headers.get("content-type") ?? "").includes("text/html")) {
    const html = await res.text();
    document.open();
    document.write(html);
    document.close();
    return "redirecting";
  }
  const data = await readJson(res);
  return data.subscription;
}

export async function cancelSubscription(email: string, route: string): Promise<Subscription> {
  const res = await fetch(`${FLIGHT_API_URL}/cancel`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, route }),
  });
  const data = await readJson(res);
  return data.subscription;
}
