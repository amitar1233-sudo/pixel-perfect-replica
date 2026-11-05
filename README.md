# Flight Price Notifier

A client-side React single-page app (Vite + React Router + Tailwind v4 + Supabase auth).
`vite build` produces a fully static site in `dist/`, ready for Vercel or any static host.

## Routes

| Path      | Page                                   |
| --------- | -------------------------------------- |
| `/`       | Landing page                           |
| `/signin` | Sign in                                |
| `/signup` | Sign up                                |
| `/app`    | Dashboard (redirects to `/signin` when signed out) |
| `*`       | 404                                    |

Routes are defined in `src/router.tsx`; pages live in `src/pages/`.

## Development

Requires Node.js 20+.

```sh
npm ci
npm run dev      # http://localhost:8080
npm test
npm run build    # type-checks, then outputs dist/
npm run preview  # serve dist/ locally
```

## Environment variables

Read at **build time** (Vite inlines `VITE_*` vars into the bundle):

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_PUBLISHABLE_KEY`

They point at the project's own Supabase project (`ckcnwiwdvhigsccxdbdn`) and are
set in `.env`. The client in `src/integrations/supabase/client.ts` reads them via
`import.meta.env`; nothing is hardcoded. On Vercel, add the same two variables under
Project → Settings → Environment Variables (values there override `.env`), then redeploy.

## Deploying to Vercel

Import the repo in Vercel; `vercel.json` already sets the Vite preset, `npm run build`,
the `dist` output directory, and a SPA fallback rewrite so deep links such as `/app`
load `index.html` and are routed client-side.

In your Supabase project's Auth settings, add your Vercel domain to **Site URL** /
**Redirect URLs** (e.g. `https://your-app.vercel.app/app`) so sign-up confirmation
emails redirect back correctly.

`.npmrc` sets `legacy-peer-deps=true` to work around an npm 10 resolver crash with
vitest 4's peer-dependency graph.
