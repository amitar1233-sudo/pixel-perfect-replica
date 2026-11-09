import { useNavigate } from "react-router";
import { useEffect } from "react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { SiteHeader } from "@/components/SiteHeader";
import { PlanCards } from "@/components/PlanCards";
import { usePageMeta } from "@/hooks/usePageMeta";

export default function AppShell() {
  usePageMeta("Dashboard — Flight Price Notifier", [
    { name: "description", content: "Your flight route tracking dashboard." },
    { property: "og:title", content: "Dashboard — Flight Price Notifier" },
    { property: "og:description", content: "Your flight route tracking dashboard." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ]);
  const { user, loading } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!loading && !user) navigate("/signin");
  }, [loading, user, navigate]);

  if (loading || !user) return <div className="min-h-screen bg-canvas" />;

  return (
    <div className="min-h-screen bg-canvas">
      <SiteHeader
        right={
          <Button
            variant="outline"
            onClick={async () => {
              await supabase.auth.signOut();
              navigate("/");
            }}
          >
            Sign out / 登出
          </Button>
        }
      />
      <main className="mx-auto max-w-3xl px-4 py-24 animate-fade-up">
        <h1 className="text-4xl font-bold">Hi {user.email}</h1>
        <p className="mt-2 text-muted-foreground">選一條航線、設定目標價，降價時我們寄信通知你。</p>
        {user.email && <PlanCards email={user.email} />}
      </main>
    </div>
  );
}
