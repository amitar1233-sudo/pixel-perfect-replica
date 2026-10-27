import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { supabase } from "@/integrations/supabase/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SiteHeader } from "@/components/SiteHeader";

export function AuthForm({ mode }: { mode: "signin" | "signup" }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isUp = mode === "signup";

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { data, error } = isUp
      ? await supabase.auth.signUp({ email, password, options: { emailRedirectTo: `${window.location.origin}/app` } })
      : await supabase.auth.signInWithPassword({ email, password });
    setBusy(false);
    if (error) return setError(error.message);
    if (data.session) navigate({ to: "/app" });
    else setError("請到信箱確認後再登入 / Check your email to confirm.");
  }

  return (
    <div className="min-h-screen bg-background bg-glow">
      <SiteHeader right={null} />
      <div className="mx-auto max-w-sm px-4 py-20 animate-fade-up">
        <h1 className="text-3xl font-bold">{isUp ? "Sign up / 註冊" : "Sign in / 登入"}</h1>
        <form onSubmit={onSubmit} className="mt-8 space-y-4 rounded-xl border border-border bg-card p-6">
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input id="password" type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button type="submit" variant="hero" className="w-full" disabled={busy}>
            {busy ? "..." : isUp ? "Create account" : "Sign in"}
          </Button>
        </form>
        <p className="mt-4 text-center text-sm text-muted-foreground">
          {isUp ? "Already have an account? " : "No account yet? "}
          <Link to={isUp ? "/signin" : "/signup"} className="text-primary hover:underline">
            {isUp ? "Sign in" : "Sign up"}
          </Link>
        </p>
      </div>
    </div>
  );
}
