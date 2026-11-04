import { matchRoutes } from "react-router";
import { describe, expect, it } from "vitest";

import { routes } from "@/router";

// Match routes without rendering: verifies each URL resolves to a real page
// instead of falling through to the catch-all 404.
describe("App routing", () => {
  it.each(["/", "/app", "/signin", "/signup"])("matches a page for %s", (path) => {
    const matches = matchRoutes(routes, path);
    expect(matches?.at(-1)?.route.path).not.toBe("*");
  });

  it("falls back to not found for unknown paths", () => {
    const matches = matchRoutes(routes, "/does-not-exist");
    expect(matches?.at(-1)?.route.path).toBe("*");
  });
});
