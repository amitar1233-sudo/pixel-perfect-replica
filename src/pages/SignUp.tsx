import { AuthForm } from "@/components/AuthForm";
import { usePageMeta } from "@/hooks/usePageMeta";

export default function SignUp() {
  usePageMeta("Sign up — Flight Price Notifier", [
    { name: "description", content: "Create an account to get fare-drop email alerts." },
    { property: "og:title", content: "Sign up — Flight Price Notifier" },
    { property: "og:description", content: "Create an account to get fare-drop email alerts." },
    { property: "og:type", content: "website" },
    { name: "twitter:card", content: "summary" },
  ]);
  return <AuthForm mode="signup" />;
}
