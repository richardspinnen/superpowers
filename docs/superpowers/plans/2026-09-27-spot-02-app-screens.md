# Spot — Plan 2: App Screens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the tested database core into a working, signed-in web app. It covers email sign-in, onboarding, the time-aware "Now" screen, spot pages, members and circles with introductions, profiles with a membership card and QR invitation, and settings. It is bilingual, with light and dark themes, and follows the approved mockup.

**Architecture:** Next.js 16 App Router with server components doing all data access through `@supabase/ssr` (cookie sessions refreshed in `src/proxy.ts`). Mutations are server actions. Privacy stays in the database (RLS); the UI only reads what RLS returns. One global stylesheet holds the design tokens. All copy comes from typed EN/DE dictionaries. Pure logic (time of day, formatting, URL state, error mapping) is unit-tested with Vitest; every user flow is covered by Playwright against the local Supabase stack with a demo data set.

**Tech Stack:** Next.js 16.3.6, React 19.2, TypeScript, `@supabase/ssr` 0.12.7, `@supabase/supabase-js` 2.117.2, `qrcode`, Vitest, Playwright, Supabase CLI (local stack incl. Mailpit).

**Spec:** `docs/superpowers/specs/2026-09-27-spot-recommendations-app-design.md` (§5 screens, §10 product decisions: wording, navigation, time-aware home, moods, notes for later plans).

**Roadmap change (recorded here):** the spec's original Plan 3 content is split so something usable ships sooner. This plan contains the *read side*: the Discover UI and the spot page, fed by demo data locally. **Plan 3:** spotting places (Google Places module, the Spot tab, add/edit a spot, "Known for", report button + email, place refresh job). **Plan 4:** membership levels and Apple/Google Wallet passes.

## Global Constraints

- Next.js **16.3.6**: middleware is **`src/proxy.ts`** exporting `proxy`. `cookies()`, `headers()`, page `params` and `searchParams` are **async**. The repo's `AGENTS.md` applies: before using any Next.js API not shown in this plan, read its guide in `node_modules/next/dist/docs/`.
- No Tailwind. All styling lives in `src/app/globals.css` using the design tokens defined there. Only black, white and greys are allowed, plus `--danger` for errors. The font is Geist. Content is max 480 px wide with 24 px side gutters, and there is a floating tab bar.
- **No hard-coded UI copy.** Every user-visible string comes from `src/i18n/en.ts` / `src/i18n/de.ts`. Wording follows spec §10: My circle, All members, Add to circle, In your circle, Request introduction, Introduction requested, Spotted by, Your invitation, and the tab name Now.
- Locale resolution uses the first that applies:
  1. the signed-in member's `profiles.locale`
  2. the `locale` cookie
  3. `en` if `Accept-Language` starts with `en`
  4. otherwise `de`
- Supabase is accessed only through `src/lib/supabase/{server,proxy,admin}.ts`. The admin (secret-key) client is imported only by server actions and scripts, never by client components. `SUPABASE_SECRET_KEY` must never be `NEXT_PUBLIC_`.
- Plan 2 never renders `profiles.avatar_url` (initials only), per the Plan 1 final review.
- The database decides privacy. The UI never tries to reconstruct or bypass RLS.
- Database error messages map to dictionary keys via `src/lib/errors.ts`: `username_reserved`, `rate_limited`, `invalid_tags`, `invalid_scope`, `invalid_radius`, `invalid_page`, unique violation 23505 → `username_taken`, check violation 23514 → `username_format` or `display_name`.
- Time of day uses the **Europe/Berlin** time zone (launch city). Slots per spec §10:
  - coffee: 05:00–11:00 and 15:00–17:00
  - lunch: 11:00–15:00
  - dinner: 17:00–21:00
  - bar: 21:00–01:00
  - night: 01:00–05:00
- If the browser gives no location, the app uses Oberkassel, Düsseldorf (lat 51.2317, lng 6.7545).
- Discover radii cycle through 2000 → 5000 → 10000 → 20000 m ("the whole city"), and the default is 2000.
- Demo data is local only. `scripts/seed-demo.ts` refuses any non-localhost Supabase URL.

---

## File Structure

```
.env.example                         # documented env vars (committed)
scripts/env-local.sh                 # writes .env.local from `supabase status`
scripts/seed-demo.ts                 # local demo members, places, spots (Düsseldorf)
supabase/config.toml                 # redirect URLs, email rate limit
supabase/migrations/20260927000009_moods.sql
next.config.ts                       # /@:username rewrite
vitest.config.ts
playwright.config.ts
src/proxy.ts                         # session refresh + sign-in gate
src/lib/env.ts                       # typed env access
src/lib/supabase/server.ts           # per-request server client
src/lib/supabase/proxy.ts            # updateSession for proxy.ts
src/lib/supabase/admin.ts            # secret-key client (server only)
src/lib/supabase/database.types.ts   # generated
src/lib/viewer.ts                    # getViewer / requireMember (per-request cache)
src/lib/errors.ts                    # DB error → dictionary key
src/lib/format.ts                    # distance, member-since, initials
src/lib/time-of-day.ts               # slots, Berlin clock, tag ordering
src/lib/now-url.ts                   # Now-screen URL state
src/lib/safe-next.ts                 # open-redirect-safe "next" paths
src/lib/actions/follow.ts            # follow / unfollow / accept / decline
src/lib/actions/settings.ts          # language, privacy, sign out, delete account
src/i18n/{en,de,index}.ts            # dictionaries + locale resolution
src/components/{Avatar,Icons,Shell,PublicShell,TabBar,LocateMe,FollowButton,CopyButton,MembershipCard}.tsx
src/app/globals.css
src/app/layout.tsx
src/app/login/{page.tsx,LoginForm.tsx,actions.ts}
src/app/auth/callback/route.ts
src/app/onboarding/{page.tsx,OnboardingForm.tsx,actions.ts}
src/app/(app)/layout.tsx             # members-only shell
src/app/(app)/page.tsx               # Now
src/app/(app)/spots/[id]/page.tsx
src/app/(app)/members/page.tsx
src/app/(app)/settings/page.tsx
src/app/m/[username]/{layout.tsx,page.tsx}   # profiles (public preview)
src/app/i/[id]/route.ts              # QR target → current username
tests/e2e/{global-setup.ts,helpers.ts,*.spec.ts}
.github/workflows/db-tests.yml       # + app and e2e jobs
```

**Test conventions:**
- Unit tests sit next to the code as `src/**/*.test.ts` and run with `npm test` (Vitest).
- E2E specs live in `tests/e2e/*.spec.ts` and run with `npm run test:e2e` (Playwright).
- E2E needs the local stack running (`npx supabase start`, with Mailpit *not* excluded) and `.env.local` (`bash scripts/env-local.sh`).
- The e2e global setup loads the demo data. E2E runs in English (`locale: 'en-US'`), except where a test switches language.

---

### Task 1: Foundations: dependencies, env, Supabase clients, proxy, test runners

**Files:**
- Modify: `package.json`, `.gitignore`, `supabase/config.toml`, `src/app/layout.tsx` (fonts only), `src/app/page.tsx` (delete), `postcss.config.mjs` (delete)
- Create: `.env.example`, `scripts/env-local.sh`, `vitest.config.ts`, `src/lib/env.ts`, `src/lib/env.test.ts`, `src/lib/supabase/server.ts`, `src/lib/supabase/proxy.ts`, `src/lib/supabase/database.types.ts` (generated), `src/proxy.ts`

**Interfaces:**
- Produces:
  - `env.siteUrl(): string`
  - `env.supabaseUrl(): string`
  - `env.supabaseKey(): string`
  - `env.googleEnabled(): boolean`
  - `env.appleEnabled(): boolean`
  - `serverEnv.secretKey(): string`
  - `createClient(): Promise<SupabaseClient<Database>>` (server)
  - `updateSession(request: NextRequest): Promise<NextResponse>`
  - `type Database` from `@/lib/supabase/database.types`
  - npm scripts: `typecheck`, `test`, `test:e2e`, `seed:demo`, `types:db`
  - The public (signed-out) path prefixes are `/login`, `/auth`, `/m`, `/i`, `/@`. Every other path redirects signed-out visitors to `/login?next=<path>`.

- [ ] **Step 1: Install dependencies and remove Tailwind**

```bash
cd /home/user/spot
npm uninstall tailwindcss @tailwindcss/postcss
rm -f postcss.config.mjs src/app/page.tsx
npm install @supabase/ssr@0.12.7 @supabase/supabase-js@2.117.2 qrcode@1.5.4 server-only
npm install --save-dev vitest@^5 @types/qrcode @playwright/test
```

In `package.json` `"scripts"`, add:

```json
"typecheck": "tsc --noEmit",
"test": "vitest run",
"test:e2e": "playwright test",
"seed:demo": "node --env-file=.env.local --experimental-strip-types scripts/seed-demo.ts",
"types:db": "supabase gen types typescript --local > src/lib/supabase/database.types.ts"
```

- [ ] **Step 2: Environment files**

Create `.env.example`:

```bash
# Copy to .env.local (or run: bash scripts/env-local.sh against the local stack)
NEXT_PUBLIC_SITE_URL=http://127.0.0.1:3000
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=
# Server only. Never prefix with NEXT_PUBLIC_.
SUPABASE_SECRET_KEY=
# Show the provider buttons only once the provider is configured in Supabase Auth.
NEXT_PUBLIC_AUTH_GOOGLE=false
NEXT_PUBLIC_AUTH_APPLE=false
# Local e2e only: Mailpit API of the local Supabase stack
MAILPIT_URL=http://127.0.0.1:54324
```

In `.gitignore`, directly below the existing `.env*` line, add `!.env.example`.

Create `scripts/env-local.sh`:

```bash
#!/usr/bin/env bash
# Writes .env.local for the running local Supabase stack.
set -euo pipefail
eval "$(npx supabase status -o env)"
cat > .env.local <<EOF
NEXT_PUBLIC_SITE_URL=http://127.0.0.1:3000
NEXT_PUBLIC_SUPABASE_URL=${API_URL}
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=${PUBLISHABLE_KEY}
SUPABASE_SECRET_KEY=${SECRET_KEY}
NEXT_PUBLIC_AUTH_GOOGLE=false
NEXT_PUBLIC_AUTH_APPLE=false
MAILPIT_URL=http://127.0.0.1:54324
EOF
echo "Wrote .env.local"
```

Run `npx supabase status -o env` once and confirm the variable names `API_URL`, `PUBLISHABLE_KEY` and `SECRET_KEY`. If the CLI prints different names, adapt the script and note it in the report.

- [ ] **Step 3: Local auth settings**

In `supabase/config.toml`:
- In `[auth]`, set `additional_redirect_urls = ["http://127.0.0.1:3000/**", "http://localhost:3000/**"]`.
- In `[auth.rate_limit]`, set `email_sent = 100`. E2E sends many sign-in emails.

Restart the stack with Mailpit included:

```bash
npx supabase stop && npx supabase start -x studio,edge-runtime,logflare,vector,imgproxy
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:54324/api/v1/messages   # expect 200
bash scripts/env-local.sh
```

- [ ] **Step 4: Write the failing unit test**

Create `vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: { alias: { '@': new URL('./src', import.meta.url).pathname } },
  test: { include: ['src/**/*.test.ts'], environment: 'node' },
});
```

Create `src/lib/env.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { env, serverEnv } from './env';

afterEach(() => vi.unstubAllEnvs());

describe('env', () => {
  it('reads the Supabase URL', () => {
    vi.stubEnv('NEXT_PUBLIC_SUPABASE_URL', 'http://127.0.0.1:54321');
    expect(env.supabaseUrl()).toBe('http://127.0.0.1:54321');
  });

  it('names the missing variable', () => {
    vi.stubEnv('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', '');
    expect(() => env.supabaseKey()).toThrow('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY');
  });

  it('defaults the site URL to the local dev server', () => {
    vi.stubEnv('NEXT_PUBLIC_SITE_URL', '');
    expect(env.siteUrl()).toBe('http://127.0.0.1:3000');
  });

  it('treats provider flags as off unless exactly "true"', () => {
    vi.stubEnv('NEXT_PUBLIC_AUTH_GOOGLE', 'yes');
    vi.stubEnv('NEXT_PUBLIC_AUTH_APPLE', 'true');
    expect(env.googleEnabled()).toBe(false);
    expect(env.appleEnabled()).toBe(true);
  });

  it('requires the secret key on the server', () => {
    vi.stubEnv('SUPABASE_SECRET_KEY', '');
    expect(() => serverEnv.secretKey()).toThrow('SUPABASE_SECRET_KEY');
  });
});
```

- [ ] **Step 5: Run it to verify it fails**

Run: `npm test`
Expected: FAIL. `Cannot find module './env'`.

- [ ] **Step 6: Implement env, Supabase clients and proxy**

Create `src/lib/env.ts`:

```ts
function required(name: string, value: string | undefined): string {
  if (!value) throw new Error(`Missing environment variable: ${name}`);
  return value;
}

// NEXT_PUBLIC_ values are read with literal property access so Next.js can inline them.
export const env = {
  siteUrl: () => process.env.NEXT_PUBLIC_SITE_URL || 'http://127.0.0.1:3000',
  supabaseUrl: () => required('NEXT_PUBLIC_SUPABASE_URL', process.env.NEXT_PUBLIC_SUPABASE_URL),
  supabaseKey: () =>
    required('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY', process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY),
  googleEnabled: () => process.env.NEXT_PUBLIC_AUTH_GOOGLE === 'true',
  appleEnabled: () => process.env.NEXT_PUBLIC_AUTH_APPLE === 'true',
};

export const serverEnv = {
  secretKey: () => required('SUPABASE_SECRET_KEY', process.env.SUPABASE_SECRET_KEY),
};
```

Generate the database types (the local stack must be running):

```bash
npm run types:db
```

Create `src/lib/supabase/server.ts`:

```ts
import 'server-only';
import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';
import { env } from '@/lib/env';
import type { Database } from './database.types';

// One client per request. Never share a client across requests.
export async function createClient() {
  const cookieStore = await cookies();
  return createServerClient<Database>(env.supabaseUrl(), env.supabaseKey(), {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          cookiesToSet.forEach(({ name, value, options }) => cookieStore.set(name, value, options));
        } catch {
          // Called during Server Component rendering: src/proxy.ts refreshes the session instead.
        }
      },
    },
  });
}
```

Create `src/lib/supabase/proxy.ts`:

```ts
import { createServerClient } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';
import { env } from '@/lib/env';
import type { Database } from './database.types';

const PUBLIC_PREFIXES = ['/login', '/auth', '/m', '/i'];

export function isPublicPath(pathname: string): boolean {
  return (
    pathname.startsWith('/@') ||
    PUBLIC_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))
  );
}

// Refreshes the auth session cookie on every request and sends signed-out
// visitors to /login. Authorization itself is enforced by the database (RLS).
export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request });

  const supabase = createServerClient<Database>(env.supabaseUrl(), env.supabaseKey(), {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet, headers) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        Object.entries(headers ?? {}).forEach(([key, value]) => response.headers.set(key, value));
      },
    },
  });

  const { data } = await supabase.auth.getClaims();
  const { pathname, search } = request.nextUrl;

  if (!data?.claims && !isPublicPath(pathname)) {
    const url = request.nextUrl.clone();
    url.pathname = '/login';
    url.search = `?next=${encodeURIComponent(pathname + search)}`;
    const redirect = NextResponse.redirect(url);
    response.cookies.getAll().forEach((cookie) => redirect.cookies.set(cookie));
    return redirect;
  }

  return response;
}
```

Create `src/proxy.ts`:

```ts
import type { NextRequest } from 'next/server';
import { updateSession } from '@/lib/supabase/proxy';

export async function proxy(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)'],
};
```

Replace `src/app/layout.tsx` with a temporary minimal layout (Task 2 replaces it):

```tsx
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
```

