import { useEffect } from "react";

type Meta = { name?: string; property?: string; content: string };

/**
 * Client-side replacement for TanStack's route `head()`: sets document.title and
 * upserts the given <meta> tags when the page mounts.
 */
export function usePageMeta(title: string, meta: Meta[] = []) {
  const key = JSON.stringify(meta);
  useEffect(() => {
    document.title = title;
    for (const m of meta) {
      const attr = m.name ? "name" : "property";
      const value = (m.name ?? m.property)!;
      let el = document.head.querySelector<HTMLMetaElement>(`meta[${attr}="${value}"]`);
      if (!el) {
        el = document.createElement("meta");
        el.setAttribute(attr, value);
        document.head.appendChild(el);
      }
      el.setAttribute("content", m.content);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, key]);
}
