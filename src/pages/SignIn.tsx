import { AuthForm } from "@/components/AuthForm";
import { usePageMeta } from "@/hooks/usePageMeta";

export default function SignIn() {
  usePageMeta("Sign in — Flight Price Notifier", [
    { name: "description", content: "Sign in to manage your flight price alerts." },
    { property: "og:title", content: "Sign in — Flight Price Notifier" },
    { property: "og:description", content: "Sign in to manage your flight price alerts." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ]);
  return <AuthForm mode="signin" />;
}