Create `src/lib/supabase/proxy.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { isPublicPath } from './proxy';

describe('isPublicPath', () => {
  it.each(['/login', '/auth/callback', '/m/anna', '/i/123', '/@anna'])('%s is public', (path) => {
    expect(isPublicPath(path)).toBe(true);
  });

  it.each(['/', '/members', '/settings', '/spots/1', '/mx', '/imprint'])('%s needs sign-in', (path) => {
    expect(isPublicPath(path)).toBe(false);
  });
});
```

- [ ] **Step 7: Verify**

```bash
npm test          # expect: all tests pass
npm run typecheck # expect: no errors
npm run build     # expect: build succeeds
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(app): Supabase SSR clients, session proxy, env and test runners"
```

---

### Task 2: Design tokens, dictionaries and pure helpers

**Files:**
- Create: `src/app/globals.css` (replace), `src/app/layout.tsx` (replace), `src/i18n/en.ts`, `src/i18n/de.ts`, `src/i18n/index.ts`, `src/i18n/i18n.test.ts`, `src/lib/viewer.ts`, `src/lib/errors.ts`, `src/lib/errors.test.ts`, `src/lib/format.ts`, `src/lib/format.test.ts`, `src/lib/time-of-day.ts`, `src/lib/time-of-day.test.ts`, `src/lib/now-url.ts`, `src/lib/now-url.test.ts`

**Interfaces:**
- Consumes: `createClient()` (Task 1).
- Produces:
  - `type Locale = 'de' | 'en'`
  - `isLocale(v): v is Locale`
  - `messages: Record<Locale, Messages>`
  - `resolveLocale(input: { profileLocale?: string | null; cookie?: string; acceptLanguage?: string | null }): Locale`
  - `getViewer(): Promise<{ supabase; user; profile; locale; t }>` (per-request `cache`)
  - `requireMember()`: same fields with non-null `user` and `profile`; redirects to `/login` or `/onboarding` otherwise
  - `errorKey(err): keyof Messages['errors']`
  - `formatDistance(m, locale)`
  - `formatMemberSince(iso, locale)`
  - `initials(name)`
  - `type Slot`
  - `SLOTS`
  - `slotAt(h, m)`
  - `berlinClock(date)`
  - `orderTags(tags, first)`
  - `RADII`
  - `type Scope`
  - `type NowState`
  - `nextRadius(r)`
  - `nowHref(state, patch?)`
  - `parseNowParams(sp, defaultTag, validTags)`
  - CSS class names listed in `globals.css`. Later tasks use only these.

- [ ] **Step 1: Write the failing tests**

Create `src/i18n/i18n.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { messages, resolveLocale } from './index';

function shape(value: unknown): unknown {
  if (typeof value === 'function') return 'fn';
  if (Array.isArray(value)) return value.map(shape);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => [k, shape(v)]));
  }
  return typeof value;
}

describe('dictionaries', () => {
  it('German and English have exactly the same keys and value kinds', () => {
    expect(shape(messages.de)).toEqual(shape(messages.en));
  });

  it('uses the agreed wording', () => {
    expect(messages.en.nav.now).toBe('Now');
    expect(messages.de.nav.now).toBe('Jetzt');
    expect(messages.en.members.requestIntroduction).toBe('Request introduction');
    expect(messages.de.members.requestIntroduction).toBe('Vorstellung anfragen');
    expect(messages.en.now.following).toBe('My circle');
  });
});

describe('resolveLocale', () => {
  it('prefers the member profile', () => {
    expect(resolveLocale({ profileLocale: 'en', cookie: 'de', acceptLanguage: 'de-DE' })).toBe('en');
  });
  it('then the cookie', () => {
    expect(resolveLocale({ cookie: 'en', acceptLanguage: 'de-DE' })).toBe('en');
  });
  it('then an English Accept-Language', () => {
    expect(resolveLocale({ acceptLanguage: 'en-US,en;q=0.9' })).toBe('en');
  });
  it('defaults to German', () => {
    expect(resolveLocale({ acceptLanguage: 'fr-FR' })).toBe('de');
    expect(resolveLocale({})).toBe('de');
  });
});
```

Create `src/lib/errors.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { errorKey } from './errors';

describe('errorKey', () => {
  it('maps raised machine codes', () => {
    expect(errorKey({ code: 'P0001', message: 'username_reserved' })).toBe('username_reserved');
    expect(errorKey({ code: 'P0001', message: 'rate_limited' })).toBe('rate_limited');
    expect(errorKey({ code: 'P0001', message: 'invalid_radius' })).toBe('invalid_radius');
  });
  it('maps constraint violations', () => {
    expect(errorKey({ code: '23505', message: 'duplicate key value violates unique constraint "profiles_username_key"' })).toBe('username_taken');
    expect(errorKey({ code: '23514', message: 'violates check constraint "profiles_username_check"' })).toBe('username_format');
    expect(errorKey({ code: '23514', message: 'violates check constraint "profiles_display_name_check"' })).toBe('display_name');
  });
  it('falls back to generic', () => {
    expect(errorKey({ code: '42501', message: 'permission denied' })).toBe('generic');
    expect(errorKey(null)).toBe('generic');
  });
});
```

Create `src/lib/format.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { formatDistance, formatMemberSince, initials } from './format';

describe('formatDistance', () => {
  it('shows metres below 1 km', () => {
    expect(formatDistance(453.2, 'en')).toBe('453 m');
  });
  it('shows km with at most one decimal, localized', () => {
    expect(formatDistance(1204, 'en')).toBe('1.2 km');
    expect(formatDistance(1204, 'de')).toBe('1,2 km');
    expect(formatDistance(2000, 'en')).toBe('2 km');
  });
});

describe('formatMemberSince', () => {
  it('shows month/year in Berlin time', () => {
    expect(formatMemberSince('2026-09-30T23:30:00Z', 'en')).toBe('10/2026');
    expect(formatMemberSince('2026-09-30T23:30:00Z', 'de')).toBe('10/2026');
  });
});

describe('initials', () => {
  it('takes up to two initials', () => {
    expect(initials('Sofia Brandt')).toBe('SB');
    expect(initials('anna')).toBe('A');
    expect(initials('  ')).toBe('?');
  });
});
```

Create `src/lib/time-of-day.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { berlinClock, orderTags, SLOTS, slotAt } from './time-of-day';

describe('slotAt', () => {
  it.each([
    [5, 0, 'coffee'], [10, 59, 'coffee'], [11, 0, 'lunch'], [14, 59, 'lunch'],
    [15, 0, 'coffee'], [16, 59, 'coffee'], [17, 0, 'dinner'], [20, 59, 'dinner'],
    [21, 0, 'bar'], [23, 59, 'bar'], [0, 59, 'bar'], [1, 0, 'night'], [4, 59, 'night'],
  ] as const)('%i:%i is %s', (h, m, slot) => {
    expect(slotAt(h, m)).toBe(slot);
  });

  it('pre-selects the agreed moods', () => {
    expect(SLOTS.coffee.tag).toBe('coffee');
    expect(SLOTS.lunch.tag).toBe('quick-bite');
    expect(SLOTS.dinner.tag).toBe('date-night');
    expect(SLOTS.bar.tag).toBe('cocktails');
    expect(SLOTS.night.tag).toBe('club-night');
  });
});

describe('berlinClock', () => {
  it('reads the time in Berlin', () => {
    expect(berlinClock(new Date('2026-09-27T17:30:00Z'))).toEqual({ hours: 19, minutes: 30, label: '19:30' });
    expect(berlinClock(new Date('2026-01-15T23:05:00Z'))).toEqual({ hours: 0, minutes: 5, label: '00:05' });
  });
});

describe('orderTags', () => {
  it('puts the slot moods first, keeping the rest in order', () => {
    const tags = ['date-night', 'brunch', 'coffee', 'wine'].map((slug) => ({ slug }));
    expect(orderTags(tags, ['coffee', 'brunch', 'missing']).map((t) => t.slug)).toEqual(['coffee', 'brunch', 'date-night', 'wine']);
  });
});
```

Create `src/lib/now-url.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { nextRadius, nowHref, parseNowParams, type NowState } from './now-url';

const base: NowState = { tag: 'date-night', scope: 'following', radius: 2000, lat: null, lng: null };

describe('nowHref', () => {
  it('omits defaults', () => {
    expect(nowHref(base)).toBe('/?tag=date-night');
  });
  it('applies a patch and keeps location', () => {
    expect(nowHref({ ...base, lat: 51.23171, lng: 6.75449 }, { scope: 'everyone', radius: 5000 }))
      .toBe('/?tag=date-night&scope=everyone&radius=5000&lat=51.2317&lng=6.7545');
  });
});

describe('nextRadius', () => {
  it('cycles 2 → 5 → 10 → 20 → 2 km', () => {
    expect([2000, 5000, 10000, 20000].map(nextRadius)).toEqual([5000, 10000, 20000, 2000]);
    expect(nextRadius(1234)).toBe(2000);
  });
});

describe('parseNowParams', () => {
  const valid = ['date-night', 'coffee'];
  it('uses defaults for missing or invalid values', () => {
    expect(parseNowParams({ tag: 'nope', scope: 'x', radius: '7', lat: '200' }, 'coffee', valid))
      .toEqual({ tag: 'coffee', scope: 'following', radius: 2000, lat: null, lng: null });
  });
  it('reads valid values', () => {
    expect(parseNowParams({ tag: 'date-night', scope: 'everyone', radius: '10000', lat: '51.2', lng: '6.7' }, 'coffee', valid))
      .toEqual({ tag: 'date-night', scope: 'everyone', radius: 10000, lat: 51.2, lng: 6.7 });
  });
  it('needs both coordinates', () => {
    expect(parseNowParams({ lat: '51.2' }, 'coffee', valid).lat).toBeNull();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL. The modules cannot be found.

- [ ] **Step 3: Implement the dictionaries**

Create `src/i18n/en.ts`:

```ts
export const en = {
  nav: { now: 'Now', members: 'Members', profile: 'Profile' },
  login: {
    title: 'Members only.',
    subtitle: 'Sign in or join with your email address.',
    email: 'Email',
    emailPlaceholder: 'you@example.com',
    send: 'Send sign-in link',
    sent: (email: string) => `Check your inbox. We sent a sign-in link to ${email}.`,
    or: 'or',
    google: 'Continue with Google',
    apple: 'Continue with Apple',
    deleted: 'Your account has been deleted.',
  },
  onboarding: {
    title: 'Welcome to spot.',
    subtitle: 'Choose how members will find you.',
    username: 'Username',
    usernameHint: '3–30 characters: a–z, 0–9 and _',
    displayName: 'Name',
    submit: 'Continue',
  },
  now: {
    slots: {
      coffee: ['Time for', 'coffee?'],
      lunch: ['Where for', 'lunch?'],
      dinner: ['Where for', 'dinner?'],
      bar: ['One more', 'drink?'],
      night: ['Still', 'dancing?'],
    },
    moods: 'Moods',
    nearYou: 'Near you',
    fallbackArea: 'Oberkassel, Düsseldorf',
    locationOff: 'Location is off, so spot shows places near Oberkassel.',
    following: 'My circle',
    everyone: 'All members',
    within: (distance: string) => `within ${distance}`,
    wholeCity: 'the whole city',
    and: (n: number) => (n === 1 ? ' + 1 member' : ` + ${n} members`),
    empty: (mood: string) => `No one in your circle has spotted a ${mood.toLowerCase()} place nearby yet.`,
    emptyEveryone: (mood: string) => `No member has spotted a ${mood.toLowerCase()} place nearby yet.`,
    widen: 'Widen the radius',
    askAll: 'Ask all members',
  },
  spot: {
    back: 'Back',
    address: 'Address',
    spottedBy: 'Spotted by',
    openMaps: 'Open in Google Maps',
  },
  members: {
    title: 'Members',
    invitation: 'Your invitation',
    invitationHint: 'Share it with people whose taste you trust.',
    copy: 'Copy',
    copied: 'Copied',
    search: 'Search members',
    none: 'No members found.',
    addToCircle: 'Add to circle',
    inCircle: 'In your circle',
    requestIntroduction: 'Request introduction',
    introductionRequested: 'Introduction requested',
    private: 'Private',
  },
  profile: {
    followers: 'followers',
    inCircle: 'in circle',
    spots: 'Spots',
    yourSpots: 'Your spots',
    noSpots: 'No spots yet.',
    lockedTitle: 'Private member',
    lockedBody: 'Their spots are shared by introduction only.',
    settings: 'Settings',
    join: (name: string) => `Join spot to add ${name} to your circle.`,
    signIn: 'Sign in',
  },
  card: {
    membership: 'Membership',
    memberSince: 'Member since',
    share: 'Share card',
    shared: 'Invitation copied',
    qr: 'QR code that opens this profile',
  },
  settings: {
    title: 'Settings',
    language: 'Language',
    privateLabel: 'Private membership',
    privateHint: 'Only members you accept see your spots.',
    on: 'On',
    off: 'Off',
    requests: 'Introduction requests',
    noRequests: 'No open requests.',
    accept: 'Accept',
    decline: 'Decline',
    signOut: 'Sign out',
    deleteAccount: 'Delete account',
    deleteWarning: 'This permanently deletes your profile, your circle and your spots.',
    deleteConfirm: 'Delete permanently',
    cancel: 'Cancel',
  },
  errors: {
    generic: 'Something went wrong. Please try again.',
    email: 'Enter a valid email address.',
    link: 'This sign-in link is invalid or has expired. Request a new one.',
    username_reserved: 'This username is reserved.',
    username_taken: 'This username is taken.',
    username_format: 'Use 3–30 characters: a–z, 0–9 and _.',
    display_name: 'Enter a name of up to 50 characters.',
    rate_limited: 'You’ve reached today’s limit. Try again tomorrow.',
    invalid_tags: 'Choose 1 to 3 moods.',
    invalid_scope: 'Something went wrong. Please try again.',
    invalid_radius: 'Something went wrong. Please try again.',
    invalid_page: 'Something went wrong. Please try again.',
  },
};

export type Messages = typeof en;
```

Create `src/i18n/de.ts`:

```ts
import type { Messages } from './en';

