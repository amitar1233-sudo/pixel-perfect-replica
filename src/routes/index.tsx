import { createFileRoute, Link } from "@tanstack/react-router";
import { Radar, BellRing, CircleX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SiteHeader } from "@/components/SiteHeader";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Flight Price Notifier — 機票降價通知" },
      { name: "description", content: "設定航線與目標價，機票降價就通知你。Set a route and a target price — we email you when the fare drops." },
      { property: "og:title", content: "Flight Price Notifier — 機票降價通知" },
      { property: "og:description", content: "Set a route and a target price — we email you when the fare drops." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

const features = [
  { icon: Radar, title: "盯緊熱門航線 (Always-on route watching)", body: "持續監控台北出發的熱門航線（東京、首爾），自動抓最低票價。" },
  { icon: BellRing, title: "達標自動通知 (Target-price email alerts)", body: "低於你設定的目標價，就寄 email 提醒你，附上立即訂購連結。" },
  { icon: CircleX, title: "隨時取消 (Cancel anytime)", body: "月訂閱制，不想用隨時停，沒有綁約。" },
];

function Index() {
  return (
    <div className="min-h-screen bg-background">
      <SiteHeader
        right={
          <Button asChild variant="hero">
            <Link to="/signin">Sign in / 登入</Link>
          </Button>
        }
      />
      <main>
        <section className="relative overflow-hidden bg-glow">
          <div className="mx-auto max-w-4xl px-4 py-28 text-center animate-fade-up">
            <h1 className="text-5xl font-bold tracking-tight md:text-7xl">
              <span className="text-gradient">Flight Price Notifier</span>
            </h1>
            <p className="mt-6 text-xl font-medium md:text-2xl">設定航線與目標價，機票降價就通知你</p>
            <p className="mt-3 text-muted-foreground">
              Set a route and a target price — we email you when the fare drops.
            </p>
            <div className="mt-10">
              <Button asChild variant="hero" size="lg">
                <Link to="/signup">免費開始 · Get started</Link>
              </Button>
            </div>
          </div>
        </section>
        <section className="mx-auto grid max-w-6xl gap-6 px-4 pb-24 md:grid-cols-3">
          {features.map((f, i) => (
            <div
              key={f.title}
              className="rounded-xl border border-border bg-card p-6 animate-fade-up transition-colors hover:border-primary/50"
              style={{ animationDelay: `${150 + i * 120}ms` }}
            >
              <f.icon className="h-8 w-8 text-primary" />
              <h3 className="mt-4 text-lg font-semibold">{f.title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{f.body}</p>
            </div>
          ))}
        </section>
      </main>
      <footer className="border-t border-border py-8 text-center text-sm text-muted-foreground">
        © 2026 Flight Price Notifier
      </footer>
    </div>
  );
}