export const de: Messages = {
  nav: { now: 'Jetzt', members: 'Mitglieder', profile: 'Profil' },
  login: {
    title: 'Nur für Mitglieder.',
    subtitle: 'Melde dich mit deiner E-Mail-Adresse an oder tritt bei.',
    email: 'E-Mail',
    emailPlaceholder: 'du@beispiel.de',
    send: 'Anmeldelink senden',
    sent: (email: string) => `Schau in dein Postfach. Wir haben einen Anmeldelink an ${email} geschickt.`,
    or: 'oder',
    google: 'Weiter mit Google',
    apple: 'Weiter mit Apple',
    deleted: 'Dein Konto wurde gelöscht.',
  },
  onboarding: {
    title: 'Willkommen bei spot.',
    subtitle: 'Wähle, wie Mitglieder dich finden.',
    username: 'Nutzername',
    usernameHint: '3–30 Zeichen: a–z, 0–9 und _',
    displayName: 'Name',
    submit: 'Weiter',
  },
  now: {
    slots: {
      coffee: ['Zeit für', 'Kaffee?'],
      lunch: ['Wohin zum', 'Mittagessen?'],
      dinner: ['Wohin zum', 'Abendessen?'],
      bar: ['Noch einen', 'Drink?'],
      night: ['Noch', 'tanzen?'],
    },
    moods: 'Stimmungen',
    nearYou: 'In deiner Nähe',
    fallbackArea: 'Oberkassel, Düsseldorf',
    locationOff: 'Standort ist aus, daher zeigt spot Orte in Oberkassel.',
    following: 'Mein Kreis',
    everyone: 'Alle Mitglieder',
    within: (distance: string) => `im Umkreis von ${distance}`,
    wholeCity: 'der ganzen Stadt',
    and: (n: number) => (n === 1 ? ' + 1 Mitglied' : ` + ${n} Mitglieder`),
    empty: (mood: string) => `Noch niemand aus deinem Kreis hat hier in der Nähe einen Spot für ${mood} markiert.`,
    emptyEveryone: (mood: string) => `Noch kein Mitglied hat hier in der Nähe einen Spot für ${mood} markiert.`,
    widen: 'Umkreis erweitern',
    askAll: 'Alle Mitglieder fragen',
  },
  spot: {
    back: 'Zurück',
    address: 'Adresse',
    spottedBy: 'Entdeckt von',
    openMaps: 'In Google Maps öffnen',
  },
  members: {
    title: 'Mitglieder',
    invitation: 'Deine Einladung',
    invitationHint: 'Teile sie mit Menschen, deren Geschmack du vertraust.',
    copy: 'Kopieren',
    copied: 'Kopiert',
    search: 'Mitglieder suchen',
    none: 'Keine Mitglieder gefunden.',
    addToCircle: 'In den Kreis',
    inCircle: 'In deinem Kreis',
    requestIntroduction: 'Vorstellung anfragen',
    introductionRequested: 'Vorstellung angefragt',
    private: 'Privat',
  },
  profile: {
    followers: 'Follower',
    inCircle: 'im Kreis',
    spots: 'Spots',
    yourSpots: 'Deine Spots',
    noSpots: 'Noch keine Spots.',
    lockedTitle: 'Privates Mitglied',
    lockedBody: 'Spots nur nach Vorstellung.',
    settings: 'Einstellungen',
    join: (name: string) => `Tritt spot bei, um ${name} in deinen Kreis aufzunehmen.`,
    signIn: 'Anmelden',
  },
  card: {
    membership: 'Mitgliedschaft',
    memberSince: 'Mitglied seit',
    share: 'Karte teilen',
    shared: 'Einladung kopiert',
    qr: 'QR-Code, der dieses Profil öffnet',
  },
  settings: {
    title: 'Einstellungen',
    language: 'Sprache',
    privateLabel: 'Private Mitgliedschaft',
    privateHint: 'Nur Mitglieder, die du annimmst, sehen deine Spots.',
    on: 'An',
    off: 'Aus',
    requests: 'Vorstellungsanfragen',
    noRequests: 'Keine offenen Anfragen.',
    accept: 'Annehmen',
    decline: 'Ablehnen',
    signOut: 'Abmelden',
    deleteAccount: 'Konto löschen',
    deleteWarning: 'Das löscht dein Profil, deinen Kreis und deine Spots endgültig.',
    deleteConfirm: 'Endgültig löschen',
    cancel: 'Abbrechen',
  },
  errors: {
    generic: 'Etwas ist schiefgelaufen. Bitte versuche es noch einmal.',
    email: 'Gib eine gültige E-Mail-Adresse ein.',
    link: 'Dieser Anmeldelink ist ungültig oder abgelaufen. Fordere einen neuen an.',
    username_reserved: 'Dieser Nutzername ist reserviert.',
    username_taken: 'Dieser Nutzername ist vergeben.',
    username_format: 'Nutze 3–30 Zeichen: a–z, 0–9 und _.',
    display_name: 'Gib einen Namen mit bis zu 50 Zeichen ein.',
    rate_limited: 'Du hast das heutige Limit erreicht. Versuch es morgen wieder.',
    invalid_tags: 'Wähle 1 bis 3 Stimmungen.',
    invalid_scope: 'Etwas ist schiefgelaufen. Bitte versuche es noch einmal.',
    invalid_radius: 'Etwas ist schiefgelaufen. Bitte versuche es noch einmal.',
    invalid_page: 'Etwas ist schiefgelaufen. Bitte versuche es noch einmal.',
  },
};
```

Create `src/i18n/index.ts`:

```ts
import { de } from './de';
import { en, type Messages } from './en';

export type Locale = 'de' | 'en';
export type { Messages };

export const messages: Record<Locale, Messages> = { de, en };

export function isLocale(value: unknown): value is Locale {
  return value === 'de' || value === 'en';
}

export function resolveLocale(input: {
  profileLocale?: string | null;
  cookie?: string;
  acceptLanguage?: string | null;
}): Locale {
  if (isLocale(input.profileLocale)) return input.profileLocale;
  if (isLocale(input.cookie)) return input.cookie;
  return /^\s*en\b/i.test(input.acceptLanguage ?? '') ? 'en' : 'de';
}
```

- [ ] **Step 4: Implement the helpers**

Create `src/lib/errors.ts`:

```ts
import type { Messages } from '@/i18n';

export type ErrorKey = keyof Messages['errors'];

const RAISED: ErrorKey[] = ['username_reserved', 'rate_limited', 'invalid_tags', 'invalid_scope', 'invalid_radius', 'invalid_page'];

export function errorKey(error: { code?: string; message?: string } | null | undefined): ErrorKey {
  if (!error) return 'generic';
  const message = error.message ?? '';
  const raised = RAISED.find((key) => message.includes(key));
  if (raised) return raised;
  if (error.code === '23505') return 'username_taken';
  if (error.code === '23514') return message.includes('display_name') ? 'display_name' : 'username_format';
  return 'generic';
}
```

Create `src/lib/format.ts`:

```ts
import type { Locale } from '@/i18n';

const tag = (locale: Locale) => (locale === 'de' ? 'de-DE' : 'en-GB');

export function formatDistance(metres: number, locale: Locale): string {
  if (metres < 1000) return `${Math.round(metres)} m`;
  const km = new Intl.NumberFormat(tag(locale), { maximumFractionDigits: 1 }).format(metres / 1000);
  return `${km} km`;
}

// Always MM/YYYY (card design), in Berlin time. `locale` is kept for future formats.
export function formatMemberSince(iso: string, _locale: Locale): string {
  const parts = new Intl.DateTimeFormat('en-GB', { month: '2-digit', year: 'numeric', timeZone: 'Europe/Berlin' }).formatToParts(new Date(iso));
  const month = parts.find((p) => p.type === 'month')?.value ?? '';
  const year = parts.find((p) => p.type === 'year')?.value ?? '';
  return `${month}/${year}`;
}

export function initials(name: string): string {
  const letters = name.trim().split(/\s+/).filter(Boolean).map((word) => word[0]).join('').slice(0, 2);
  return letters ? letters.toUpperCase() : '?';
}
```

Create `src/lib/time-of-day.ts`:

```ts
export type Slot = 'coffee' | 'lunch' | 'dinner' | 'bar' | 'night';

// The pre-selected mood and the moods shown first for each part of the day (spec §10).
export const SLOTS: Record<Slot, { tag: string; first: string[] }> = {
  coffee: { tag: 'coffee', first: ['coffee', 'brunch', 'quick-bite', 'solo', 'family-friendly'] },
  lunch: { tag: 'quick-bite', first: ['quick-bite', 'business-lunch', 'cheap-eats', 'outdoor-seating'] },
  dinner: { tag: 'date-night', first: ['date-night', 'special-occasion', 'big-group', 'wine'] },
  bar: { tag: 'cocktails', first: ['cocktails', 'wine', 'quiet-drinks', 'craft-beer', 'live-music'] },
  night: { tag: 'club-night', first: ['club-night', 'late-night', 'live-music', 'cheap-eats'] },
};

export function slotAt(hours: number, minutes: number): Slot {
  const t = hours + minutes / 60;
  if (t >= 5 && t < 11) return 'coffee';
  if (t >= 11 && t < 15) return 'lunch';
  if (t >= 15 && t < 17) return 'coffee';
  if (t >= 17 && t < 21) return 'dinner';
  if (t >= 21 || t < 1) return 'bar';
  return 'night';
}

export function berlinClock(date: Date): { hours: number; minutes: number; label: string } {
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Europe/Berlin',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date);
  const hours = Number(parts.find((p) => p.type === 'hour')?.value ?? 0);
  const minutes = Number(parts.find((p) => p.type === 'minute')?.value ?? 0);
  return { hours, minutes, label: `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}` };
}

export function orderTags<T extends { slug: string }>(tags: T[], first: string[]): T[] {
  const lead = first.map((slug) => tags.find((t) => t.slug === slug)).filter((t): t is T => Boolean(t));
  return [...lead, ...tags.filter((t) => !first.includes(t.slug))];
}
```

Create `src/lib/now-url.ts`:

```ts
export const RADII = [2000, 5000, 10000, 20000];
export type Scope = 'following' | 'everyone';
export type NowState = { tag: string; scope: Scope; radius: number; lat: number | null; lng: number | null };
type Params = Record<string, string | string[] | undefined>;

export function nextRadius(radius: number): number {
  const i = RADII.indexOf(radius);
  return RADII[(i + 1) % RADII.length];
}

export function nowHref(state: NowState, patch: Partial<NowState> = {}): string {
  const s = { ...state, ...patch };
  const q = new URLSearchParams({ tag: s.tag });
  if (s.scope !== 'following') q.set('scope', s.scope);
  if (s.radius !== RADII[0]) q.set('radius', String(s.radius));
  if (s.lat !== null && s.lng !== null) {
    q.set('lat', s.lat.toFixed(4));
    q.set('lng', s.lng.toFixed(4));
  }
  return `/?${q.toString()}`;
}

function one(value: string | string[] | undefined): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function coordinate(value: string | string[] | undefined, limit: number): number | null {
  const raw = one(value);
  const n = Number(raw);
  return raw !== undefined && raw !== '' && Number.isFinite(n) && Math.abs(n) <= limit ? n : null;
}

export function parseNowParams(sp: Params, defaultTag: string, validTags: string[]): NowState {
  const tag = one(sp.tag);
  const radius = Number(one(sp.radius));
  const lat = coordinate(sp.lat, 90);
  const lng = coordinate(sp.lng, 180);
  return {
    tag: tag && validTags.includes(tag) ? tag : defaultTag,
    scope: one(sp.scope) === 'everyone' ? 'everyone' : 'following',
    radius: RADII.includes(radius) ? radius : RADII[0],
    lat: lat !== null && lng !== null ? lat : null,
    lng: lat !== null && lng !== null ? lng : null,
  };
}
```

Create `src/lib/viewer.ts`:

```ts
import 'server-only';
import { cache } from 'react';
import { cookies, headers } from 'next/headers';
import { redirect } from 'next/navigation';
import { messages, resolveLocale } from '@/i18n';
import { createClient } from '@/lib/supabase/server';

// Everything a page needs about the current visitor, loaded once per request.
export const getViewer = cache(async () => {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  const profile = user
    ? (await supabase.from('profiles').select('id, username, display_name, locale, is_private, created_at').eq('id', user.id).maybeSingle()).data
    : null;
  const locale = resolveLocale({
    profileLocale: profile?.locale,
    cookie: (await cookies()).get('locale')?.value,
    acceptLanguage: (await headers()).get('accept-language'),
  });
  return { supabase, user, profile, locale, t: messages[locale] };
});

export async function requireMember() {
  const viewer = await getViewer();
  if (!viewer.user) redirect('/login');
  if (!viewer.profile) redirect('/onboarding');
  return { ...viewer, user: viewer.user, profile: viewer.profile };
}
```

- [ ] **Step 5: Design tokens and root layout**

Replace `src/app/globals.css`:

```css
:root {
  color-scheme: light;
  --paper: #ffffff;
  --surface: #f4f4f5;
  --ink: #0b0b0c;
  --ink-soft: #6b6b72;
  --ink-faint: #a3a3aa;
  --line: #e7e7ea;
  --accent: #0b0b0c;
  --accent-ink: #ffffff;
  --danger: #b42318;
  --card: #0b0b0c;
  --card-ink: #f5f5f7;
  --card-soft: #8e8e95;
  --card-line: #26262a;
  --font: var(--font-geist), 'Helvetica Neue', 'Segoe UI', system-ui, -apple-system, sans-serif;
}

@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --paper: #0a0a0b;
    --surface: #151517;
    --ink: #f5f5f7;
    --ink-soft: #9a9aa1;
    --ink-faint: #5e5e65;
    --line: #212124;
    --accent: #f5f5f7;
    --accent-ink: #0a0a0b;
    --danger: #f97066;
    --card: #1a1a1d;
    --card-line: #2e2e33;
  }
}

* { box-sizing: border-box; }
html, body { margin: 0; }
body {
  background: var(--paper);
  color: var(--ink);
  font-family: var(--font);
  font-size: 15px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
}
a { color: inherit; text-decoration: none; }
button, input { font: inherit; color: inherit; }
:focus-visible { outline: 2px solid var(--ink); outline-offset: 2px; }

/* Shell */
.app-header {
  display: flex; align-items: center; justify-content: space-between;
  max-width: 480px; margin: 0 auto;
  padding: calc(20px + env(safe-area-inset-top, 0px)) 24px 8px;
}
.brand { font-weight: 600; font-size: 20px; letter-spacing: -0.03em; }
.brand span { color: var(--ink-faint); }
.page {
  max-width: 480px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px;
  padding: 8px 24px calc(128px + env(safe-area-inset-bottom, 0px));
}
.page--center { min-height: 100dvh; justify-content: center; padding-bottom: 48px; }
.tabs {
  position: fixed; left: 50%; transform: translateX(-50%); z-index: 10;
  bottom: calc(18px + env(safe-area-inset-bottom, 0px));
  display: flex; gap: 4px; padding: 6px;
  border: 1px solid var(--line); border-radius: 999px;
  background: color-mix(in srgb, var(--paper) 82%, transparent);
  -webkit-backdrop-filter: blur(18px) saturate(1.4); backdrop-filter: blur(18px) saturate(1.4);
  box-shadow: 0 12px 32px -12px rgba(0, 0, 0, .28), 0 2px 6px -2px rgba(0, 0, 0, .08);
}
.tab {
  display: flex; align-items: center; gap: 8px; padding: 10px 14px; border-radius: 999px;
  font-size: 13px; font-weight: 500; color: var(--ink-soft);
}
.tab svg { width: 20px; height: 20px; }
.tab span { display: none; }
.tab[aria-current='page'] { background: var(--ink); color: var(--paper); padding-inline: 16px 18px; }
.tab[aria-current='page'] span { display: inline; }

/* Type */
.eyebrow { margin: 12px 0 -16px; font-size: 13px; color: var(--ink-soft); }
.title { margin: 0; font-weight: 500; font-size: 36px; line-height: 1.05; letter-spacing: -0.045em; text-wrap: balance; }
.title em { font-style: normal; color: var(--ink-faint); }
.lede { margin: -12px 0 0; color: var(--ink-soft); }
.section-title { margin: 0; font-size: 13px; font-weight: 500; color: var(--ink-soft); }
.hint { margin: -12px 0 0; font-size: 13px; color: var(--ink-faint); }

/* Controls */
.chips { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: none; margin-inline: -24px; padding-inline: 24px; }
.chip {
  flex: none; border-radius: 999px; padding: 8px 14px; background: var(--surface);
  color: var(--ink-soft); font-size: 13.5px; font-weight: 500; white-space: nowrap;
}
.chip[aria-current] { background: var(--accent); color: var(--accent-ink); }
.metarow { display: flex; align-items: center; gap: 8px; margin-top: -12px; font-size: 13px; color: var(--ink-faint); }
.link { font-weight: 500; color: var(--ink); background: none; border: 0; padding: 0; cursor: pointer; }
.link--soft {
  color: var(--ink-soft); font-weight: 400;
  text-decoration: underline; text-decoration-color: var(--line); text-underline-offset: 4px;
}
.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px; white-space: nowrap;
  border: 1px solid var(--line); background: transparent; border-radius: 12px;
  padding: 12px 16px; font-weight: 500; font-size: 15px; cursor: pointer;
}
.btn--primary { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); }
.btn--danger { color: var(--danger); }
.btn--small { padding: 8px 14px; font-size: 13px; border-radius: 999px; }
.btn--block { width: 100%; padding-block: 15px; }
.btn:disabled { opacity: .5; cursor: not-allowed; }
.actions { display: flex; flex-wrap: wrap; gap: 10px; }
.segmented { display: inline-flex; background: var(--surface); border-radius: 10px; padding: 3px; }
.segmented button {
  border: 0; background: transparent; padding: 6px 12px; border-radius: 8px;
  font-size: 13px; font-weight: 500; color: var(--ink-soft); cursor: pointer;
}
.segmented button[aria-pressed='true'] { background: var(--paper); color: var(--ink); box-shadow: 0 1px 2px rgba(0, 0, 0, .08); }

/* Forms */
.form { display: flex; flex-direction: column; gap: 16px; }
.field { display: flex; flex-direction: column; gap: 8px; }
.label { font-size: 13px; font-weight: 500; color: var(--ink-soft); }
.input { border: 0; border-radius: 12px; background: var(--surface); padding: 13px 14px; font-size: 16px; width: 100%; }
.input::placeholder { color: var(--ink-faint); }
.divider { display: flex; align-items: center; gap: 12px; color: var(--ink-faint); font-size: 13px; }
.divider::before, .divider::after { content: ''; flex: 1; height: 1px; background: var(--line); }
.notice { margin: 0; padding: 12px 14px; border-radius: 12px; background: var(--surface); font-size: 14px; }
.notice--error { color: var(--danger); }

/* Lists */
.list { list-style: none; margin: 0; padding: 0; }
.row { display: grid; grid-template-columns: 1fr auto; gap: 4px 16px; padding: 18px 0; border-top: 1px solid var(--line); }
.list > li:first-child > .row { border-top: 0; }
.row-name { font-size: 18px; font-weight: 500; letter-spacing: -0.02em; }
.row-dist { font-size: 13px; color: var(--ink-soft); font-variant-numeric: tabular-nums; align-self: baseline; }
.row-meta { grid-column: 1 / -1; font-size: 13.5px; color: var(--ink-soft); }
.empty { background: var(--surface); border-radius: 16px; padding: 24px; display: flex; flex-direction: column; gap: 16px; }
.empty p { margin: 0; }
.person { display: grid; grid-template-columns: auto 1fr auto; gap: 12px; align-items: center; padding: 14px 0; border-top: 1px solid var(--line); }
.person-name { font-weight: 500; }
.person-meta { display: block; font-size: 13px; color: var(--ink-soft); }
.avatar {
  width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; flex: none;
  background: var(--surface); font-size: 13px; font-weight: 600;
  box-shadow: 0 0 0 1.5px var(--paper), 0 0 0 3px var(--ink-faint);
}
.avatar--lg { width: 64px; height: 64px; font-size: 22px; }

/* Spot page */
.facts { display: grid; grid-template-columns: auto 1fr; gap: 8px 20px; margin: 0; padding: 16px 0; border-block: 1px solid var(--line); font-size: 14px; }
.facts dt { color: var(--ink-soft); }
.facts dd { margin: 0; }
.quote { margin: 4px 0 0; }
.tags-inline { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: 13px; color: var(--ink-faint); }

/* Profile */
.profile-head { display: grid; grid-template-columns: auto 1fr; gap: 16px; align-items: center; }
.profile-head .title { font-size: 28px; }
.stats { display: flex; gap: 16px; font-size: 13px; color: var(--ink-soft); margin-top: 4px; }
.stats b { color: var(--ink); font-weight: 600; font-variant-numeric: tabular-nums; }
.locked { text-align: center; background: var(--surface); border-radius: 16px; padding: 32px 18px; }
.locked h2 { margin: 0 0 4px; font-size: 15px; }
.locked p { margin: 0; color: var(--ink-soft); }
.share { display: flex; align-items: center; gap: 10px; background: var(--surface); border-radius: 12px; padding: 6px 6px 6px 14px; }
.share code { flex: 1; font-family: var(--font); font-size: 15px; overflow-x: auto; white-space: nowrap; }

/* Membership card */
.card {
  aspect-ratio: 1.586; max-width: 100%; border-radius: 18px; padding: 20px 22px;
  background: var(--card); color: var(--card-ink); border: 1px solid var(--card-line);
  display: grid; grid-template-columns: 1fr auto; grid-template-rows: auto 1fr auto; gap: 8px;
  box-shadow: 0 18px 40px -22px rgba(0, 0, 0, .55);
}
.card-brand { font-weight: 600; font-size: 18px; letter-spacing: -0.03em; }
.card-brand span { color: var(--card-soft); }
.card-type { font-size: 12px; color: var(--card-soft); align-self: center; text-align: right; }
.card-name { grid-column: 1 / -1; align-self: end; font-size: 22px; font-weight: 500; letter-spacing: -0.02em; }
.card-meta { display: flex; flex-direction: column; gap: 2px; font-size: 12px; color: var(--card-soft); align-self: end; }
.card-meta b { color: var(--card-ink); font-weight: 500; }
.card-qr { width: 64px; height: 64px; background: #ffffff; border-radius: 6px; padding: 5px; align-self: end; }
.card-qr svg { display: block; width: 100%; height: 100%; }

/* Settings */
.setting { display: flex; justify-content: space-between; align-items: center; gap: 14px; padding: 14px 0; border-top: 1px solid var(--line); }
.setting small { display: block; color: var(--ink-soft); font-size: 13px; }

@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
```

Replace `src/app/layout.tsx`:

```tsx
import type { Metadata, Viewport } from 'next';
import { Geist } from 'next/font/google';
import { getViewer } from '@/lib/viewer';
import './globals.css';

const geist = Geist({ subsets: ['latin'], variable: '--font-geist' });

export const metadata: Metadata = {
  title: 'spot.',
  description: 'Restaurants and bars your circle has spotted.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  viewportFit: 'cover',
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#0a0a0b' },
  ],
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const { locale } = await getViewer();
  return (
    <html lang={locale} className={geist.variable}>
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 6: Run tests, typecheck, build**

```bash
npm test && npm run typecheck && npm run build
```

Expected: all unit tests pass (env, proxy, i18n, errors, format, time-of-day, now-url); typecheck clean; build succeeds.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(app): design tokens, EN/DE dictionaries and tested helpers"
```

---

### Task 3: Sign-in, onboarding and the members-only shell

**Files:**
- Create:
  - `src/lib/safe-next.ts`, `src/lib/safe-next.test.ts`
  - `src/app/login/{page.tsx,LoginForm.tsx,actions.ts}`
  - `src/app/auth/callback/route.ts`
  - `src/app/onboarding/{page.tsx,OnboardingForm.tsx,actions.ts}`
  - `src/components/{Avatar,Icons,TabBar,Shell}.tsx`
  - `src/app/(app)/layout.tsx`, `src/app/(app)/page.tsx` (temporary; Task 5 replaces it)
  - `playwright.config.ts`
  - `tests/e2e/{global-setup.ts,helpers.ts,auth.spec.ts}`
- Modify: `tsconfig.json` if needed so `tests/` is type-checked (it already includes `**/*.ts`)

**Interfaces:**
- Consumes: `getViewer`, `requireMember`, `messages`, `errorKey`, `env`, `createClient`.
- Produces:
  - `safeNext(value): string` (a same-origin path, default `/`)
  - `<Avatar name size? />`
  - `<Shell username displayName labels>` (header with brand + avatar link to `/m/<username>`, floating `TabBar`)
  - `<TabBar labels={{ now, members }} />`
  - Icons `NowIcon` and `MembersIcon`
  - E2E helpers:
    - `uniqueEmail()`
    - `uniqueUsername()`
    - `signIn(page, email)`
    - `joinAsNewMember(page, name?) → { email, username }`
    - `admin()` (secret-key Supabase client)
  - Routes:
    - `/login`
    - `/auth/callback`
    - `/onboarding`
    - `/` (members only)

- [ ] **Step 1: Write the failing tests**

Create `src/lib/safe-next.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { safeNext } from './safe-next';

describe('safeNext', () => {
  it('keeps same-origin paths', () => {
    expect(safeNext('/members?q=anna')).toBe('/members?q=anna');
  });
  it.each([null, undefined, '', 'https://evil.example', '//evil.example', '/\\evil', 'members'])('rejects %s', (value) => {
    expect(safeNext(value)).toBe('/');
  });
});
```

Create `playwright.config.ts`:

```ts
import { defineConfig, devices } from '@playwright/test';

try {
  process.loadEnvFile('.env.local');
} catch {
  // CI writes .env.local before running; locally run: bash scripts/env-local.sh
}

const executablePath = process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined;

export default defineConfig({
  testDir: 'tests/e2e',
  globalSetup: './tests/e2e/global-setup.ts',
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    ...devices['Pixel 7'],
    baseURL: 'http://127.0.0.1:3000',
    locale: 'en-US',
    timezoneId: 'Europe/Berlin',
    launchOptions: executablePath ? { executablePath } : {},
  },
  webServer: {
    command: process.env.CI
      ? 'npm run start -- --hostname 127.0.0.1 --port 3000'
      : 'npm run dev -- --hostname 127.0.0.1 --port 3000',
    url: 'http://127.0.0.1:3000/login',
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
});
```

Create `tests/e2e/global-setup.ts` (Task 4 adds the demo data call):

```ts
export default async function globalSetup() {
  // Demo data is loaded here from Task 4 on.
}
```

Create `tests/e2e/helpers.ts`:

```ts
import { expect, type Browser, type Page } from '@playwright/test';
import { createClient } from '@supabase/supabase-js';

const MAILPIT = process.env.MAILPIT_URL ?? 'http://127.0.0.1:54324';

export function uniqueEmail(prefix = 'e2e'): string {
  return `${prefix}.${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}@test.spot.local`;
}

export function uniqueUsername(): string {
  return `e2e_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 5)}`;
}

async function signInLink(email: string): Promise<string> {
  for (let attempt = 0; attempt < 40; attempt++) {
    const search = await fetch(`${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:"${email}"`)}`);
    const { messages } = (await search.json()) as { messages?: { ID: string }[] };
    if (messages?.[0]) {
      const message = (await (await fetch(`${MAILPIT}/api/v1/message/${messages[0].ID}`)).json()) as { Text?: string; HTML?: string };
      const match = `${message.Text ?? ''} ${message.HTML ?? ''}`.match(/https?:\/\/[^\s"'<>]+\/auth\/v1\/verify\?[^\s"'<>]+/);
      if (match) return match[0].replaceAll('&amp;', '&');
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`No sign-in email arrived for ${email}`);
}

export async function signIn(page: Page, email: string): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByRole('button', { name: 'Send sign-in link' }).click();
  await expect(page.getByText(`We sent a sign-in link to ${email}`)).toBeVisible();
  await page.goto(await signInLink(email));
}

export async function joinAsNewMember(page: Page, name = 'Test Member'): Promise<{ email: string; username: string }> {
  const email = uniqueEmail();
  const username = uniqueUsername();
  await signIn(page, email);
  await expect(page).toHaveURL(/\/onboarding/);
  await page.getByLabel('Username', { exact: true }).fill(username);
  await page.getByLabel('Name', { exact: true }).fill(name);
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page).toHaveURL(/\/(\?.*)?$/);
  return { email, username };
}

// browser.newPage() does not inherit the project's `use` options; open extra members through this.
export async function newMemberPage(browser: Browser): Promise<Page> {
  const context = await browser.newContext({ baseURL: 'http://127.0.0.1:3000', locale: 'en-US', timezoneId: 'Europe/Berlin' });
  return context.newPage();
}

export function admin() {
  return createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.SUPABASE_SECRET_KEY!, {
    auth: { persistSession: false },
  });
}
```

Create `tests/e2e/auth.spec.ts`:

```ts
import { expect, test } from '@playwright/test';
import { joinAsNewMember, newMemberPage, signIn, uniqueEmail } from './helpers';

test('signed-out visitors are sent to sign in', async ({ page }) => {
  await page.goto('/members');
  await expect(page).toHaveURL(/\/login\?next=%2Fmembers/);
  await expect(page.getByRole('heading', { name: 'Members only.' })).toBeVisible();
});

test('rejects an invalid email address', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill('not-an-email');
  await page.getByRole('button', { name: 'Send sign-in link' }).click();
  await expect(page.getByText('Enter a valid email address.')).toBeVisible();
});

test('a new member signs in with a magic link, picks a username and lands on Now', async ({ page }) => {
  await joinAsNewMember(page, 'Rita Rhein');
  await expect(page.getByRole('link', { name: 'Profile' })).toHaveText('RR');
  await expect(page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Now' })).toHaveAttribute('aria-current', 'page');
});

test('reserved and taken usernames are explained', async ({ page, browser }) => {
  const first = await joinAsNewMember(page);

  const other = await newMemberPage(browser);
  await signIn(other, uniqueEmail());
  await other.getByLabel('Username', { exact: true }).fill('members');
  await other.getByLabel('Name', { exact: true }).fill('Someone');
  await other.getByRole('button', { name: 'Continue' }).click();
  await expect(other.getByText('This username is reserved.')).toBeVisible();

  await other.getByLabel('Username', { exact: true }).fill(first.username);
  await other.getByRole('button', { name: 'Continue' }).click();
  await expect(other.getByText('This username is taken.')).toBeVisible();
});

test('an invalid sign-in link explains itself', async ({ page }) => {
  await page.goto('/auth/callback?code=not-a-real-code');
  await expect(page).toHaveURL(/\/login\?error=link/);
  await expect(page.getByText('This sign-in link is invalid or has expired.')).toBeVisible();
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
npm test                 # expect: safe-next test fails (module missing)
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npm run test:e2e
                         # expect: auth.spec fails (no /login page yet)
```

(`PLAYWRIGHT_CHROMIUM_EXECUTABLE` is only needed in this container; elsewhere run `npx playwright install chromium` once.)

- [ ] **Step 3: Implement safeNext and the shared components**

Create `src/lib/safe-next.ts`:

```ts
// Only same-origin paths may be used as a post-sign-in destination.
export function safeNext(value: FormDataEntryValue | string | string[] | null | undefined): string {
  const path = typeof value === 'string' ? value : '';
  if (!path.startsWith('/') || path.startsWith('//') || path.startsWith('/\\')) return '/';
  return path;
}
```

Create `src/components/Avatar.tsx`:

```tsx
import { initials } from '@/lib/format';

export function Avatar({ name, size }: { name: string; size?: 'lg' }) {
  return (
    <span className={size === 'lg' ? 'avatar avatar--lg' : 'avatar'} aria-hidden="true">
      {initials(name)}
    </span>
  );
}
```

Create `src/components/Icons.tsx`:

```tsx
export function NowIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="m15.5 8.5-2 5-5 2 2-5z" />
    </svg>
  );
}

export function MembersIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 20c.8-3.5 3.4-5.5 6.5-5.5s5.7 2 6.5 5.5" />
      <path d="M16 4.8a3.5 3.5 0 0 1 0 6.4M18 14.8c1.8.7 3 2.5 3.5 5.2" />
    </svg>
  );
}
```

Create `src/components/TabBar.tsx`:

```tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { MembersIcon, NowIcon } from './Icons';

export function TabBar({ labels }: { labels: { now: string; members: string } }) {
  const pathname = usePathname();
  const active = pathname.startsWith('/members') ? 'members' : pathname === '/' || pathname.startsWith('/spots') ? 'now' : null;
  const items = [
    { key: 'now', href: '/', label: labels.now, icon: <NowIcon /> },
    { key: 'members', href: '/members', label: labels.members, icon: <MembersIcon /> },
  ] as const;

  return (
    <nav className="tabs" aria-label="Main">
      {items.map((item) => (
        <Link key={item.key} href={item.href} className="tab" aria-label={item.label} aria-current={active === item.key ? 'page' : undefined}>
          {item.icon}
          <span>{item.label}</span>
        </Link>
      ))}
    </nav>
  );
}
```

Create `src/components/Shell.tsx`:

```tsx
import Link from 'next/link';
import type { Messages } from '@/i18n';
import { Avatar } from './Avatar';
import { TabBar } from './TabBar';

export function Shell({
  username,
  displayName,
  nav,
  children,
}: {
  username: string;
  displayName: string;
  nav: Messages['nav'];
  children: React.ReactNode;
}) {
  return (
    <>
      <header className="app-header">
        <Link href="/" className="brand">spot<span>.</span></Link>
        <Link href={`/m/${username}`} aria-label={nav.profile}>
          <Avatar name={displayName} />
        </Link>
      </header>
      <main className="page">{children}</main>
      <TabBar labels={{ now: nav.now, members: nav.members }} />
    </>
  );
}
```

Note for the test `toHaveText('RR')`: the avatar link's accessible name comes from `aria-label` ("Profile"), and its text content is the initials.

- [ ] **Step 4: Implement sign-in**

Create `src/app/login/actions.ts`:

```ts
'use server';

import { redirect } from 'next/navigation';
import { env } from '@/lib/env';
import { safeNext } from '@/lib/safe-next';
import { createClient } from '@/lib/supabase/server';
import { getViewer } from '@/lib/viewer';

export type LoginState = { status: 'idle' | 'sent' | 'error'; message: string };

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function callbackUrl(next: string): string {
  return `${env.siteUrl()}/auth/callback?next=${encodeURIComponent(next)}`;
}

export async function sendMagicLink(_previous: LoginState, formData: FormData): Promise<LoginState> {
  const { t } = await getViewer();
  const email = String(formData.get('email') ?? '').trim().toLowerCase();
  if (!EMAIL.test(email)) return { status: 'error', message: t.errors.email };

  const supabase = await createClient();
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: callbackUrl(safeNext(formData.get('next'))) },
  });
  if (error) return { status: 'error', message: t.errors.generic };
  return { status: 'sent', message: t.login.sent(email) };
}

async function signInWith(provider: 'google' | 'apple', formData: FormData): Promise<never> {
  const supabase = await createClient();
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider,
    options: { redirectTo: callbackUrl(safeNext(formData.get('next'))) },
  });
  redirect(error || !data.url ? '/login?error=generic' : data.url);
}

export async function signInWithGoogle(formData: FormData) {
  await signInWith('google', formData);
}

export async function signInWithApple(formData: FormData) {
  await signInWith('apple', formData);
}
```

Create `src/app/login/LoginForm.tsx`:

```tsx
'use client';

import { useActionState } from 'react';
import { sendMagicLink, type LoginState } from './actions';

export function LoginForm({ next, labels }: { next: string; labels: { email: string; placeholder: string; send: string } }) {
  const [state, action, pending] = useActionState<LoginState, FormData>(sendMagicLink, { status: 'idle', message: '' });

  return (
    <form action={action} className="form" noValidate>
      <input type="hidden" name="next" value={next} />
      <div className="field">
        <label className="label" htmlFor="email">{labels.email}</label>
        <input id="email" name="email" type="email" autoComplete="email" required className="input" placeholder={labels.placeholder} />
      </div>
      {state.status !== 'idle' && (
        <p className={state.status === 'error' ? 'notice notice--error' : 'notice'} role="status">{state.message}</p>
      )}
      <button type="submit" className="btn btn--primary btn--block" disabled={pending}>{labels.send}</button>
    </form>
  );
}
```

`noValidate` is deliberate: the server validates the address and answers in the member's language (tested in `auth.spec.ts`).

Create `src/app/login/page.tsx`:

```tsx
import { redirect } from 'next/navigation';
import { env } from '@/lib/env';
import { safeNext } from '@/lib/safe-next';
import { getViewer } from '@/lib/viewer';
import { signInWithApple, signInWithGoogle } from './actions';
import { LoginForm } from './LoginForm';

export default async function LoginPage({ searchParams }: PageProps<'/login'>) {
  const sp = await searchParams;
  const { user, t } = await getViewer();
  const next = safeNext(sp.next);
  if (user) redirect(next);

  const errorParam = typeof sp.error === 'string' && sp.error in t.errors ? (sp.error as keyof typeof t.errors) : null;
  const providers = [
    env.googleEnabled() && { action: signInWithGoogle, label: t.login.google },
    env.appleEnabled() && { action: signInWithApple, label: t.login.apple },
  ].filter(Boolean) as { action: (formData: FormData) => Promise<void>; label: string }[];

  return (
    <main className="page page--center">
      <p className="brand">spot<span>.</span></p>
      <h1 className="title">{t.login.title}</h1>
      <p className="lede">{t.login.subtitle}</p>
      {sp.deleted === '1' && <p className="notice" role="status">{t.login.deleted}</p>}
      {errorParam && <p className="notice notice--error" role="alert">{t.errors[errorParam]}</p>}
      <LoginForm next={next} labels={{ email: t.login.email, placeholder: t.login.emailPlaceholder, send: t.login.send }} />
      {providers.length > 0 && (
        <>
          <p className="divider">{t.login.or}</p>
          {providers.map((provider) => (
            <form key={provider.label} action={provider.action}>
              <input type="hidden" name="next" value={next} />
              <button type="submit" className="btn btn--block">{provider.label}</button>
            </form>
          ))}
        </>
      )}
    </main>
  );
}
```

Create `src/app/auth/callback/route.ts`:

```ts
import { NextResponse, type NextRequest } from 'next/server';
import { safeNext } from '@/lib/safe-next';
import { createClient } from '@/lib/supabase/server';

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const code = searchParams.get('code');
  const next = safeNext(searchParams.get('next'));

  if (code) {
    const supabase = await createClient();
    const { error } = await supabase.auth.exchangeCodeForSession(code);
    if (!error) return NextResponse.redirect(new URL(next, request.url));
  }
  return NextResponse.redirect(new URL('/login?error=link', request.url));
}
```

- [ ] **Step 5: Implement onboarding and the members-only layout**

Create `src/app/onboarding/actions.ts`:

```ts
'use server';

import { redirect } from 'next/navigation';
import { errorKey } from '@/lib/errors';
import { getViewer } from '@/lib/viewer';

export type OnboardingState = { message: string | null };

export async function createProfile(_previous: OnboardingState, formData: FormData): Promise<OnboardingState> {
  const { supabase, user, locale, t } = await getViewer();
  if (!user) redirect('/login');

  const username = String(formData.get('username') ?? '').trim().toLowerCase();
  const displayName = String(formData.get('displayName') ?? '').trim();
  if (!/^[a-z0-9_]{3,30}$/.test(username)) return { message: t.errors.username_format };
  if (displayName.length < 1 || displayName.length > 50) return { message: t.errors.display_name };

  const { error } = await supabase.from('profiles').insert({ id: user.id, username, display_name: displayName, locale });
  if (error) return { message: t.errors[errorKey(error)] };
  redirect('/');
}
```

Create `src/app/onboarding/OnboardingForm.tsx`:

```tsx
'use client';

import { useActionState } from 'react';
import { createProfile, type OnboardingState } from './actions';

export function OnboardingForm({
  labels,
}: {
  labels: { username: string; usernameHint: string; displayName: string; submit: string };
}) {
  const [state, action, pending] = useActionState<OnboardingState, FormData>(createProfile, { message: null });

  return (
    <form action={action} className="form" noValidate>
      <div className="field">
        <label className="label" htmlFor="username">{labels.username}</label>
        <input id="username" name="username" className="input" autoComplete="username" autoCapitalize="none" spellCheck={false} maxLength={30} required />
        <small className="hint" style={{ margin: 0 }}>{labels.usernameHint}</small>
      </div>
      <div className="field">
        <label className="label" htmlFor="displayName">{labels.displayName}</label>
        <input id="displayName" name="displayName" className="input" autoComplete="name" maxLength={50} required />
      </div>
      {state.message && <p className="notice notice--error" role="alert">{state.message}</p>}
      <button type="submit" className="btn btn--primary btn--block" disabled={pending}>{labels.submit}</button>
    </form>
  );
}
```

Create `src/app/onboarding/page.tsx`:

```tsx
import { redirect } from 'next/navigation';
import { getViewer } from '@/lib/viewer';
import { OnboardingForm } from './OnboardingForm';

export default async function OnboardingPage() {
  const { user, profile, t } = await getViewer();
  if (!user) redirect('/login');
  if (profile) redirect('/');

  return (
    <main className="page page--center">
      <p className="brand">spot<span>.</span></p>
      <h1 className="title">{t.onboarding.title}</h1>
      <p className="lede">{t.onboarding.subtitle}</p>
      <OnboardingForm
        labels={{
          username: t.onboarding.username,
          usernameHint: t.onboarding.usernameHint,
          displayName: t.onboarding.displayName,
          submit: t.onboarding.submit,
        }}
      />
    </main>
  );
}
```

Create `src/app/(app)/layout.tsx`:

```tsx
import { Shell } from '@/components/Shell';
import { requireMember } from '@/lib/viewer';

export default async function MembersLayout({ children }: { children: React.ReactNode }) {
  const { profile, t } = await requireMember();
  return (
    <Shell username={profile.username} displayName={profile.display_name} nav={t.nav}>
      {children}
    </Shell>
  );
}
```

Create the temporary `src/app/(app)/page.tsx` (Task 5 replaces it):

```tsx
import { berlinClock, slotAt } from '@/lib/time-of-day';
import { requireMember } from '@/lib/viewer';

export default async function NowPage() {
  const { t } = await requireMember();
  const clock = berlinClock(new Date());
  const [lead, rest] = t.now.slots[slotAt(clock.hours, clock.minutes)];
  return <h1 className="title">{lead} <em>{rest}</em></h1>;
}
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
npm test && npm run typecheck
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npm run test:e2e
```

Expected: unit tests pass; `auth.spec.ts` 5/5 pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(app): magic-link sign-in, onboarding and members-only shell"
```

---

### Task 4: Coffee and club-night moods, and local demo data

**Files:**
- Create: `supabase/migrations/20260927000009_moods.sql`, `scripts/seed-demo.ts`
- Modify: `supabase/tests/04_tags_places.test.sql` (tag count 16 → 18), `tests/e2e/global-setup.ts`

**Interfaces:**
- Consumes: the tables from Plan 1, `.env.local` (`NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SECRET_KEY`).
- Produces:
  - Active tags `coffee` (Coffee / Kaffee, sort 170) and `club-night` (Club night / Clubnacht, sort 180).
  - `npm run seed:demo`: an idempotent local demo set with these members, all public except jonas:

    | Username | Display name |
    |---|---|
    | anna | Anna |
    | mehmet_eats | Mehmet |
    | lea | Lea |
    | sofia_isst | Sofia Brandt |
    | tim | Tim |
    | jonas | Jonas (private) |

  - The demo set also has 12 places with `google_place_id` `demo-p1`…`demo-p12` and 19 spots.
  - Demo emails are `<username>@demo.spot.local`.
  - The e2e global setup runs `seed:demo`.

- [ ] **Step 1: Write the failing database test change**

In `supabase/tests/04_tags_places.test.sql`, change the first assertion to expect 18 tags:

```sql
select is(
  (select count(*) from public.tags where active),
  18::bigint,
  'the 18 launch tags are seeded and readable by visitors'
);
```

and add two assertions at the end (raise `plan(6)` to `plan(8)`):

```sql
select results_eq(
  $$ select label_en, label_de from public.tags where slug = 'coffee' $$,
  $$ values ('Coffee'::text, 'Kaffee'::text) $$,
  'coffee mood exists in both languages'
);

select results_eq(
  $$ select label_en, label_de from public.tags where slug = 'club-night' $$,
  $$ values ('Club night'::text, 'Clubnacht'::text) $$,
  'club-night mood exists in both languages'
);
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm run test:db`
Expected: `04_tags_places.test.sql` FAILS (16 tags, no coffee/club-night).

- [ ] **Step 3: Add the migration**

Create `supabase/migrations/20260927000009_moods.sql`:

```sql
-- Moods for the time-aware home screen (spec §10): coffee in the morning, club night after 01:00.
insert into public.tags (slug, label_en, label_de, sort_order) values
  ('coffee', 'Coffee', 'Kaffee', 170),
  ('club-night', 'Club night', 'Clubnacht', 180)
on conflict (slug) do nothing;
```

Run: `npm run test:db`. Expected: all database tests pass.

- [ ] **Step 4: Write the demo data script**

Create `scripts/seed-demo.ts`:

```ts
// Local demo data: invented members, places and spots in Düsseldorf.
// Run with: npm run seed:demo (idempotent). Refuses to run against a non-local Supabase.
import { createClient } from '@supabase/supabase-js';

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const key = process.env.SUPABASE_SECRET_KEY;
if (!url || !key) throw new Error('Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SECRET_KEY (bash scripts/env-local.sh).');
if (!/^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?/.test(url)) throw new Error('Demo data is for local development only.');

const db = createClient(url, key, { auth: { persistSession: false } });

const MEMBERS = [
  { username: 'anna', display_name: 'Anna', is_private: false },
  { username: 'mehmet_eats', display_name: 'Mehmet', is_private: false },
  { username: 'lea', display_name: 'Lea', is_private: false },
  { username: 'sofia_isst', display_name: 'Sofia Brandt', is_private: false },
  { username: 'tim', display_name: 'Tim', is_private: false },
  { username: 'jonas', display_name: 'Jonas', is_private: true },
];

// Around Oberkassel, Düsseldorf. Names and places are invented; streets are real.
const PLACES = [
  { key: 'p1', name: 'Bar Nachtfalter', address: 'Dominikanerstraße, Düsseldorf', lat: 51.22865, lng: 6.7588 },
  { key: 'p2', name: 'Lotte & Lime', address: 'Luegallee, Düsseldorf', lat: 51.22721, lng: 6.76311 },
  { key: 'p3', name: 'Kantine am Platz', address: 'Belsenplatz, Düsseldorf', lat: 51.23008, lng: 6.75163 },
  { key: 'p4', name: 'Weinstube Blau', address: 'Alt-Niederkassel, Düsseldorf', lat: 51.24221, lng: 6.7502 },
  { key: 'p5', name: 'Café Schwalbe', address: 'Oberkasseler Straße, Düsseldorf', lat: 51.23592, lng: 6.76096 },
  { key: 'p6', name: 'Hafenwirtschaft 7', address: 'Speditionstraße, Düsseldorf', lat: 51.20655, lng: 6.78176 },
  { key: 'p7', name: 'Nudelwerk', address: 'Kurze Straße, Düsseldorf', lat: 51.2335, lng: 6.77602 },
  { key: 'p8', name: 'Sonnendeck', address: 'Kaistraße, Düsseldorf', lat: 51.21328, lng: 6.77745 },
  { key: 'p9', name: 'Rote Laterne', address: 'Ratinger Straße, Düsseldorf', lat: 51.23619, lng: 6.76741 },
  { key: 'p10', name: 'Olivenhain', address: 'Kaiserswerther Markt, Düsseldorf', lat: 51.30087, lng: 6.77602 },
  { key: 'p11', name: 'Klavierzimmer', address: 'Bilker Straße, Düsseldorf', lat: 51.22811, lng: 6.77961 },
  { key: 'p12', name: 'Keller 12', address: 'Bolkerstraße, Düsseldorf', lat: 51.23439, lng: 6.77458 },
];

const SPOTS: [username: string, place: string, tags: string[], note: string | null][] = [
  ['anna', 'p1', ['date-night', 'cocktails'], 'Sit at the bar and ask for the house negroni.'],
  ['anna', 'p4', ['wine', 'quiet-drinks'], 'Natural wines by the glass. Very calm on weekdays.'],
  ['anna', 'p5', ['coffee', 'brunch'], 'The best flat white in Oberkassel.'],
  ['anna', 'p3', ['quick-bite', 'business-lunch'], 'Order the daily special.'],
  ['mehmet_eats', 'p1', ['date-night'], 'Dim light, good playlist. Book ahead on Fridays.'],
  ['mehmet_eats', 'p3', ['cheap-eats', 'quick-bite'], 'Lunch menu under 10 €.'],
  ['mehmet_eats', 'p9', ['late-night', 'cheap-eats'], 'Open until 3. The dumplings save every night out.'],
  ['mehmet_eats', 'p6', ['big-group', 'craft-beer', 'outdoor-seating'], null],
  ['mehmet_eats', 'p12', ['club-night', 'late-night'], 'Techno in a vaulted cellar. Goes until sunrise.'],
  ['lea', 'p2', ['date-night', 'special-occasion'], 'The tasting menu is worth it for anniversaries.'],
  ['lea', 'p4', ['date-night', 'wine'], 'Candles and a short, good wine list.'],
  ['lea', 'p8', ['outdoor-seating', 'cocktails'], 'Go for sunset.'],
  ['lea', 'p5', ['brunch', 'family-friendly'], 'Kids’ corner in the back.'],
  ['sofia_isst', 'p11', ['live-music', 'date-night'], 'Jazz trio from Thursday to Saturday.'],
  ['sofia_isst', 'p10', ['date-night', 'wine'], 'Worth the trip across town.'],
  ['sofia_isst', 'p7', ['solo', 'quick-bite'], 'Counter seats, fast service, great for eating alone.'],
  ['tim', 'p6', ['big-group'], null],
  ['tim', 'p3', ['cheap-eats'], null],
  ['jonas', 'p4', ['date-night'], 'My favourite place in Niederkassel.'],
];

async function memberId(member: (typeof MEMBERS)[number]): Promise<string> {
  const { data: existing } = await db.from('profiles').select('id').eq('username', member.username).maybeSingle();
  if (existing) return existing.id;

  const email = `${member.username}@demo.spot.local`;
  let userId: string | undefined;
  const created = await db.auth.admin.createUser({ email, email_confirm: true });
  if (created.data.user) userId = created.data.user.id;
  else {
    const { data } = await db.auth.admin.listUsers({ perPage: 1000 });
    userId = data.users.find((u) => u.email === email)?.id;
  }
  if (!userId) throw created.error ?? new Error(`Could not create ${email}`);

  const { error } = await db.from('profiles').insert({ id: userId, locale: 'de', ...member });
  if (error) throw error;
  return userId;
}

const ids = new Map<string, string>();
for (const member of MEMBERS) ids.set(member.username, await memberId(member));

const { data: places, error: placeError } = await db
  .from('places')
  .upsert(
    PLACES.map((p) => ({
      google_place_id: `demo-${p.key}`,
      name: p.name,
      address: p.address,
      location: `SRID=4326;POINT(${p.lng} ${p.lat})`,
    })),
    { onConflict: 'google_place_id' },
  )
  .select('id, google_place_id');
if (placeError) throw placeError;
const placeIds = new Map(places.map((p) => [p.google_place_id.replace('demo-', ''), p.id]));

const { error: spotError } = await db.from('recommendations').upsert(
  SPOTS.map(([username, place, tags, note]) => ({ user_id: ids.get(username)!, place_id: placeIds.get(place)!, tags, note })),
  { onConflict: 'user_id,place_id' },
);
if (spotError) throw spotError;

console.log(`Demo data ready: ${MEMBERS.length} members, ${PLACES.length} places, ${SPOTS.length} spots.`);
```

Replace `tests/e2e/global-setup.ts`:

```ts
import { execSync } from 'node:child_process';

export default async function globalSetup() {
  execSync('npm run seed:demo', { stdio: 'inherit' });
}
```

- [ ] **Step 5: Verify the demo data**

```bash
npm run seed:demo   # expect: Demo data ready: 6 members, 12 places, 19 spots.
npm run seed:demo   # run again: same line, no error (idempotent)
npm run typecheck
```

Note: `scripts/` is covered by `tsconfig.json`'s `**/*.ts`. If Next's type check complains about top-level `await` in the script, add `"scripts"` to the `exclude` array in `tsconfig.json` and document it in the report. The script is run by Node, not bundled.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(db): coffee and club-night moods; local Düsseldorf demo data"
```

---

### Task 5: The Now screen

**Files:**
- Create: `src/components/LocateMe.tsx`, `tests/e2e/now.spec.ts`
- Replace: `src/app/(app)/page.tsx`

**Interfaces:**
- Consumes:
  - `requireMember`
  - `SLOTS`, `slotAt`, `berlinClock`, `orderTags`
  - `parseNowParams`, `nowHref`, `nextRadius`
  - `formatDistance`
  - `errorKey`
  - RPC `discover(p_tag, p_lat, p_lng, p_radius_m, p_scope)`
  - `tags` table
  - Demo data (Task 4)
- Produces:
  - `/` shows the time-aware headline, mood chips (links), a scope toggle, a radius cycle, a result list linking to `/spots/<place_id>`, and empty states.
  - Location comes from the URL (`lat`, `lng`). `<LocateMe>` asks the browser once per session and falls back to Oberkassel.

- [ ] **Step 1: Write the failing e2e test**

Create `tests/e2e/now.spec.ts`:

```ts
import { expect, test } from '@playwright/test';
import { joinAsNewMember } from './helpers';

const OBERKASSEL = 'lat=51.2317&lng=6.7545';

test.beforeEach(async ({ page }) => {
  await joinAsNewMember(page);
});

test('greets with a time-aware question and a mood row', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(/^(Time for coffee\?|Where for lunch\?|Where for dinner\?|One more drink\?|Still dancing\?)$/);
  await expect(page.getByRole('navigation', { name: 'Moods' }).getByRole('link', { name: 'Coffee' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Moods' }).locator('[aria-current]')).toHaveCount(1);
});

test('a new member has an empty circle and can ask all members', async ({ page }) => {
  await page.goto(`/?tag=date-night&${OBERKASSEL}`);
  await expect(page.getByText('No one in your circle has spotted a date night place nearby yet.')).toBeVisible();
  await page.getByRole('link', { name: 'Ask all members' }).click();

  const rows = page.getByRole('list').getByRole('link');
  await expect(rows).toHaveCount(4);
  await expect(rows.nth(0)).toContainText('Bar Nachtfalter');
  await expect(rows.nth(0)).toContainText('+ 1 member');
  await expect(page.getByText('Weinstube Blau')).toBeVisible();
  await expect(page.getByText('Klavierzimmer')).toBeVisible();
});

test('private members’ spots never appear for strangers', async ({ page }) => {
  await page.goto(`/?tag=date-night&scope=everyone&${OBERKASSEL}`);
  // Jonas (private) also spotted Weinstube Blau; only Lea is shown there.
  await expect(page.getByRole('link', { name: /Weinstube Blau/ })).toContainText('Lea');
  await expect(page.getByRole('link', { name: /Weinstube Blau/ })).not.toContainText('+ 1 member');
});

test('the radius cycles and widening finds farther places', async ({ page }) => {
  await page.goto(`/?tag=date-night&scope=everyone&${OBERKASSEL}`);
  await expect(page.getByText('Olivenhain')).toHaveCount(0);
  await page.getByRole('link', { name: 'within 2 km' }).click();
  await expect(page).toHaveURL(/radius=5000/);
  await page.getByRole('link', { name: 'within 5 km' }).click();
  await page.getByRole('link', { name: 'within 10 km' }).click();
  await expect(page.getByText('Olivenhain')).toBeVisible();
});

test('switching the mood filters the list', async ({ page }) => {
  await page.goto(`/?tag=coffee&scope=everyone&${OBERKASSEL}`);
  await expect(page.getByRole('list').getByRole('link')).toHaveCount(1);
  await expect(page.getByText('Café Schwalbe')).toBeVisible();
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npx playwright test tests/e2e/now.spec.ts`
Expected: FAIL. There is no mood row or list yet.

- [ ] **Step 3: Implement**

Create `src/components/LocateMe.tsx`:

```tsx
'use client';

import { useEffect } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';

const ASKED = 'spot:location-asked';

// Asks for the browser location once per session and puts it into the URL.
export function LocateMe({ hasLocation }: { hasLocation: boolean }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  useEffect(() => {
    if (hasLocation || !('geolocation' in navigator)) return;
    try {
      if (sessionStorage.getItem(ASKED)) return;
      sessionStorage.setItem(ASKED, '1');
    } catch {
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const next = new URLSearchParams(params.toString());
        next.set('lat', position.coords.latitude.toFixed(4));
        next.set('lng', position.coords.longitude.toFixed(4));
        router.replace(`${pathname}?${next.toString()}`, { scroll: false });
      },
      () => {},
      { maximumAge: 300_000, timeout: 10_000 },
    );
  }, [hasLocation, params, pathname, router]);

  return null;
}
```

Replace `src/app/(app)/page.tsx`:

```tsx
import Link from 'next/link';
import { Suspense } from 'react';
import { LocateMe } from '@/components/LocateMe';
import { errorKey } from '@/lib/errors';
import { formatDistance } from '@/lib/format';
import { nextRadius, nowHref, parseNowParams, RADII } from '@/lib/now-url';
import { berlinClock, orderTags, SLOTS, slotAt } from '@/lib/time-of-day';
import { requireMember } from '@/lib/viewer';

const OBERKASSEL = { lat: 51.2317, lng: 6.7545 };
type Recommender = { id: string; username: string; display_name: string };

export default async function NowPage({ searchParams }: PageProps<'/'>) {
  const { supabase, t, locale } = await requireMember();
  const clock = berlinClock(new Date());
  const slot = slotAt(clock.hours, clock.minutes);

  const { data: tagRows } = await supabase.from('tags').select('slug, label_en, label_de').eq('active', true).order('sort_order');
  const tags = orderTags(tagRows ?? [], SLOTS[slot].first);
  const state = parseNowParams(await searchParams, SLOTS[slot].tag, tags.map((tag) => tag.slug));
  const hasLocation = state.lat !== null && state.lng !== null;
  const origin = hasLocation ? { lat: state.lat!, lng: state.lng! } : OBERKASSEL;

  const { data: results, error } = await supabase.rpc('discover', {
    p_tag: state.tag,
    p_lat: origin.lat,
    p_lng: origin.lng,
    p_radius_m: state.radius,
    p_scope: state.scope,
  });

  const label = (slug: string) => {
    const tag = tags.find((x) => x.slug === slug);
    return tag ? (locale === 'de' ? tag.label_de : tag.label_en) : slug;
  };
  const [lead, rest] = t.now.slots[slot];
  const widest = state.radius === RADII[RADII.length - 1];

  return (
    <>
      <Suspense>
        <LocateMe hasLocation={hasLocation} />
      </Suspense>
      <p className="eyebrow">{hasLocation ? t.now.nearYou : t.now.fallbackArea} · {clock.label}</p>
      <h1 className="title">{lead} <em>{rest}</em></h1>

      <nav className="chips" aria-label={t.now.moods}>
        {tags.map((tag) => (
          <Link key={tag.slug} className="chip" href={nowHref(state, { tag: tag.slug })} scroll={false} aria-current={tag.slug === state.tag ? 'true' : undefined}>
            {label(tag.slug)}
          </Link>
        ))}
      </nav>

      <div className="metarow">
        <Link className="link" scroll={false} href={nowHref(state, { scope: state.scope === 'following' ? 'everyone' : 'following' })}>
          {state.scope === 'following' ? t.now.following : t.now.everyone}
        </Link>
        <span aria-hidden="true">·</span>
        <Link className="link link--soft" scroll={false} href={nowHref(state, { radius: nextRadius(state.radius) })}>
          {t.now.within(widest ? t.now.wholeCity : formatDistance(state.radius, locale))}
        </Link>
      </div>
      {!hasLocation && <p className="hint">{t.now.locationOff}</p>}

      {error ? (
        <p className="notice notice--error" role="alert">{t.errors[errorKey(error)]}</p>
      ) : results && results.length > 0 ? (
        <ul className="list">
          {results.map((result) => {
            const first = ((result.recommenders ?? []) as Recommender[])[0];
            const others = Number(result.recommender_count) - 1;
            return (
              <li key={result.place_id}>
                <Link className="row" href={`/spots/${result.place_id}`}>
                  <span className="row-name">{result.name}</span>
                  <span className="row-dist">{formatDistance(result.distance_m, locale)}</span>
                  <span className="row-meta">{first?.display_name}{others > 0 ? t.now.and(others) : ''}</span>
                </Link>
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="empty">
          <p>{state.scope === 'following' ? t.now.empty(label(state.tag)) : t.now.emptyEveryone(label(state.tag))}</p>
          <div className="actions">
            {!widest && <Link className="btn" href={nowHref(state, { radius: nextRadius(state.radius) })}>{t.now.widen}</Link>}
            {state.scope === 'following' && <Link className="btn btn--primary" href={nowHref(state, { scope: 'everyone' })}>{t.now.askAll}</Link>}
          </div>
        </div>
      )}
    </>
  );
}
```

- [ ] **Step 4: Run tests**

```bash
npm test && npm run typecheck
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npm run test:e2e
```

Expected: all unit tests pass; all e2e specs pass (auth + now).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(app): time-aware Now screen backed by discover()"
```

---

### Task 6: Spot page

**Files:**
- Create: `src/app/(app)/spots/[id]/page.tsx`, `tests/e2e/spot.spec.ts`

**Interfaces:**
- Consumes: `requireMember`, `places`, `recommendations` (embedding `author:profiles(username, display_name)`), `tags`, `<Avatar>`.
- Produces: `/spots/<place id>`. It shows the name, address, a Google Maps link, and "Spotted by", listing each visible spot with author (link to `/m/<username>`), note and moods. Unknown ids return 404.

- [ ] **Step 1: Write the failing e2e test**

Create `tests/e2e/spot.spec.ts`:

```ts
import { expect, test } from '@playwright/test';
import { joinAsNewMember } from './helpers';

test.beforeEach(async ({ page }) => {
  await joinAsNewMember(page);
});

test('opening a spot shows who spotted it and what they wrote', async ({ page }) => {
  await page.goto('/?tag=date-night&scope=everyone&lat=51.2317&lng=6.7545');
  await page.getByRole('link', { name: /Bar Nachtfalter/ }).click();

  await expect(page.getByRole('heading', { level: 1, name: 'Bar Nachtfalter' })).toBeVisible();
  await expect(page.getByText('Dominikanerstraße, Düsseldorf')).toBeVisible();
  await expect(page.getByRole('heading', { name: /Spotted by/ })).toBeVisible();
  await expect(page.getByText('Sit at the bar and ask for the house negroni.')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Anna', exact: true })).toHaveAttribute('href', '/m/anna');
  await expect(page.getByRole('link', { name: 'Open in Google Maps' })).toHaveAttribute('href', /google\.com\/maps/);
});

test('a private member’s spot is not listed for strangers', async ({ page }) => {
  await page.goto('/?tag=wine&scope=everyone&lat=51.2317&lng=6.7545');
  await page.getByRole('link', { name: /Weinstube Blau/ }).click();
  await expect(page.getByText('My favourite place in Niederkassel.')).toHaveCount(0);
});

test('an unknown spot is a 404', async ({ page }) => {
  const response = await page.goto('/spots/00000000-0000-0000-0000-000000000000');
  expect(response?.status()).toBe(404);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npx playwright test tests/e2e/spot.spec.ts`
Expected: FAIL (404 for every spot: page missing).

- [ ] **Step 3: Implement**

Create `src/app/(app)/spots/[id]/page.tsx`:

```tsx
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { Avatar } from '@/components/Avatar';
import { requireMember } from '@/lib/viewer';

export default async function SpotPage({ params }: PageProps<'/spots/[id]'>) {
  const { id } = await params;
  const { supabase, t, locale } = await requireMember();

  const { data: place } = await supabase.from('places').select('id, name, address, google_place_id').eq('id', id).maybeSingle();
  if (!place) notFound();

  const [{ data: spots }, { data: tags }] = await Promise.all([
    supabase
      .from('recommendations')
      .select('id, tags, note, author:profiles(username, display_name)')
      .eq('place_id', place.id)
      .order('created_at', { ascending: false }),
    supabase.from('tags').select('slug, label_en, label_de'),
  ]);
  const label = (slug: string) => {
    const tag = tags?.find((x) => x.slug === slug);
    return tag ? (locale === 'de' ? tag.label_de : tag.label_en) : slug;
  };
  const maps = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${place.name} ${place.address ?? ''}`)}&query_place_id=${encodeURIComponent(place.google_place_id)}`;

  return (
    <>
      <Link href="/" className="link link--soft">← {t.spot.back}</Link>
      <h1 className="title">{place.name}</h1>
      <dl className="facts">
        <dt>{t.spot.address}</dt>
        <dd>{place.address}</dd>
      </dl>
      <div className="actions">
        <a className="btn" href={maps} target="_blank" rel="noreferrer">{t.spot.openMaps}</a>
      </div>
      <h2 className="section-title">{t.spot.spottedBy} · {spots?.length ?? 0}</h2>
      <ul className="list">
        {(spots ?? []).map((spot) => (
          <li key={spot.id} className="person" style={{ alignItems: 'start' }}>
            <Avatar name={spot.author?.display_name ?? '?'} />
            <div>
              <Link className="person-name" href={`/m/${spot.author?.username}`}>{spot.author?.display_name}</Link>
              {spot.note && <p className="quote">{spot.note}</p>}
              <div className="tags-inline">{spot.tags.map((slug) => <span key={slug}>{label(slug)}</span>)}</div>
            </div>
            <span />
          </li>
        ))}
      </ul>
    </>
  );
}
```

If the generated types model `author` as an array rather than an object, use `.select('..., author:profiles!inner(username, display_name)')` or read `spot.author` accordingly, and record the choice in the report. Each recommendation has exactly one author (FK `recommendations.user_id → profiles.id`).

- [ ] **Step 4: Run tests**

```bash
npm run typecheck
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npm run test:e2e
```

Expected: all e2e specs pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(app): spot page with the circle's notes"
```

---

### Task 7: Members, circles, introductions and profiles

**Files:**
- Create:
  - `src/lib/actions/follow.ts`
  - `src/components/{FollowButton,CopyButton,PublicShell}.tsx`
  - `src/app/(app)/members/page.tsx`
  - `src/app/m/[username]/{layout.tsx,page.tsx}`
  - `tests/e2e/members.spec.ts`

**Interfaces:**
- Consumes: `requireMember`, `getViewer`, `safeNext`, `errorKey`, `env.siteUrl`, `follow_counts`, `follows`, `profiles`, `recommendations`, `<Shell>`, `<Avatar>`.
- Produces:
  - Server actions, each taking `FormData` with `userId` and `returnTo`:
    - `followMember`
    - `unfollowMember`
    - `acceptRequest`
    - `declineRequest`
  - Each action redirects to `returnTo`, adding `?error=<key>` on failure.
  - `<FollowButton userId isPrivate status returnTo labels />`
  - `<CopyButton text label doneLabel share? />` (client; `share` uses the Web Share API when available)
  - `<PublicShell signInLabel>`
  - `/members` (invitation, search `?q=`, member list)
  - `/m/<username>` (header, counts, follow button, spots or locked panel)
  - Signed-out visitors to `/m/<username>` see a join prompt.

- [ ] **Step 1: Write the failing e2e test**

Create `tests/e2e/members.spec.ts`:

```ts
import { expect, test } from '@playwright/test';
import { joinAsNewMember } from './helpers';

test('adding a member to your circle brings their spots into My circle', async ({ page }) => {
  await joinAsNewMember(page);
  await page.getByRole('link', { name: 'Members' }).click();
  await expect(page.getByRole('heading', { name: 'Members' })).toBeVisible();
  // The unfiltered list shows the 30 newest members; search so older demo members are always found.
  await page.goto('/members?q=anna');

  const anna = page.locator('.person', { hasText: '@anna' });
  await anna.getByRole('button', { name: 'Add to circle' }).click();
  await expect(anna.getByRole('button', { name: 'In your circle' })).toBeVisible();

  await page.goto('/?tag=date-night&lat=51.2317&lng=6.7545');
  await expect(page.getByRole('link', { name: /Bar Nachtfalter/ })).toContainText('Anna');
});

test('a private member needs an introduction', async ({ page }) => {
  await joinAsNewMember(page);
  await page.goto('/m/jonas');
  await expect(page.getByRole('heading', { name: 'Private member' })).toBeVisible();
  await page.getByRole('button', { name: 'Request introduction' }).click();
  await expect(page.getByRole('button', { name: 'Introduction requested' })).toBeDisabled();
  await expect(page.getByRole('heading', { name: 'Private member' })).toBeVisible();
});

test('members can be searched', async ({ page }) => {
  await joinAsNewMember(page);
  await page.goto('/members?q=sofia');
  await expect(page.locator('.person')).toHaveCount(1);
  await expect(page.locator('.person')).toContainText('Sofia Brandt');
  await page.goto('/members?q=zzzz-nobody');
  await expect(page.getByText('No members found.')).toBeVisible();
});

test('your invitation link is shown and copyable', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  const { username } = await joinAsNewMember(page);
  await page.goto('/members');
  await expect(page.locator('.share code')).toHaveText(`http://127.0.0.1:3000/@${username}`);
  await page.getByRole('button', { name: 'Copy' }).click();
  await expect(page.getByRole('button', { name: 'Copied' })).toBeVisible();
});

test('a profile shows counts and spots', async ({ page }) => {
  await joinAsNewMember(page);
  await page.goto('/m/anna');
  await expect(page.getByRole('heading', { level: 1, name: 'Anna' })).toBeVisible();
  await expect(page.getByText('followers')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Bar Nachtfalter' })).toBeVisible();
});

test('signed-out visitors see a public profile with a join prompt', async ({ page }) => {
  await page.goto('/m/anna');
  await expect(page.getByRole('heading', { level: 1, name: 'Anna' })).toBeVisible();
  await expect(page.getByText('Join spot to add Anna to your circle.')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login?next=%2Fm%2Fanna');
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npx playwright test tests/e2e/members.spec.ts`
Expected: FAIL (`/members` and `/m/*` do not exist).

- [ ] **Step 3: Implement the follow actions and buttons**

Create `src/lib/actions/follow.ts`:

```ts
'use server';

import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';
import { errorKey } from '@/lib/errors';
import { safeNext } from '@/lib/safe-next';
import { requireMember } from '@/lib/viewer';

function done(formData: FormData, error: { code?: string; message?: string } | null): never {
  const target = new URL(safeNext(formData.get('returnTo')), 'http://spot.local');
  target.searchParams.delete('error');
  if (error) target.searchParams.set('error', errorKey(error));
  revalidatePath('/', 'layout');
  redirect(target.pathname + target.search);
}

function userId(formData: FormData): string {
  return String(formData.get('userId') ?? '');
}

export async function followMember(formData: FormData) {
  const { supabase, user } = await requireMember();
  const { error } = await supabase.from('follows').insert({ follower_id: user.id, followee_id: userId(formData) });
  done(formData, error);
}

export async function unfollowMember(formData: FormData) {
  const { supabase, user } = await requireMember();
  const { error } = await supabase.from('follows').delete().eq('follower_id', user.id).eq('followee_id', userId(formData));
  done(formData, error);
}

export async function acceptRequest(formData: FormData) {
  const { supabase, user } = await requireMember();
  const { error } = await supabase.from('follows').update({ status: 'accepted' }).eq('follower_id', userId(formData)).eq('followee_id', user.id);
  done(formData, error);
}

export async function declineRequest(formData: FormData) {
  const { supabase, user } = await requireMember();
  const { error } = await supabase.from('follows').delete().eq('follower_id', userId(formData)).eq('followee_id', user.id);
  done(formData, error);
}
```

Create `src/components/FollowButton.tsx`:

```tsx
import { followMember, unfollowMember } from '@/lib/actions/follow';

export function FollowButton({
  userId,
  isPrivate,
  status,
  returnTo,
  labels,
}: {
  userId: string;
  isPrivate: boolean;
  status: 'pending' | 'accepted' | null;
  returnTo: string;
  labels: { addToCircle: string; inCircle: string; requestIntroduction: string; introductionRequested: string };
}) {
  if (status === 'pending') {
    return <button type="button" className="btn btn--small" disabled>{labels.introductionRequested}</button>;
  }
  return (
    <form action={status === 'accepted' ? unfollowMember : followMember}>
      <input type="hidden" name="userId" value={userId} />
      <input type="hidden" name="returnTo" value={returnTo} />
      <button type="submit" className={status === 'accepted' ? 'btn btn--small' : 'btn btn--small btn--primary'}>
        {status === 'accepted' ? labels.inCircle : isPrivate ? labels.requestIntroduction : labels.addToCircle}
      </button>
    </form>
  );
}
```

Create `src/components/CopyButton.tsx`:

```tsx
'use client';

import { useState } from 'react';

export function CopyButton({ text, label, doneLabel, share = false }: { text: string; label: string; doneLabel: string; share?: boolean }) {
  const [done, setDone] = useState(false);

  async function handleClick() {
    try {
      if (share && typeof navigator.share === 'function') {
        await navigator.share({ url: text });
      } else {
        await navigator.clipboard.writeText(text);
      }
      setDone(true);
    } catch {
      // The member dismissed the share sheet or the clipboard is unavailable; nothing to report.
    }
  }

  return (
    <button type="button" className="btn btn--small" onClick={handleClick}>
      {done ? doneLabel : label}
    </button>
  );
}
```

Create `src/components/PublicShell.tsx`:

```tsx
import Link from 'next/link';

export function PublicShell({ signIn, children }: { signIn: { label: string; href: string }; children: React.ReactNode }) {
  return (
    <>
      <header className="app-header">
        <Link href="/login" className="brand">spot<span>.</span></Link>
        <Link href={signIn.href} className="link">{signIn.label}</Link>
      </header>
      <main className="page">{children}</main>
    </>
  );
}
```

- [ ] **Step 4: Implement the Members page**

Create `src/app/(app)/members/page.tsx`:

```tsx
import { Avatar } from '@/components/Avatar';
import { CopyButton } from '@/components/CopyButton';
import { FollowButton } from '@/components/FollowButton';
import { env } from '@/lib/env';
import { requireMember } from '@/lib/viewer';

export default async function MembersPage({ searchParams }: PageProps<'/members'>) {
  const sp = await searchParams;
  const { supabase, t, profile } = await requireMember();
  const q = typeof sp.q === 'string' ? sp.q.trim().slice(0, 40) : '';
  const errorParam = typeof sp.error === 'string' && sp.error in t.errors ? (sp.error as keyof typeof t.errors) : null;

  let query = supabase.from('profiles').select('id, username, display_name, is_private').neq('id', profile.id).order('created_at', { ascending: false }).limit(30);
  if (q) {
    const safe = q.replace(/[%_,()*\\]/g, '');
    query = query.or(`username.ilike.%${safe}%,display_name.ilike.%${safe}%`);
  }
  const [{ data: people }, { data: mine }] = await Promise.all([
    query,
    supabase.from('follows').select('followee_id, status').eq('follower_id', profile.id),
  ]);
  const status = new Map((mine ?? []).map((f) => [f.followee_id, f.status as 'pending' | 'accepted']));
  const invitation = `${env.siteUrl()}/@${profile.username}`;
  const returnTo = q ? `/members?q=${encodeURIComponent(q)}` : '/members';

  return (
    <>
      <h1 className="title">{t.members.title}</h1>
      {errorParam && <p className="notice notice--error" role="alert">{t.errors[errorParam]}</p>}

      <section className="field">
        <h2 className="section-title">{t.members.invitation}</h2>
        <div className="share">
          <code>{invitation}</code>
          <CopyButton text={invitation} label={t.members.copy} doneLabel={t.members.copied} />
        </div>
        <p className="hint" style={{ margin: 0 }}>{t.members.invitationHint}</p>
      </section>

      <form role="search" className="field">
        <label className="label" htmlFor="q">{t.members.search}</label>
        <input id="q" name="q" type="search" className="input" defaultValue={q} placeholder={t.members.search} />
      </form>

      {people && people.length > 0 ? (
        <ul className="list">
          {people.map((person) => (
            <li key={person.id} className="person">
              <Avatar name={person.display_name} />
              <a href={`/m/${person.username}`}>
                <span className="person-name">{person.display_name}</span>
                <span className="person-meta">@{person.username}{person.is_private ? ` · ${t.members.private}` : ''}</span>
              </a>
              <FollowButton userId={person.id} isPrivate={person.is_private} status={status.get(person.id) ?? null} returnTo={returnTo} labels={t.members} />
            </li>
          ))}
        </ul>
      ) : (
        <p className="notice">{t.members.none}</p>
      )}
    </>
  );
}
```

- [ ] **Step 5: Implement profiles**

Create `src/app/m/[username]/layout.tsx`:

```tsx
import { PublicShell } from '@/components/PublicShell';
import { Shell } from '@/components/Shell';
import { getViewer } from '@/lib/viewer';

export default async function ProfileLayout({ children, params }: LayoutProps<'/m/[username]'>) {
  const { username } = await params;
  const { profile, t } = await getViewer();
  if (profile) {
    return <Shell username={profile.username} displayName={profile.display_name} nav={t.nav}>{children}</Shell>;
  }
  return <PublicShell signIn={{ label: t.profile.signIn, href: `/login?next=${encodeURIComponent(`/m/${username}`)}` }}>{children}</PublicShell>;
}
```

Create `src/app/m/[username]/page.tsx`:

```tsx
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { Avatar } from '@/components/Avatar';
import { FollowButton } from '@/components/FollowButton';
import { getViewer } from '@/lib/viewer';

export default async function ProfilePage({ params }: PageProps<'/m/[username]'>) {
  const { username } = await params;
  const { supabase, t, profile: me } = await getViewer();

  const { data: member } = await supabase
    .from('profiles')
    .select('id, username, display_name, is_private, created_at')
    .eq('username', username.toLowerCase())
    .maybeSingle();
  if (!member) notFound();

  const own = me?.id === member.id;
  const { data: counts } = await supabase.rpc('follow_counts', { p_user_id: member.id }).single();
  const link = me && !own
    ? (await supabase.from('follows').select('status').eq('follower_id', me.id).eq('followee_id', member.id).maybeSingle()).data
    : null;
  const status = (link?.status ?? null) as 'pending' | 'accepted' | null;
  const canSee = own || !member.is_private || status === 'accepted';
  const spots = canSee
    ? (await supabase.from('recommendations').select('id, place:places(id, name)').eq('user_id', member.id).order('created_at', { ascending: false })).data ?? []
    : [];

  return (
    <>
      <div className="profile-head">
        <Avatar name={member.display_name} size="lg" />
        <div>
          <h1 className="title">{member.display_name}</h1>
          <div className="person-meta">@{member.username}{member.is_private ? ` · ${t.members.private}` : ''}</div>
          <div className="stats">
            <span><b>{counts?.followers ?? 0}</b> {t.profile.followers}</span>
            <span><b>{counts?.following ?? 0}</b> {t.profile.inCircle}</span>
          </div>
        </div>
      </div>

      {/* Task 8 inserts the membership card here. */}

      {me && !own && (
        <div className="actions">
          <FollowButton userId={member.id} isPrivate={member.is_private} status={status} returnTo={`/m/${member.username}`} labels={t.members} />
        </div>
      )}
      {own && (
        <div className="actions">
          <Link className="btn btn--small" href="/settings">{t.profile.settings}</Link>
        </div>
      )}
      {!me && <p className="notice">{t.profile.join(member.display_name)}</p>}

      {canSee ? (
        <>
          <h2 className="section-title">{own ? t.profile.yourSpots : t.profile.spots} · {spots.length}</h2>
          {spots.length > 0 ? (
            <ul className="list">
              {spots.map((spot) => (
                <li key={spot.id}>
                  <Link className="row" href={`/spots/${spot.place?.id}`}>
                    <span className="row-name">{spot.place?.name}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="notice">{t.profile.noSpots}</p>
          )}
        </>
      ) : (
        <div className="locked">
          <h2>{t.profile.lockedTitle}</h2>
          <p>{t.profile.lockedBody}</p>
        </div>
      )}
    </>
  );
}
```

Note: `/m/<username>` links to `/spots/<id>`, which is members-only. A signed-out visitor who follows the link goes through sign-in and comes back via `next`.

- [ ] **Step 6: Run tests**

```bash
npm run typecheck
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npm run test:e2e
```

Expected: all e2e specs pass.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(app): members, circles, introductions and profiles"
```

---

### Task 8: Membership card and invitation links

**Files:**
- Create: `src/components/MembershipCard.tsx`, `src/app/i/[id]/route.ts`, `tests/e2e/card.spec.ts`
- Modify: `next.config.ts`, `src/app/m/[username]/page.tsx` (insert the card and a share button)

**Interfaces:**
- Consumes: `env.siteUrl`, `formatMemberSince`, `CopyButton`, `profiles`.
- Produces:
  - `<MembershipCard member={{ id, username, display_name, created_at }} labels locale />`: a black card showing name, handle, "Member since MM/YYYY" and a scannable QR code for `${siteUrl}/i/<id>`.
  - `/i/<id>` redirects to `/m/<current username>`, or to `/` if the id is unknown.
  - `/@<username>` is rewritten to `/m/<username>`.

- [ ] **Step 1: Write the failing e2e test**

Create `tests/e2e/card.spec.ts`:

```ts
import { expect, test } from '@playwright/test';
import { admin, joinAsNewMember } from './helpers';

test('your profile shows your membership card with a QR code and a share button', async ({ page }) => {
  const { username } = await joinAsNewMember(page, 'Carla Card');
  await page.getByRole('link', { name: 'Profile' }).click();
  await expect(page).toHaveURL(new RegExp(`/m/${username}$`));

  const card = page.getByRole('group', { name: 'Membership' });
  await expect(card).toContainText('Carla Card');
  await expect(card).toContainText(`@${username}`);
  await expect(card).toContainText(/Member since\s*\d{2}\/\d{4}/);
  await expect(card.getByRole('img', { name: 'QR code that opens this profile' }).locator('svg')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Share card' })).toBeVisible();
});

test('invitation links open the member’s profile', async ({ page }) => {
  await page.goto('/@anna');
  await expect(page.getByRole('heading', { level: 1, name: 'Anna' })).toBeVisible();

  const { data } = await admin().from('profiles').select('id').eq('username', 'anna').single();
  await page.goto(`/i/${data!.id}`);
  await expect(page).toHaveURL(/\/m\/anna$/);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npx playwright test tests/e2e/card.spec.ts`
Expected: FAIL (no card; `/@anna` and `/i/…` are 404).

- [ ] **Step 3: Implement**

Create `src/components/MembershipCard.tsx`:

```tsx
import QRCode from 'qrcode';
import type { Locale, Messages } from '@/i18n';
import { env } from '@/lib/env';
import { formatMemberSince } from '@/lib/format';

export async function MembershipCard({
  member,
  labels,
  locale,
}: {
  member: { id: string; username: string; display_name: string; created_at: string };
  labels: Messages['card'];
  locale: Locale;
}) {
  // The QR code carries the member id, not the username: usernames can change (spec §10).
  const svg = await QRCode.toString(`${env.siteUrl()}/i/${member.id}`, {
    type: 'svg',
    margin: 0,
    errorCorrectionLevel: 'M',
    color: { dark: '#0b0b0cff', light: '#ffffffff' },
  });

  return (
    <div className="card" role="group" aria-label={labels.membership}>
      <div className="card-brand">spot<span>.</span></div>
      <div className="card-type">{labels.membership}</div>
      <div className="card-name">{member.display_name}</div>
      <div className="card-meta">
        <span>@{member.username}</span>
        <span>{labels.memberSince} <b>{formatMemberSince(member.created_at, locale)}</b></span>
      </div>
      <div className="card-qr" role="img" aria-label={labels.qr} dangerouslySetInnerHTML={{ __html: svg }} />
    </div>
  );
}
```

In `src/app/m/[username]/page.tsx`:
- Read `locale` from `getViewer()`.
- Import `MembershipCard`, `CopyButton` and `env`.
- Replace the comment `{/* Task 8 inserts the membership card here. */}` with:

```tsx
<MembershipCard member={member} labels={t.card} locale={locale} />
```

and in the `own` actions block, add before the Settings link:

```tsx
<CopyButton text={`${env.siteUrl()}/@${member.username}`} label={t.card.share} doneLabel={t.card.shared} share />
```

Create `src/app/i/[id]/route.ts`:

```ts
import { NextResponse, type NextRequest } from 'next/server';
import { createClient } from '@/lib/supabase/server';

// QR codes on membership cards point here with the member id; usernames can change.
export async function GET(request: NextRequest, context: RouteContext<'/i/[id]'>) {
  const { id } = await context.params;
  const supabase = await createClient();
  const { data } = await supabase.from('profiles').select('username').eq('id', id).maybeSingle();
  return NextResponse.redirect(new URL(data ? `/m/${data.username}` : '/', request.url));
}
```

Replace `next.config.ts`:

```ts
import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: '/@:username', destination: '/m/:username' }];
  },
};

export default nextConfig;
```

If `RouteContext` is not a global type in this Next.js version, check `node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/route.md` and use the documented signature.

- [ ] **Step 4: Run tests**

```bash
npm run typecheck
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npm run test:e2e
```

Expected: all e2e specs pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(app): membership card with QR invitation and /@username links"
```

---

### Task 9: Settings: language, privacy, introduction requests, sign out, delete account

**Files:**
- Create: `src/lib/supabase/admin.ts`, `src/lib/actions/settings.ts`, `src/app/(app)/settings/page.tsx`, `tests/e2e/settings.spec.ts`

**Interfaces:**
- Consumes: `requireMember`, `acceptRequest`/`declineRequest` (Task 7), `serverEnv.secretKey`, `env.supabaseUrl`.
- Produces:
  - `createAdminClient()` (server only)
  - Server actions:
    - `setLanguage(formData: locale)`: updates `profiles.locale` and sets the `locale` cookie for 1 year
    - `setPrivate(formData: value 'true'|'false')`
    - `signOut()`
    - `deleteAccount()`: deletes the auth user via the admin API, which cascades in the database, signs out, and redirects to `/login?deleted=1`
  - `/settings`, with `?confirm=delete` showing the confirmation step

- [ ] **Step 1: Write the failing e2e test**

Create `tests/e2e/settings.spec.ts`:

```ts
import { expect, test } from '@playwright/test';
import { admin, joinAsNewMember, newMemberPage } from './helpers';

test('switching the language to German', async ({ page }) => {
  const { username } = await joinAsNewMember(page);
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Deutsch' }).click();
  await expect(page.getByRole('heading', { name: 'Einstellungen' })).toBeVisible();
  await expect(page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Jetzt' })).toBeVisible();
  await page.goto(`/m/${username}`);
  await expect(page.getByText('Mitglied seit')).toBeVisible();
  await page.goto('/settings');
  await page.getByRole('button', { name: 'English' }).click();
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible();
});

test('a private member accepts an introduction request', async ({ page, browser }) => {
  const host = await joinAsNewMember(page, 'Paula Private');
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Private membership: Off' }).click();
  await expect(page.getByRole('button', { name: 'Private membership: On' })).toBeVisible();

  const guestPage = await newMemberPage(browser);
  await joinAsNewMember(guestPage, 'Gustav Guest');
  await guestPage.goto(`/m/${host.username}`);
  await guestPage.getByRole('button', { name: 'Request introduction' }).click();
  await expect(guestPage.getByRole('button', { name: 'Introduction requested' })).toBeDisabled();

  await page.goto('/settings');
  const request = page.locator('.person', { hasText: 'Gustav Guest' });
  await request.getByRole('button', { name: 'Accept' }).click();
  await expect(page.getByText('No open requests.')).toBeVisible();

  await guestPage.goto(`/m/${host.username}`);
  await expect(guestPage.getByRole('button', { name: 'In your circle' })).toBeVisible();
  await expect(guestPage.getByRole('heading', { name: 'Private member' })).toHaveCount(0);
});

test('signing out', async ({ page }) => {
  await joinAsNewMember(page);
  await page.goto('/settings');
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/login/);
  await page.goto('/members');
  await expect(page).toHaveURL(/\/login/);
});

test('deleting the account removes the member', async ({ page }) => {
  const { username } = await joinAsNewMember(page);
  await page.goto('/settings');
  await page.getByRole('link', { name: 'Delete account' }).click();
  await expect(page.getByText('This permanently deletes your profile, your circle and your spots.')).toBeVisible();
  await page.getByRole('button', { name: 'Delete permanently' }).click();
  await expect(page).toHaveURL(/\/login\?deleted=1/);
  await expect(page.getByText('Your account has been deleted.')).toBeVisible();

  const { data } = await admin().from('profiles').select('id').eq('username', username);
  expect(data).toEqual([]);
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npx playwright test tests/e2e/settings.spec.ts`
Expected: FAIL (`/settings` does not exist).

- [ ] **Step 3: Implement**

Create `src/lib/supabase/admin.ts`:

```ts
import 'server-only';
import { createClient } from '@supabase/supabase-js';
import { env, serverEnv } from '@/lib/env';
import type { Database } from './database.types';

// Bypasses RLS. Use only for actions the member cannot perform on their own rows (account deletion).
export function createAdminClient() {
  return createClient<Database>(env.supabaseUrl(), serverEnv.secretKey(), { auth: { persistSession: false } });
}
```

Create `src/lib/actions/settings.ts`:

```ts
'use server';

import { revalidatePath } from 'next/cache';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { isLocale } from '@/i18n';
import { createAdminClient } from '@/lib/supabase/admin';
import { requireMember } from '@/lib/viewer';

export async function setLanguage(formData: FormData) {
  const locale = formData.get('locale');
  if (!isLocale(locale)) redirect('/settings');
  const { supabase, user } = await requireMember();
  await supabase.from('profiles').update({ locale }).eq('id', user.id);
  (await cookies()).set('locale', locale, { path: '/', maxAge: 60 * 60 * 24 * 365, sameSite: 'lax' });
  revalidatePath('/', 'layout');
  redirect('/settings');
}

export async function setPrivate(formData: FormData) {
  const { supabase, user } = await requireMember();
  await supabase.from('profiles').update({ is_private: formData.get('value') === 'true' }).eq('id', user.id);
  revalidatePath('/', 'layout');
  redirect('/settings');
}

export async function signOut() {
  const { supabase } = await requireMember();
  await supabase.auth.signOut();
  redirect('/login');
}

export async function deleteAccount() {
  const { supabase, user } = await requireMember();
  // Deleting the auth user cascades to profile, circle, spots and filed reports (Plan 1).
  const { error } = await createAdminClient().auth.admin.deleteUser(user.id);
  if (error) redirect('/settings?error=generic');
  await supabase.auth.signOut({ scope: 'local' });
  redirect('/login?deleted=1');
}
```

Create `src/app/(app)/settings/page.tsx`:

```tsx
import Link from 'next/link';
import { Avatar } from '@/components/Avatar';
import { acceptRequest, declineRequest } from '@/lib/actions/follow';
import { deleteAccount, setLanguage, setPrivate, signOut } from '@/lib/actions/settings';
import { requireMember } from '@/lib/viewer';

export default async function SettingsPage({ searchParams }: PageProps<'/settings'>) {
  const sp = await searchParams;
  const { supabase, t, profile, locale } = await requireMember();
  const { data: requests } = await supabase
    .from('follows')
    .select('follower:profiles!follows_follower_id_fkey(id, username, display_name)')
    .eq('followee_id', profile.id)
    .eq('status', 'pending');
  const confirmDelete = sp.confirm === 'delete';
  const privateState = `${t.settings.privateLabel}: ${profile.is_private ? t.settings.on : t.settings.off}`;

  return (
    <>
      <h1 className="title">{t.settings.title}</h1>
      {sp.error === 'generic' && <p className="notice notice--error" role="alert">{t.errors.generic}</p>}

      <section>
        <div className="setting">
          <span>{t.settings.language}</span>
          <form action={setLanguage} className="segmented">
            <button type="submit" name="locale" value="de" aria-pressed={locale === 'de'}>Deutsch</button>
            <button type="submit" name="locale" value="en" aria-pressed={locale === 'en'}>English</button>
          </form>
        </div>
        <div className="setting">
          <div>
            <span>{t.settings.privateLabel}</span>
            <small>{t.settings.privateHint}</small>
          </div>
          <form action={setPrivate}>
            <input type="hidden" name="value" value={String(!profile.is_private)} />
            <button type="submit" className="btn btn--small" aria-label={privateState}>
              {profile.is_private ? t.settings.on : t.settings.off}
            </button>
          </form>
        </div>
      </section>

      <section className="field">
        <h2 className="section-title">{t.settings.requests}</h2>
        {requests && requests.length > 0 ? (
          <ul className="list">
            {requests.map(({ follower }) => follower && (
              <li key={follower.id} className="person">
                <Avatar name={follower.display_name} />
                <Link href={`/m/${follower.username}`}>
                  <span className="person-name">{follower.display_name}</span>
                  <span className="person-meta">@{follower.username}</span>
                </Link>
                <div className="actions">
                  <form action={acceptRequest}>
                    <input type="hidden" name="userId" value={follower.id} />
                    <input type="hidden" name="returnTo" value="/settings" />
                    <button type="submit" className="btn btn--small btn--primary">{t.settings.accept}</button>
                  </form>
                  <form action={declineRequest}>
                    <input type="hidden" name="userId" value={follower.id} />
                    <input type="hidden" name="returnTo" value="/settings" />
                    <button type="submit" className="btn btn--small">{t.settings.decline}</button>
                  </form>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="notice">{t.settings.noRequests}</p>
        )}
      </section>

      <section className="actions">
        <form action={signOut}>
          <button type="submit" className="btn">{t.settings.signOut}</button>
        </form>
        {!confirmDelete && <Link className="btn btn--danger" href="/settings?confirm=delete">{t.settings.deleteAccount}</Link>}
      </section>

      {confirmDelete && (
        <section className="empty">
          <p>{t.settings.deleteWarning}</p>
          <div className="actions">
            <form action={deleteAccount}>
              <button type="submit" className="btn btn--primary">{t.settings.deleteConfirm}</button>
            </form>
            <Link className="btn" href="/settings">{t.settings.cancel}</Link>
          </div>
        </section>
      )}
    </>
  );
}
```

If PostgREST names the follows→profiles foreign key differently, run:

```sql
select conname from pg_constraint where conrelid = 'public.follows'::regclass and contype = 'f';
```

against the local DB and use that name in the embed. Record it in the report.

- [ ] **Step 4: Run tests**

```bash
npm test && npm run typecheck
PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npm run test:e2e
```

Expected: all unit and e2e tests pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(app): settings with language, privacy, introductions, sign out and account deletion"
```

---

### Task 10: CI for the app: lint, typecheck, unit and e2e

**Files:**
- Modify: `.github/workflows/db-tests.yml`

**Interfaces:**
- Consumes: every npm script above, and `scripts/env-local.sh`.
- Produces: two more jobs in the `Database tests` workflow:
  - `app`: lint, typecheck, unit tests and build
  - `e2e`: local stack with Mailpit, demo data, production build, Playwright

- [ ] **Step 1: Add the jobs**

Append to `.github/workflows/db-tests.yml` under `jobs:` (keep the existing `db` job unchanged):

```yaml
  app:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
      - run: npm test
      - run: npm run build
        env:
          NEXT_PUBLIC_SUPABASE_URL: http://127.0.0.1:54321
          NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: build-only-placeholder

  e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: npm
      - run: npm ci
      - run: npx supabase start -x studio,edge-runtime,logflare,vector,imgproxy
      - run: bash scripts/env-local.sh
      - run: npx playwright install --with-deps chromium
      - run: npm run build
      - run: npm run test:e2e
        env:
          CI: 'true'
      - uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-report
          path: |
            playwright-report
            test-results
          retention-days: 7
```

- [ ] **Step 2: Verify locally what CI will run**

```bash
npm run lint && npm run typecheck && npm test && npm run build
CI=true PLAYWRIGHT_CHROMIUM_EXECUTABLE=/opt/pw-browsers/chromium-1194/chrome-linux/chrome npm run test:e2e
```

Expected: everything passes. With `CI=true`, Playwright starts `npm run start` against the fresh build.

Add `playwright-report/` and `test-results/` to `.gitignore` if not already ignored.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "ci: lint, typecheck, unit and end-to-end tests for the app"
```

- [ ] **Step 4: Verify CI (controller)**

The controller pushes and confirms all three jobs pass on GitHub: `db`, `app`, `e2e`.
