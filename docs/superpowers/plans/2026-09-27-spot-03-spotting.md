# Spot — Plan 3: Spotting Places — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Members can spot a place: open the new Spot tab (＋), search a place (Google Places, or a local fake), pick 1–3 moods, write a note, add up to two "Known for" entries, and later edit, delete or report spots.

**Architecture:** One new migration adds `known_for` plus two functions: `save_spot()` writes a spot and its Known-for entries atomically, and `known_for_counts()` aggregates visible entries. `src/lib/places/` is the only code that talks to Google, behind a `PlacesProvider` interface with a fake for local development, tests and CI. Places rows are written only server-side (admin client) after the provider confirms the place, so clients can never forge a place. A cron route refreshes cached place fields every 30 days (Google ToS).

**Tech Stack:** Next.js 16.3.6 (App Router, server actions), Supabase (Postgres + PostGIS, RLS, pgTAP), Google Places API (New), Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-09-27-spot-recommendations-app-design.md` (§2 places/recommendations/reports, §5.2–5.3, §6 `places/`, §7, §10 "Known for" and notes for later plans). Repo: `richardspinnen/spot` (`/home/user/spot`), branch `main`.

## Global Constraints

- Node 22; zero new npm dependencies.
- Next.js 16 rules: `params`/`searchParams`/`cookies()` are async; use the global `PageProps<'/route'>` types; `npm run typecheck` runs `next typegen` first.
- All UI strings live in `src/i18n/en.ts` and `src/i18n/de.ts` with identical keys (a test enforces parity). Wording: noun "spot", verb "Spot this place" / "Als Spot markieren", "Spotted by" / "Entdeckt von", "Known for" / "Bekannt für". Never "gespottet".
- Look: black/white/greys only, existing tokens and classes in `src/app/globals.css`; one primary action per screen.
- Google API key is server-only (`GOOGLE_PLACES_API_KEY`, never `NEXT_PUBLIC_`). Production never silently falls back to fake data.
- Only `google_place_id` is permanent; `name`, `address`, `location` are a cache refreshed at most every 30 days. Places are closed, never deleted.
- Known for: optional, up to 2 entries per member per place, each 1–40 characters, same visibility as the spot it belongs to.
- DB functions: `security definer` only when needed, always `set search_path = ''`; revoke `execute` from `public`/`anon` where members-only.
- Route handlers and server actions check auth themselves (`requireMember()` or an explicit check).
- Every commit message ends with the two trailer lines given in the task brief.
- Run before every commit: `npm run lint && npm run typecheck && npm test`. DB tasks also `npm run test:db`; UI tasks also the e2e specs they touch.

## File Structure

| File | Responsibility |
|---|---|
| `supabase/migrations/20260927000010_known_for.sql` | `known_for` table, RLS, `save_spot()`, `known_for_counts()` |
| `supabase/tests/09_known_for.test.sql` | pgTAP for the above |
| `src/lib/places/types.ts` | `PlacesProvider` interface, `PlaceSuggestion`, `PlaceDetails`, `PlacesUnavailableError`, `isGooglePlaceId` |
| `src/lib/places/fake.ts` | In-memory provider (Düsseldorf demo places + 4 unspotted ones) |
| `src/lib/places/google.ts` | Google Places API (New) provider, `fetch` injected |
| `src/lib/places/cache.ts` | Short TTL memo wrapper for a provider |
| `src/lib/places/index.ts` | `placesProvider()` selection by env (server-only) |
| `src/lib/places/store.ts` | `lookupPlace()` / `ensurePlace()` — DB cache in front of the provider (server-only) |
| `src/lib/places/refresh.ts` | `refreshPlace()` — pure decision for the refresh job |
| `src/lib/spot-form.ts` | `parseSpotForm()` — pure form parsing/validation |
| `src/lib/errors.ts` | per-table `errorKey` mapping (modify) |
| `src/lib/actions/spot.ts` | `saveSpot`, `deleteSpot`, `reportSpot` server actions |
| `src/app/api/places/autocomplete/route.ts` | Autocomplete JSON for the search box |
| `src/app/api/cron/refresh-places/route.ts` | Refresh job endpoint (Bearer `CRON_SECRET`) |
| `src/app/(app)/spot/page.tsx` | Spot tab: search, then the spot form |
| `src/components/PlaceSearch.tsx` | Client search box |
| `src/components/TabBar.tsx`, `Icons.tsx` | Third tab with a plus icon (modify) |
| `src/app/(app)/spots/[id]/page.tsx` | Known for, closed label, spot/edit button, report (modify) |
| `src/app/(app)/page.tsx` | Top Known-for entry on Now rows (modify) |
| `tests/e2e/spotting.spec.ts` | End-to-end spotting flows |
| `vercel.json`, `README.md`, `scripts/env-local.sh` | Cron schedule, docs, `PLACES_PROVIDER=fake` locally/CI |

---

### Task 1: Known-for table and save_spot / known_for_counts functions

**Files:**
- Create: `supabase/migrations/20260927000010_known_for.sql`
- Create: `supabase/tests/09_known_for.test.sql`
- Modify: `src/lib/supabase/database.types.ts` (regenerate with `npm run types:db`)

**Interfaces:**
- Consumes: `public.recommendations` (RLS via `can_see_picks_of`), test helpers `tests.create_user`, `tests.user_id`, `tests.create_place`, `tests.place_id`, `tests.authenticate_as`, `tests.as_anon`.
- Produces:
  - `public.save_spot(p_place_id uuid, p_tags text[], p_note text, p_known_for text[]) returns uuid` (the recommendation id). Raises `not_signed_in`, `invalid_known_for`; the existing trigger still raises `invalid_tags`, `rate_limited`; note > 500 chars violates `recommendations_note_check` (23514).
  - `public.known_for_counts(p_place_ids uuid[]) returns table(place_id uuid, label text, members bigint)`, ordered by place, `members desc`, `label`. Only entries on spots visible to the caller.

- [ ] **Step 1: Write the failing pgTAP test** `supabase/tests/09_known_for.test.sql`:

```sql
begin;
create extension if not exists pgtap with schema extensions;
select plan(16);

do $$
begin
  perform tests.create_user('ann');
  perform tests.create_user('ben');
  perform tests.create_user('cat', true);
  perform tests.create_user('dan');
  perform tests.create_user('eve');
  perform tests.create_place('g-1', 'One', 51.23, 6.75);
  perform tests.create_place('g-2', 'Two', 51.24, 6.75);
end;
$$;

select tests.authenticate_as(tests.user_id('ann'));
select lives_ok(
  $$ select public.save_spot(tests.place_id('g-1'), array['date-night'], '  Corner table  ', array['Truffle pasta', ' truffle   PASTA ']) $$,
  'save_spot creates a spot'
);
select is((select note from public.recommendations where user_id = tests.user_id('ann')), 'Corner table', 'note is trimmed');
select is((select count(*)::int from public.known_for), 1, 'case-insensitive duplicates collapse, whitespace is normalized');

select lives_ok(
  $$ select public.save_spot(tests.place_id('g-1'), array['wine'], '', array['Tiramisu']) $$,
  'saving again edits the same spot'
);
select is((select count(*)::int from public.recommendations where user_id = tests.user_id('ann')), 1, 'still one spot per member and place');
select is((select note from public.recommendations where user_id = tests.user_id('ann')), null, 'empty note becomes null');
select is((select array_agg(label) from public.known_for), array['Tiramisu'], 'known-for entries are replaced');

select throws_ok(
  $$ select public.save_spot(tests.place_id('g-2'), array['wine'], null, array['a', 'b', 'c']) $$,
  'P0001', 'invalid_known_for', 'at most two entries'
);
select throws_ok(
  $$ select public.save_spot(tests.place_id('g-2'), array['wine'], null, array[repeat('x', 41)]) $$,
  'P0001', 'invalid_known_for', 'entries are at most 40 characters'
);
select throws_ok(
  $$ insert into public.known_for (recommendation_id, label) select id, 'Sneaky' from public.recommendations limit 1 $$,
  '42501', null, 'members cannot write known_for directly'
);

-- ben writes it lowercase; eve and private cat agree with ann's spelling
select tests.authenticate_as(tests.user_id('ben'));
select public.save_spot(tests.place_id('g-1'), array['wine'], null, array['tiramisu']);
select tests.authenticate_as(tests.user_id('eve'));
select public.save_spot(tests.place_id('g-1'), array['wine'], null, array['Tiramisu']);
select tests.authenticate_as(tests.user_id('cat'));
select public.save_spot(tests.place_id('g-1'), array['wine'], null, array['Tiramisu', 'Negroni']);

select tests.authenticate_as(tests.user_id('dan'));
select results_eq(
  $$ select label, members from public.known_for_counts(array[tests.place_id('g-1')]) $$,
  $$ values ('Tiramisu'::text, 3::bigint) $$,
  'strangers count only public spots, case-insensitively, showing the most common spelling'
);
select tests.authenticate_as(tests.user_id('cat'));
select results_eq(
  $$ select label, members from public.known_for_counts(array[tests.place_id('g-1')]) $$,
  $$ values ('Tiramisu'::text, 4::bigint), ('Negroni'::text, 1::bigint) $$,
  'the author sees their own entries'
);

select tests.as_anon();
select throws_ok(
  $$ select public.save_spot(tests.place_id('g-1'), array['wine'], null, null) $$,
  '42501', null, 'anon cannot call save_spot'
);

reset role;
delete from public.recommendations where user_id = tests.user_id('cat');
select is((select count(*)::int from public.known_for where label = 'Negroni'), 0, 'deleting a spot deletes its known-for entries');

select tests.authenticate_as(tests.user_id('dan'));
select throws_ok(
  $$ select public.save_spot(tests.place_id('g-2'), array['wine'], repeat('x', 501), null) $$,
  '23514', null, 'note longer than 500 characters is rejected'
);
select lives_ok(
  $$ select public.save_spot(tests.place_id('g-2'), array['wine'], null, null) $$,
  'known-for is optional'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run it and see it fail**

Run: `npm run test:db`
Expected: `09_known_for.test.sql` fails (`function public.save_spot does not exist`); files 01–08 still pass.

- [ ] **Step 3: Write the migration** `supabase/migrations/20260927000010_known_for.sql`:

```sql
-- "Known for": what a member says a place is known for, attached to their
-- spot so it shares the spot's visibility and disappears with it.
create table public.known_for (
  recommendation_id uuid not null references public.recommendations (id) on delete cascade,
  label text not null check (char_length(label) between 1 and 40),
  created_at timestamptz not null default now(),
  primary key (recommendation_id, label)
);

create unique index known_for_label_ci_idx on public.known_for (recommendation_id, lower(label));

alter table public.known_for enable row level security;

-- The subquery runs under recommendations' RLS, so an entry is visible
-- exactly when its spot is.
create policy "known-for entries are visible with their spot"
  on public.known_for for select
  to anon, authenticated
  using (exists (select 1 from public.recommendations r where r.id = recommendation_id));

-- Writes go through save_spot() only.
revoke insert, update, delete on public.known_for from anon, authenticated;

-- Writes a member's spot and its known-for entries in one transaction.
create function public.save_spot(p_place_id uuid, p_tags text[], p_note text, p_known_for text[])
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_user uuid := auth.uid();
  v_note text := nullif(btrim(p_note), '');
  v_labels text[];
  v_id uuid;
begin
  if v_user is null then
    raise exception 'not_signed_in';
  end if;

  -- Trim, collapse inner whitespace, drop empties, de-duplicate ignoring case
  -- (first spelling wins).
  select coalesce(array_agg(label order by first_pos), '{}')
    into v_labels
  from (
    select distinct on (lower(label)) label, pos as first_pos
    from (
      select regexp_replace(btrim(raw), '\s+', ' ', 'g') as label, pos
      from unnest(coalesce(p_known_for, '{}')) with ordinality as t(raw, pos)
    ) cleaned
    where label <> ''
    order by lower(label), pos
  ) deduped;

  if cardinality(v_labels) > 2
     or exists (select 1 from unnest(v_labels) l where char_length(l) > 40) then
    raise exception 'invalid_known_for';
  end if;

  insert into public.recommendations (user_id, place_id, tags, note)
  values (v_user, p_place_id, p_tags, v_note)
  on conflict (user_id, place_id)
    do update set tags = excluded.tags, note = excluded.note
  returning id into v_id;

  delete from public.known_for where recommendation_id = v_id;
  insert into public.known_for (recommendation_id, label)
  select v_id, l from unnest(v_labels) l;

  return v_id;
end;
$$;

revoke execute on function public.save_spot(uuid, text[], text, text[]) from public, anon;
grant execute on function public.save_spot(uuid, text[], text, text[]) to authenticated;

-- Known-for entries per place, counted over the spots the caller may see.
create function public.known_for_counts(p_place_ids uuid[])
returns table (place_id uuid, label text, members bigint)
language sql
stable
security invoker
set search_path = ''
as $$
  select r.place_id, mode() within group (order by k.label) as label, count(distinct r.user_id) as members
  from public.known_for k
  join public.recommendations r on r.id = k.recommendation_id
  where r.place_id = any (p_place_ids)
  group by r.place_id, lower(k.label)
  order by r.place_id, members desc, label;
$$;

revoke execute on function public.known_for_counts(uuid[]) from public, anon;
grant execute on function public.known_for_counts(uuid[]) to authenticated;
```

`mode()` shows the most common spelling of an entry ("Tiramisu" ×3 beats "tiramisu" ×1); the tests never rely on how a tie is broken.

- [ ] **Step 4: Run the DB tests**

Run: `npm run test:db`
Expected: all files pass, including 16 new assertions.

- [ ] **Step 5: Regenerate types and check**

Run: `npm run types:db && npm run typecheck`
Expected: `database.types.ts` gains `known_for`, `save_spot`, `known_for_counts`; typecheck passes.

- [ ] **Step 6: Commit**

```bash
git add supabase/migrations/20260927000010_known_for.sql supabase/tests/09_known_for.test.sql src/lib/supabase/database.types.ts
git commit -m "feat(db): known-for entries, atomic save_spot and known_for_counts"
```

---

### Task 2: Places module (provider interface, fake, Google, cache)

**Files:**
- Create: `src/lib/places/types.ts`, `fake.ts`, `google.ts`, `cache.ts`, `index.ts`
- Test: `src/lib/places/fake.test.ts`, `google.test.ts`, `cache.test.ts`, `index.test.ts`

**Interfaces:**
- Produces:

```ts
// types.ts
export type Locale = 'de' | 'en';
export type LatLng = { lat: number; lng: number };
export type PlaceSuggestion = { placeId: string; name: string; secondary: string };
export type PlaceDetails = { placeId: string; name: string; address: string; lat: number; lng: number; closed: boolean };
export interface PlacesProvider {
  autocomplete(input: string, opts: { near: LatLng; locale: Locale; sessionToken: string }): Promise<PlaceSuggestion[]>;
  details(placeId: string, opts: { locale: Locale; sessionToken?: string }): Promise<PlaceDetails | null>; // null = no such place
}
export class PlacesUnavailableError extends Error {}
export function isGooglePlaceId(value: unknown): value is string; // /^[A-Za-z0-9_-]{1,300}$/
// fake.ts
export const FAKE_PLACES: PlaceDetails[];
export const fakePlaces: PlacesProvider;
// google.ts
export function googlePlaces(apiKey: string, fetchImpl?: typeof fetch): PlacesProvider;
// cache.ts
export function withCache(provider: PlacesProvider, ttlMs?: number, now?: () => number): PlacesProvider;
// index.ts (server-only)
export function placesProvider(): PlacesProvider;
```

- [ ] **Step 1: Write the failing tests**

`src/lib/places/fake.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { fakePlaces, FAKE_PLACES } from './fake';

const near = { lat: 51.2317, lng: 6.7545 };

describe('fakePlaces', () => {
  it('finds places by a case-insensitive part of the name, nearest first, at most 5', async () => {
    const results = await fakePlaces.autocomplete('ENZO', { near, locale: 'en', sessionToken: 't' });
    expect(results).toEqual([{ placeId: 'fake-enzo', name: 'Trattoria Da Enzo', secondary: 'Luegallee, Düsseldorf' }]);
    const many = await fakePlaces.autocomplete('e', { near, locale: 'en', sessionToken: 't' });
    expect(many.length).toBe(5);
  });
  it('contains every demo place with the demo ids', () => {
    for (let i = 1; i <= 12; i++) expect(FAKE_PLACES.some((p) => p.placeId === `demo-p${i}`)).toBe(true);
  });
  it('returns details or null', async () => {
    expect((await fakePlaces.details('demo-p1', { locale: 'en' }))?.name).toBe('Bar Nachtfalter');
    expect(await fakePlaces.details('nope', { locale: 'en' })).toBeNull();
  });
});
```

`src/lib/places/google.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest';
import { googlePlaces } from './google';
import { PlacesUnavailableError } from './types';

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } });

describe('googlePlaces', () => {
  it('calls Places (New) autocomplete with a location bias and maps suggestions', async () => {
    const fetchImpl = vi.fn(async () =>
      json({ suggestions: [{ placePrediction: { placeId: 'ChIJ1', structuredFormat: { mainText: { text: 'Da Enzo' }, secondaryText: { text: 'Luegallee' } } } }, { queryPrediction: {} }] }),
    );
    const results = await googlePlaces('KEY', fetchImpl).autocomplete('enzo', { near: { lat: 51.2, lng: 6.7 }, locale: 'de', sessionToken: 's1' });
    expect(results).toEqual([{ placeId: 'ChIJ1', name: 'Da Enzo', secondary: 'Luegallee' }]);
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://places.googleapis.com/v1/places:autocomplete');
    expect((init.headers as Record<string, string>)['X-Goog-Api-Key']).toBe('KEY');
    expect(JSON.parse(String(init.body))).toMatchObject({
      input: 'enzo',
      languageCode: 'de',
      sessionToken: 's1',
      locationBias: { circle: { center: { latitude: 51.2, longitude: 6.7 }, radius: 20000 } },
      includedPrimaryTypes: ['restaurant', 'bar', 'cafe', 'night_club'],
    });
  });

  it('fetches details with a field mask and maps closed places', async () => {
    const fetchImpl = vi.fn(async () =>
      json({ id: 'ChIJ1', displayName: { text: 'Da Enzo' }, formattedAddress: 'Luegallee 1, Düsseldorf', location: { latitude: 51.2, longitude: 6.7 }, businessStatus: 'CLOSED_PERMANENTLY' }),
    );
    const place = await googlePlaces('KEY', fetchImpl).details('ChIJ1', { locale: 'en', sessionToken: 's1' });
    expect(place).toEqual({ placeId: 'ChIJ1', name: 'Da Enzo', address: 'Luegallee 1, Düsseldorf', lat: 51.2, lng: 6.7, closed: true });
    const [url, init] = fetchImpl.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('https://places.googleapis.com/v1/places/ChIJ1?languageCode=en&sessionToken=s1');
    expect((init.headers as Record<string, string>)['X-Goog-FieldMask']).toBe('id,displayName,formattedAddress,location,businessStatus');
  });

  it('returns null for unknown places and never builds a URL from an invalid id', async () => {
    const fetchImpl = vi.fn(async () => json({ error: {} }, 404));
    expect(await googlePlaces('KEY', fetchImpl).details('ChIJgone', { locale: 'en' })).toBeNull();
    expect(await googlePlaces('KEY', fetchImpl).details('../../x?y', { locale: 'en' })).toBeNull();
    expect(fetchImpl).toHaveBeenCalledTimes(1);
  });

  it('turns outages into PlacesUnavailableError', async () => {
    const down = googlePlaces('KEY', vi.fn(async () => json({}, 429)));
    await expect(down.autocomplete('x', { near: { lat: 0, lng: 0 }, locale: 'en', sessionToken: 's' })).rejects.toBeInstanceOf(PlacesUnavailableError);
    const offline = googlePlaces('KEY', vi.fn(async () => { throw new TypeError('fetch failed'); }));
    await expect(offline.details('ChIJ1', { locale: 'en' })).rejects.toBeInstanceOf(PlacesUnavailableError);
  });
});
```

`src/lib/places/cache.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest';
import { withCache } from './cache';
import type { PlacesProvider } from './types';

describe('withCache', () => {
  it('reuses results within the TTL, ignoring the session token', async () => {
    let t = 0;
    const inner: PlacesProvider = { autocomplete: vi.fn(async () => []), details: vi.fn(async () => null) };
    const cached = withCache(inner, 1000, () => t);
    const near = { lat: 1, lng: 2 };
    await cached.autocomplete('enzo', { near, locale: 'en', sessionToken: 'a' });
    await cached.autocomplete('enzo', { near, locale: 'en', sessionToken: 'b' });
    expect(inner.autocomplete).toHaveBeenCalledTimes(1);
    t = 1001;
    await cached.autocomplete('enzo', { near, locale: 'en', sessionToken: 'c' });
    expect(inner.autocomplete).toHaveBeenCalledTimes(2);
    await cached.details('x', { locale: 'en' });
    await cached.details('x', { locale: 'de' });
    expect(inner.details).toHaveBeenCalledTimes(2);
  });
  it('does not cache failures', async () => {
    const inner: PlacesProvider = { autocomplete: vi.fn().mockRejectedValueOnce(new Error('down')).mockResolvedValue([]), details: vi.fn() };
    const cached = withCache(inner);
    const opts = { near: { lat: 1, lng: 2 }, locale: 'en' as const, sessionToken: 's' };
    await expect(cached.autocomplete('a', opts)).rejects.toThrow('down');
    await expect(cached.autocomplete('a', opts)).resolves.toEqual([]);
  });
});
```

`src/lib/places/index.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('server-only', () => ({}));

afterEach(() => vi.unstubAllEnvs());

describe('placesProvider', () => {
  it('uses the fake only when explicitly asked', async () => {
    vi.stubEnv('GOOGLE_PLACES_API_KEY', '');
    vi.stubEnv('PLACES_PROVIDER', 'fake');
    const { placesProvider } = await import('./index');
    expect((await placesProvider().details('demo-p1', { locale: 'en' }))?.name).toBe('Bar Nachtfalter');
  });
  it('is unavailable without a key and without the fake', async () => {
    vi.stubEnv('GOOGLE_PLACES_API_KEY', '');
    vi.stubEnv('PLACES_PROVIDER', '');
    const { placesProvider } = await import('./index');
    const { PlacesUnavailableError } = await import('./types');
    expect(() => placesProvider()).toThrow(PlacesUnavailableError);
  });
});
```

- [ ] **Step 2: Run and see them fail**

Run: `npx vitest run src/lib/places`
Expected: FAIL — modules not found.

- [ ] **Step 3: Implement**

`src/lib/places/types.ts`:

```ts
export type Locale = 'de' | 'en';
export type LatLng = { lat: number; lng: number };
export type PlaceSuggestion = { placeId: string; name: string; secondary: string };
export type PlaceDetails = { placeId: string; name: string; address: string; lat: number; lng: number; closed: boolean };

// The only boundary between the app and a place-data vendor (spec §6): swapping
// Google for another vendor means writing one more implementation of this.
export interface PlacesProvider {
  autocomplete(input: string, opts: { near: LatLng; locale: Locale; sessionToken: string }): Promise<PlaceSuggestion[]>;
  /** Resolves to null when the place does not exist (any more). */
  details(placeId: string, opts: { locale: Locale; sessionToken?: string }): Promise<PlaceDetails | null>;
}

/** The vendor is down, over quota or not configured. */
export class PlacesUnavailableError extends Error {
  constructor(message = 'places_unavailable') {
    super(message);
    this.name = 'PlacesUnavailableError';
  }
}

export function isGooglePlaceId(value: unknown): value is string {
  return typeof value === 'string' && /^[A-Za-z0-9_-]{1,300}$/.test(value);
}
```

`src/lib/places/fake.ts` — copy the 12 entries of `PLACES` in `scripts/seed-demo.ts` (keys `p1`…`p12`, same names, addresses and coordinates) as `demo-p1`…`demo-p12`, then add four unspotted places:

```ts
import type { PlaceDetails, PlacesProvider } from './types';

// Local development, tests and CI (PLACES_PROVIDER=fake). The demo ids match
// scripts/seed-demo.ts so spotting a demo place joins its existing row.
export const FAKE_PLACES: PlaceDetails[] = [
  { placeId: 'demo-p1', name: 'Bar Nachtfalter', address: 'Dominikanerstraße, Düsseldorf', lat: 51.22865, lng: 6.7588, closed: false },
  // … demo-p2 … demo-p12, copied from scripts/seed-demo.ts PLACES (closed: false)
  { placeId: 'fake-enzo', name: 'Trattoria Da Enzo', address: 'Luegallee, Düsseldorf', lat: 51.2287, lng: 6.7612, closed: false },
  { placeId: 'fake-kaiser', name: 'Kaiserbar', address: 'Kaiser-Wilhelm-Ring, Düsseldorf', lat: 51.2305, lng: 6.7658, closed: false },
  { placeId: 'fake-rheinblick', name: 'Café Rheinblick', address: 'Rheinallee, Düsseldorf', lat: 51.2362, lng: 6.7641, closed: false },
  { placeId: 'fake-gleis', name: 'Gleis 3', address: 'Hansaallee, Düsseldorf', lat: 51.2331, lng: 6.7419, closed: false },
];

function distance(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  return Math.hypot(a.lat - b.lat, (a.lng - b.lng) * Math.cos((a.lat * Math.PI) / 180));
}

export const fakePlaces: PlacesProvider = {
  async autocomplete(input, { near }) {
    const needle = input.trim().toLowerCase();
    return FAKE_PLACES.filter((p) => p.name.toLowerCase().includes(needle))
      .sort((a, b) => distance(a, near) - distance(b, near))
      .slice(0, 5)
      .map((p) => ({ placeId: p.placeId, name: p.name, secondary: p.address }));
  },
  async details(placeId) {
    return FAKE_PLACES.find((p) => p.placeId === placeId) ?? null;
  },
};
```

(The comment line `// … demo-p2 …` is an instruction to you, not code to keep: the final file lists all 16 entries explicitly.)

`src/lib/places/google.ts`:

```ts
import { isGooglePlaceId, PlacesUnavailableError, type PlacesProvider } from './types';

const BASE = 'https://places.googleapis.com/v1';
const TYPES = ['restaurant', 'bar', 'cafe', 'night_club'];
const DETAILS_FIELDS = 'id,displayName,formattedAddress,location,businessStatus';

type Prediction = { placePrediction?: { placeId: string; structuredFormat?: { mainText?: { text: string }; secondaryText?: { text: string } } } };
type Details = { id: string; displayName?: { text: string }; formattedAddress?: string; location?: { latitude: number; longitude: number }; businessStatus?: string };

export function googlePlaces(apiKey: string, fetchImpl: typeof fetch = fetch): PlacesProvider {
  async function call(url: string, init: RequestInit): Promise<Response> {
    try {
      return await fetchImpl(url, { ...init, headers: { ...(init.headers as Record<string, string>), 'X-Goog-Api-Key': apiKey }, cache: 'no-store' });
    } catch {
      throw new PlacesUnavailableError();
    }
  }

  return {
    async autocomplete(input, { near, locale, sessionToken }) {
      const response = await call(`${BASE}/places:autocomplete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input,
          languageCode: locale,
          sessionToken,
          locationBias: { circle: { center: { latitude: near.lat, longitude: near.lng }, radius: 20000 } },
          includedPrimaryTypes: TYPES,
        }),
      });
      if (!response.ok) throw new PlacesUnavailableError(`autocomplete ${response.status}`);
      const body = (await response.json()) as { suggestions?: Prediction[] };
      return (body.suggestions ?? []).flatMap(({ placePrediction: p }) =>
        p ? [{ placeId: p.placeId, name: p.structuredFormat?.mainText?.text ?? '', secondary: p.structuredFormat?.secondaryText?.text ?? '' }] : [],
      );
    },

    async details(placeId, { locale, sessionToken }) {
      if (!isGooglePlaceId(placeId)) return null;
      const query = new URLSearchParams({ languageCode: locale });
      if (sessionToken) query.set('sessionToken', sessionToken);
      const response = await call(`${BASE}/places/${placeId}?${query}`, { headers: { 'X-Goog-FieldMask': DETAILS_FIELDS } });
      if (response.status === 404) return null;
      if (!response.ok) throw new PlacesUnavailableError(`details ${response.status}`);
      const body = (await response.json()) as Details;
      if (!body.location) return null;
      return {
        placeId: body.id,
        name: body.displayName?.text ?? '',
        address: body.formattedAddress ?? '',
        lat: body.location.latitude,
        lng: body.location.longitude,
        closed: body.businessStatus === 'CLOSED_PERMANENTLY',
      };
    },
  };
}
```

`src/lib/places/cache.ts`:

```ts
import type { PlacesProvider } from './types';

const MAX_ENTRIES = 500;

// Brief in-memory cache (per server instance) to limit Google cost while a
// member types. Session tokens are billing hints, not part of the answer.
export function withCache(provider: PlacesProvider, ttlMs = 5 * 60_000, now: () => number = Date.now): PlacesProvider {
  const entries = new Map<string, { at: number; value: Promise<unknown> }>();

  function remember<T>(key: string, load: () => Promise<T>): Promise<T> {
    const hit = entries.get(key);
    if (hit && now() - hit.at <= ttlMs) return hit.value as Promise<T>;
    const value = load();
    entries.set(key, { at: now(), value });
    value.catch(() => entries.delete(key));
    if (entries.size > MAX_ENTRIES) entries.delete(entries.keys().next().value!);
    return value;
  }

  return {
    autocomplete: (input, opts) =>
      remember(`a|${opts.locale}|${opts.near.lat.toFixed(3)},${opts.near.lng.toFixed(3)}|${input.trim().toLowerCase()}`, () => provider.autocomplete(input, opts)),
    details: (placeId, opts) => remember(`d|${opts.locale}|${placeId}`, () => provider.details(placeId, opts)),
  };
}
```

`src/lib/places/index.ts`:

```ts
import 'server-only';
import { withCache } from './cache';
import { fakePlaces } from './fake';
import { googlePlaces } from './google';
import { PlacesUnavailableError, type PlacesProvider } from './types';

let google: { key: string; provider: PlacesProvider } | null = null;

// Google when a key is configured; the fake only when asked for explicitly
// (local development, CI). Production without a key is "unavailable", never fake.
export function placesProvider(): PlacesProvider {
  const key = process.env.GOOGLE_PLACES_API_KEY;
  if (key) {
    if (google?.key !== key) google = { key, provider: withCache(googlePlaces(key)) };
    return google.provider;
  }
  if (process.env.PLACES_PROVIDER === 'fake') return fakePlaces;
  throw new PlacesUnavailableError('GOOGLE_PLACES_API_KEY is not set');
}
```

- [ ] **Step 4: Run the tests**

Run: `npx vitest run src/lib/places && npm run lint && npm run typecheck`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/places
git commit -m "feat(places): provider interface with Google Places (New), a local fake and a short cache"
```

---

### Task 3: Error mapping, spot form parsing and all Plan 3 strings

**Files:**
- Modify: `src/lib/errors.ts`, `src/lib/errors.test.ts`
- Create: `src/lib/spot-form.ts`, `src/lib/spot-form.test.ts`
- Modify: `src/i18n/en.ts`, `src/i18n/de.ts`

**Interfaces:**
- Produces:
  - `errorKey()` keeps its signature; new keys `note_too_long`, `invalid_known_for`, `places_unavailable`, `place_not_found`.
  - `parseSpotForm(form: FormData): { ok: true; value: SpotInput } | { ok: false; error: 'invalid_tags' | 'note_too_long' | 'invalid_known_for' }` with `SpotInput = { tags: string[]; note: string | null; knownFor: string[] }`. Form field names: `tag` (repeated), `note`, `knownFor` (repeated).
  - Messages `t.nav.spot`, `t.spotForm.*`, `t.spot.*` additions, `t.report.*`, listed below.

- [ ] **Step 1: Write the failing tests**

Append to `src/lib/errors.test.ts` inside `describe('errorKey', …)`:

```ts
  it('maps spot errors by table, not just by code', () => {
    expect(errorKey({ code: 'P0001', message: 'invalid_known_for' })).toBe('invalid_known_for');
    expect(errorKey({ code: '23514', message: 'new row for relation "recommendations" violates check constraint "recommendations_note_check"' })).toBe('note_too_long');
    expect(errorKey({ code: '23514', message: 'violates check constraint "known_for_label_check"' })).toBe('invalid_known_for');
    expect(errorKey({ code: '23514', message: 'violates check constraint "recommendations_tags_check"' })).toBe('invalid_tags');
    expect(errorKey({ code: '23505', message: 'duplicate key value violates unique constraint "known_for_pkey"' })).toBe('generic');
    expect(errorKey({ code: '23514', message: 'violates check constraint "reports_reason_check"' })).toBe('generic');
  });
```

`src/lib/spot-form.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { parseSpotForm } from './spot-form';

function form(entries: [string, string][]): FormData {
  const data = new FormData();
  for (const [key, value] of entries) data.append(key, value);
  return data;
}

describe('parseSpotForm', () => {
  it('reads moods, note and known-for entries', () => {
    expect(parseSpotForm(form([['tag', 'wine'], ['tag', 'date-night'], ['tag', 'wine'], ['note', '  Ask for Luca  '], ['knownFor', ' Truffle   pasta '], ['knownFor', '']]))).toEqual({
      ok: true,
      value: { tags: ['wine', 'date-night'], note: 'Ask for Luca', knownFor: ['Truffle pasta'] },
    });
  });
  it('treats an empty note as none', () => {
    const result = parseSpotForm(form([['tag', 'wine'], ['note', '   ']]));
    expect(result.ok && result.value.note).toBeNull();
  });
  it('needs 1 to 3 moods', () => {
    expect(parseSpotForm(form([]))).toEqual({ ok: false, error: 'invalid_tags' });
    expect(parseSpotForm(form([['tag', 'a'], ['tag', 'b'], ['tag', 'c'], ['tag', 'd']]))).toEqual({ ok: false, error: 'invalid_tags' });
  });
  it('limits the note to 500 characters', () => {
    expect(parseSpotForm(form([['tag', 'wine'], ['note', 'x'.repeat(501)]]))).toEqual({ ok: false, error: 'note_too_long' });
  });
  it('allows two known-for entries of up to 40 characters, ignoring case duplicates', () => {
    expect(parseSpotForm(form([['tag', 'wine'], ['knownFor', 'Pasta'], ['knownFor', 'pasta']]))).toEqual({ ok: true, value: { tags: ['wine'], note: null, knownFor: ['Pasta'] } });
    expect(parseSpotForm(form([['tag', 'wine'], ['knownFor', 'a'], ['knownFor', 'b'], ['knownFor', 'c']]))).toEqual({ ok: false, error: 'invalid_known_for' });
    expect(parseSpotForm(form([['tag', 'wine'], ['knownFor', 'x'.repeat(41)]]))).toEqual({ ok: false, error: 'invalid_known_for' });
  });
});
```

- [ ] **Step 2: Run and see them fail**

Run: `npx vitest run src/lib/errors.test.ts src/lib/spot-form.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement**

`src/lib/errors.ts`:

```ts
import type { Messages } from '@/i18n';

export type ErrorKey = keyof Messages['errors'];

const RAISED: ErrorKey[] = ['username_reserved', 'rate_limited', 'invalid_tags', 'invalid_known_for', 'invalid_scope', 'invalid_radius', 'invalid_page'];

// Constraint names identify the table and column, so a unique violation on a
// spot never reads as "username taken".
const CONSTRAINTS: [constraint: string, key: ErrorKey][] = [
  ['profiles_username_key', 'username_taken'],
  ['profiles_username_check', 'username_format'],
  ['profiles_display_name_check', 'display_name'],
  ['recommendations_note_check', 'note_too_long'],
  ['recommendations_tags_check', 'invalid_tags'],
  ['known_for_label_check', 'invalid_known_for'],
];

export function errorKey(error: { code?: string; message?: string } | null | undefined): ErrorKey {
  if (!error) return 'generic';
  const message = error.message ?? '';
  const raised = RAISED.find((key) => message.includes(key));
  if (raised) return raised;
  if (error.code === '23505' || error.code === '23514') {
    return CONSTRAINTS.find(([constraint]) => message.includes(constraint))?.[1] ?? 'generic';
  }
  return 'generic';
}
```

Before relying on the constraint names, confirm them: `psql postgresql://postgres:postgres@127.0.0.1:54322/postgres -c "select conname from pg_constraint where conrelid in ('public.profiles'::regclass, 'public.recommendations'::regclass, 'public.known_for'::regclass)"`. If the profile username format is enforced under another name (a domain or differently named check), use the real name and keep the existing `errors.test.ts` cases green. Run `npx playwright test tests/e2e/auth.spec.ts` afterwards: the onboarding error messages must still appear.

`src/lib/spot-form.ts`:

```ts
export type SpotInput = { tags: string[]; note: string | null; knownFor: string[] };
export type SpotFormError = 'invalid_tags' | 'note_too_long' | 'invalid_known_for';

const strings = (form: FormData, name: string) => form.getAll(name).filter((v): v is string => typeof v === 'string');

// Mirrors the database rules (recommendations checks, save_spot) so members get
// a precise message before a round trip; the database stays the authority.
export function parseSpotForm(form: FormData): { ok: true; value: SpotInput } | { ok: false; error: SpotFormError } {
  const tags = [...new Set(strings(form, 'tag'))];
  if (tags.length < 1 || tags.length > 3) return { ok: false, error: 'invalid_tags' };

  const note = String(form.get('note') ?? '').trim();
  if (note.length > 500) return { ok: false, error: 'note_too_long' };

  const knownFor: string[] = [];
  for (const raw of strings(form, 'knownFor')) {
    const label = raw.trim().replace(/\s+/g, ' ');
    if (label && !knownFor.some((x) => x.toLowerCase() === label.toLowerCase())) knownFor.push(label);
  }
  if (knownFor.length > 2 || knownFor.some((x) => x.length > 40)) return { ok: false, error: 'invalid_known_for' };

  return { ok: true, value: { tags, note: note || null, knownFor } };
}
```

Strings — add to `en.ts` (and the German column to `de.ts`, same keys):

| Key | English | German |
|---|---|---|
| `nav.spot` | `Spot` | `Spot` |
| `spotForm.title` | `Spot a place` | `Ort als Spot markieren` |
| `spotForm.editTitle` | `Edit your spot` | `Deinen Spot bearbeiten` |
| `spotForm.search` | `Search a restaurant, bar or café` | `Restaurant, Bar oder Café suchen` |
| `spotForm.searchHint` | `Type at least two letters.` | `Mindestens zwei Buchstaben eingeben.` |
| `spotForm.noResults` | `No places found.` | `Keine Orte gefunden.` |
| `spotForm.moods` | `Moods` | `Moods` |
| `spotForm.moodsHint` | `Choose 1 to 3.` | `Wähle 1 bis 3.` |
| `spotForm.note` | `Your note` | `Deine Notiz` |
| `spotForm.notePlaceholder` | `What should members know?` | `Was sollten Mitglieder wissen?` |
| `spotForm.knownFor` | `Known for` | `Bekannt für` |
| `spotForm.knownForHint` | `Optional, up to two. For example: Truffle pasta.` | `Optional, bis zu zwei. Zum Beispiel: Trüffelpasta.` |
| `spotForm.save` | `Save spot` | `Spot speichern` |
| `spotForm.delete` | `Delete spot` | `Spot löschen` |
| `spotForm.change` | `Choose another place` | `Anderen Ort wählen` |
| `spot.closed` | `Permanently closed` | `Dauerhaft geschlossen` |
| `spot.knownFor` | `Known for` | `Bekannt für` |
| `spot.members` | `(n: number) => (n === 1 ? '1 member' : \`${n} members\`)` | `(n) => (n === 1 ? '1 Mitglied' : \`${n} Mitglieder\`)` |
| `spot.spotThis` | `Spot this place` | `Als Spot markieren` |
| `spot.editMine` | `Edit your spot` | `Deinen Spot bearbeiten` |
| `spot.saved` | `Spot saved.` | `Spot gespeichert.` |
| `spot.deleted` | `Your spot was removed.` | `Dein Spot wurde entfernt.` |
| `report.action` | `Report` | `Melden` |
| `report.reason` | `Reason` | `Grund` |
| `report.reasons` | `{ wrong: 'Wrong or outdated', offensive: 'Offensive', spam: 'Spam or advertising' }` | `{ wrong: 'Falsch oder veraltet', offensive: 'Beleidigend', spam: 'Spam oder Werbung' }` |
| `report.send` | `Send report` | `Meldung senden` |
| `report.thanks` | `Thank you. We’ll take a look.` | `Danke. Wir sehen es uns an.` |
| `errors.note_too_long` | `Keep your note under 500 characters.` | `Deine Notiz darf höchstens 500 Zeichen haben.` |
| `errors.invalid_known_for` | `Add up to two “Known for” entries of up to 40 characters.` | `Bis zu zwei „Bekannt für“-Einträge mit höchstens 40 Zeichen.` |
| `errors.places_unavailable` | `Place search is unavailable right now. Please try again later.` | `Die Ortssuche ist gerade nicht verfügbar. Bitte versuche es später.` |
| `errors.place_not_found` | `This place could not be found.` | `Dieser Ort wurde nicht gefunden.` |

`spotForm` and `report` are new top-level sections; the `spot.*` rows extend the existing `spot` section. The German `de.ts` must type-check against `Messages` (it already does for the existing keys; keep that pattern).

- [ ] **Step 4: Run the tests**

Run: `npm run lint && npm run typecheck && npm test`
Expected: PASS (including the i18n parity test).

- [ ] **Step 5: Commit**

```bash
git add src/lib/errors.ts src/lib/errors.test.ts src/lib/spot-form.ts src/lib/spot-form.test.ts src/i18n
git commit -m "feat(spot): per-table error mapping, spot form parsing and spotting copy (EN/DE)"
```

---

### Task 4: Place store, autocomplete endpoint and spot actions

**Files:**
- Create: `src/lib/places/store.ts`
- Create: `src/app/api/places/autocomplete/route.ts`
- Create: `src/lib/actions/spot.ts`
- Modify: `scripts/env-local.sh` (add `PLACES_PROVIDER=fake`), `.env.local` (re-run the script)
- Test: `tests/e2e/places-api.spec.ts`

**Interfaces:**
- Consumes: `placesProvider()`, `isGooglePlaceId`, `PlacesUnavailableError` (Task 2); `parseSpotForm`, `errorKey` (Task 3); `save_spot` (Task 1); `createAdminClient()` (`src/lib/supabase/admin.ts`); `requireMember()`, `getViewer()` (`src/lib/viewer.ts`).
- Produces:
  - `lookupPlace(googleId: string, locale: Locale): Promise<{ id: string | null; googleId: string; name: string; address: string; closed: boolean } | null>` — DB row if stored, else provider details without storing; `null` when unknown. Throws `PlacesUnavailableError`.
  - `ensurePlace(googleId: string, locale: Locale, sessionToken?: string): Promise<string | null>` — returns `places.id`; calls the provider only when the row is missing or older than 30 days; `null` when unknown. Throws `PlacesUnavailableError`.
  - `GET /api/places/autocomplete?q=&lat=&lng=&session=` → `200 { suggestions: PlaceSuggestion[] }`, `401 { error: 'unauthorized' }`, `503 { error: 'places_unavailable' }`.
  - Server actions (form fields): `saveSpot` (`place`, `session`, `tag`×n, `note`, `knownFor`×n) → redirects to `/spots/{placeId}?saved=1` or back to `/spot?place=…&error=…`; `deleteSpot` (`spotId`, `placeId`) → `/spots/{placeId}?deleted=1`; `reportSpot` (`spotId`, `placeId`, `reason` ∈ `wrong|offensive|spam`) → `/spots/{placeId}?reported=1`.

- [ ] **Step 1: Write the failing e2e test** `tests/e2e/places-api.spec.ts`:

```ts
import { expect, test } from '@playwright/test';
import { joinAsNewMember } from './helpers';

test('autocomplete needs a signed-in member', async ({ request }) => {
  const response = await request.get('/api/places/autocomplete?q=enzo', { maxRedirects: 0 });
  expect([401, 307]).toContain(response.status());
});

test('autocomplete returns nearby places for members', async ({ page }) => {
  await joinAsNewMember(page);
  const response = await page.request.get('/api/places/autocomplete?q=enzo&lat=51.2317&lng=6.7545&session=3f1c2a4e-9b7d-4e6f-8a1b-2c3d4e5f6a7b');
  expect(response.status()).toBe(200);
  expect(await response.json()).toEqual({ suggestions: [{ placeId: 'fake-enzo', name: 'Trattoria Da Enzo', secondary: 'Luegallee, Düsseldorf' }] });
  expect(response.headers()['cache-control']).toContain('no-store');
  const short = await page.request.get('/api/places/autocomplete?q=e');
  expect(await short.json()).toEqual({ suggestions: [] });
});
```

- [ ] **Step 2: Run and see it fail**

Run: `npm run build && npx playwright test tests/e2e/places-api.spec.ts`
Expected: FAIL (the route does not exist yet).

- [ ] **Step 3: Implement**

`scripts/env-local.sh`: add the line `PLACES_PROVIDER=fake` to the heredoc (after `MAILPIT_URL=…`), then run `bash scripts/env-local.sh`. The CI e2e job already runs this script, so CI gets the fake too.

`src/lib/places/store.ts`:

```ts
import 'server-only';
import { createAdminClient } from '@/lib/supabase/admin';
import { placesProvider } from './index';
import { isGooglePlaceId, type Locale } from './types';

const THIRTY_DAYS = 30 * 24 * 60 * 60 * 1000;

export type KnownPlace = { id: string | null; googleId: string; name: string; address: string; closed: boolean };

// For showing a place before it is spotted: reads the stored row, otherwise
// asks the provider without storing anything (Google ToS: we only keep places
// members actually spotted).
export async function lookupPlace(googleId: string, locale: Locale): Promise<KnownPlace | null> {
  if (!isGooglePlaceId(googleId)) return null;
  const { data: row, error } = await createAdminClient()
    .from('places')
    .select('id, name, address, is_closed')
    .eq('google_place_id', googleId)
    .maybeSingle();
  if (error) throw new Error(`Could not load place: ${error.message}`);
  if (row) return { id: row.id, googleId, name: row.name, address: row.address ?? '', closed: row.is_closed };
  const details = await placesProvider().details(googleId, { locale });
  return details && { id: null, googleId, name: details.name, address: details.address, closed: details.closed };
}

// For saving a spot: makes sure the place row exists and is fresh. Only the
// server writes places, and only with data the provider confirmed.
export async function ensurePlace(googleId: string, locale: Locale, sessionToken?: string): Promise<string | null> {
  if (!isGooglePlaceId(googleId)) return null;
  const admin = createAdminClient();
  const { data: row, error } = await admin.from('places').select('id, details_refreshed_at').eq('google_place_id', googleId).maybeSingle();
  if (error) throw new Error(`Could not load place: ${error.message}`);
  if (row && Date.now() - Date.parse(row.details_refreshed_at) < THIRTY_DAYS) return row.id;

  const details = await placesProvider().details(googleId, { locale, sessionToken });
  if (!details) return row?.id ?? null;
  const { data: saved, error: saveError } = await admin
    .from('places')
    .upsert(
      {
        google_place_id: googleId,
        name: details.name,
        address: details.address,
        location: `SRID=4326;POINT(${details.lng} ${details.lat})`,
        is_closed: details.closed,
        details_refreshed_at: new Date().toISOString(),
      },
      { onConflict: 'google_place_id' },
    )
    .select('id')
    .single();
  if (saveError) throw new Error(`Could not save place: ${saveError.message}`);
  return saved.id;
}
```

Check how `scripts/seed-demo.ts` writes `location` and use the same format if it differs from the EWKT string above.

`src/app/api/places/autocomplete/route.ts`:

```ts
import { NextResponse } from 'next/server';
import { placesProvider } from '@/lib/places';
import { getViewer } from '@/lib/viewer';

const OBERKASSEL = { lat: 51.2317, lng: 6.7545 };
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const headers = { 'Cache-Control': 'private, no-store' };

function coordinate(value: string | null, limit: number): number | null {
  if (value === null || value.trim() === '') return null;
  const n = Number(value);
  return Number.isFinite(n) && Math.abs(n) <= limit ? n : null;
}

export async function GET(request: Request) {
  const { user, profile, locale } = await getViewer();
  if (!user || !profile) return NextResponse.json({ error: 'unauthorized' }, { status: 401, headers });

  const params = new URL(request.url).searchParams;
  const q = (params.get('q') ?? '').trim();
  if (q.length < 2 || q.length > 80) return NextResponse.json({ suggestions: [] }, { headers });

  const lat = coordinate(params.get('lat'), 90);
  const lng = coordinate(params.get('lng'), 180);
  const near = lat !== null && lng !== null ? { lat, lng } : OBERKASSEL;
  const session = params.get('session') ?? '';
  const sessionToken = UUID.test(session) ? session : crypto.randomUUID();

  try {
    const suggestions = await placesProvider().autocomplete(q, { near, locale, sessionToken });
    return NextResponse.json({ suggestions }, { headers });
  } catch (error) {
    console.error('places autocomplete failed', error);
    return NextResponse.json({ error: 'places_unavailable' }, { status: 503, headers });
  }
}
```

Note: `src/lib/supabase/proxy.ts` redirects signed-out requests to `/login` before this handler runs; that is why the first e2e test accepts 307 as well. The handler still checks auth itself.

`src/lib/actions/spot.ts`:

```ts
'use server';

import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';
import { errorKey, type ErrorKey } from '@/lib/errors';
import { PlacesUnavailableError } from '@/lib/places/types';
import { ensurePlace } from '@/lib/places/store';
import { parseSpotForm } from '@/lib/spot-form';
import { requireMember } from '@/lib/viewer';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const REASONS = ['wrong', 'offensive', 'spam'] as const;

function field(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === 'string' ? value : '';
}

function backToForm(googleId: string, error: ErrorKey): never {
  redirect(`/spot?place=${encodeURIComponent(googleId)}&error=${error}`);
}

export async function saveSpot(form: FormData) {
  const { supabase, locale } = await requireMember();
  const googleId = field(form, 'place');
  const input = parseSpotForm(form);
  if (!input.ok) backToForm(googleId, input.error);

  let placeId: string | null;
  try {
    placeId = await ensurePlace(googleId, locale, field(form, 'session') || undefined);
  } catch (error) {
    if (error instanceof PlacesUnavailableError) backToForm(googleId, 'places_unavailable');
    throw error;
  }
  if (!placeId) backToForm(googleId, 'place_not_found');

  const { error } = await supabase.rpc('save_spot', {
    p_place_id: placeId,
    p_tags: input.value.tags,
    p_note: input.value.note ?? '',
    p_known_for: input.value.knownFor,
  });
  if (error) backToForm(googleId, errorKey(error));

  revalidatePath('/', 'layout');
  redirect(`/spots/${placeId}?saved=1`);
}

export async function deleteSpot(form: FormData) {
  const { supabase, user } = await requireMember();
  const spotId = field(form, 'spotId');
  const placeId = field(form, 'placeId');
  if (!UUID.test(spotId) || !UUID.test(placeId)) redirect('/');
  const { error } = await supabase.from('recommendations').delete().eq('id', spotId).eq('user_id', user.id);
  revalidatePath('/', 'layout');
  redirect(`/spots/${placeId}?${error ? `error=${errorKey(error)}` : 'deleted=1'}`);
}

export async function reportSpot(form: FormData) {
  const { supabase, user } = await requireMember();
  const spotId = field(form, 'spotId');
  const placeId = field(form, 'placeId');
  const reason = field(form, 'reason');
  if (!UUID.test(spotId) || !UUID.test(placeId)) redirect('/');
  if (!(REASONS as readonly string[]).includes(reason)) redirect(`/spots/${placeId}?error=generic`);
  // No SELECT policy on reports: insert without returning the row.
  const { error } = await supabase.from('reports').insert({ reporter_id: user.id, target_type: 'recommendation', target_id: spotId, reason });
  redirect(`/spots/${placeId}?${error ? `error=${errorKey(error)}` : 'reported=1'}`);
}
```

`redirect()` throws by design: it is never called inside the `try` block above, so it is not swallowed. `p_note: ''` is how "no note" is sent (the function turns empty into null), because the generated RPC types may not accept `null` for `text` arguments.

- [ ] **Step 4: Verify**

Run: `npm run lint && npm run typecheck && npm test && npm run build && npx playwright test tests/e2e/places-api.spec.ts`
Expected: PASS. (`playwright.config.ts` starts the app itself; if a server is already running on :3000, stop it first or the old build is tested.)

- [ ] **Step 5: Commit**

```bash
git add src/lib/places/store.ts src/app/api/places src/lib/actions/spot.ts scripts/env-local.sh tests/e2e/places-api.spec.ts
git commit -m "feat(spot): place store, member-only autocomplete endpoint and spot actions"
```

---

### Task 5: Spot tab, place search and the spot form

**Files:**
- Modify: `src/components/Icons.tsx` (add `SpotIcon`), `src/components/TabBar.tsx`, `src/app/(app)/layout.tsx` (pass the new label)
- Create: `src/components/PlaceSearch.tsx`
- Create: `src/app/(app)/spot/page.tsx`
- Modify: `src/app/globals.css` (checkbox chips, textarea, search results)
- Test: `tests/e2e/spotting.spec.ts`

**Interfaces:**
- Consumes: `saveSpot`, `deleteSpot` (Task 4); `lookupPlace` (Task 4); `known_for_counts` (Task 1); `t.nav.spot`, `t.spotForm.*`, `t.errors.*` (Task 3); `PlaceSuggestion` (Task 2).
- Produces: route `/spot` (search) and `/spot?place={googleId}[&session=…][&error=…]` (form). `PlaceSearch` props: `{ labels: { search: string; hint: string; none: string; unavailable: string } }`.

- [ ] **Step 1: Write the failing e2e test** `tests/e2e/spotting.spec.ts`:

```ts
import { expect, test } from '@playwright/test';
import { joinAsNewMember, newMemberPage } from './helpers';

test('a member spots a new place and others find it with its known-for', async ({ page, browser }) => {
  await joinAsNewMember(page, 'Spotting Member');
  await page.getByRole('link', { name: 'Spot', exact: true }).click();
  await expect(page).toHaveURL(/\/spot$/);

  await page.getByRole('searchbox', { name: 'Search a restaurant, bar or café' }).fill('enzo');
  await page.getByRole('link', { name: /Trattoria Da Enzo/ }).click();

  await expect(page.getByRole('heading', { level: 1, name: 'Trattoria Da Enzo' })).toBeVisible();
  await page.getByText('Date night', { exact: true }).click();
  await page.getByLabel('Your note').fill('Ask for the table by the window.');
  await page.getByRole('textbox', { name: 'Known for 1' }).fill('Truffle pasta');
  await page.getByRole('button', { name: 'Save spot' }).click();

  await expect(page).toHaveURL(/\/spots\/[0-9a-f-]+\?saved=1/);
  await expect(page.getByText('Spot saved.')).toBeVisible();

  const other = await newMemberPage(browser);
  await other.goto('/?tag=date-night&scope=everyone&lat=51.2317&lng=6.7545');
  const row = other.getByRole('link', { name: /Trattoria Da Enzo/ });
  await expect(row).toContainText('Truffle pasta');
  await row.click();
  await expect(other.getByText('Ask for the table by the window.')).toBeVisible();
  await expect(other.getByText(/Truffle pasta\s*·\s*1 member/)).toBeVisible();
});

test('a member edits and deletes their spot', async ({ page }) => {
  await joinAsNewMember(page);
  await page.goto('/spot?place=fake-kaiser');
  await page.getByText('Cocktails', { exact: true }).click();
  await page.getByLabel('Your note').fill('First visit.');
  await page.getByRole('button', { name: 'Save spot' }).click();
  await expect(page.getByText('First visit.')).toBeVisible();

  await page.getByRole('link', { name: 'Edit your spot' }).click();
  await expect(page.getByRole('heading', { name: 'Edit your spot' })).toBeVisible();
  await expect(page.getByLabel('Your note')).toHaveValue('First visit.');
  await page.getByLabel('Your note').fill('Second visit, even better.');
  await page.getByRole('button', { name: 'Save spot' }).click();
  await expect(page.getByText('Second visit, even better.')).toBeVisible();

  await page.getByRole('link', { name: 'Edit your spot' }).click();
  await page.getByRole('button', { name: 'Delete spot' }).click();
  await expect(page.getByText('Your spot was removed.')).toBeVisible();
  await expect(page.getByText('Second visit, even better.')).toHaveCount(0);
  await expect(page.getByRole('link', { name: 'Spot this place' })).toBeVisible();
});

test('the form explains what is missing', async ({ page }) => {
  await joinAsNewMember(page);
  await page.goto('/spot?place=fake-rheinblick');
  await page.getByRole('button', { name: 'Save spot' }).click();
  await expect(page.getByRole('alert')).toHaveText('Choose 1 to 3 moods.');
});

test('an unknown place is not found', async ({ page }) => {
  await joinAsNewMember(page);
  await page.goto('/spot?place=fake-does-not-exist');
  await expect(page.getByRole('alert')).toHaveText('This place could not be found.');
});
```

(The "Known for", "Spot saved.", "Edit your spot" and "Spot this place" assertions on `/spots/[id]` pass only after Task 6; in this task run just the last two tests plus the first test up to the redirect. Task 6 makes the whole file green.)

- [ ] **Step 2: Run and see it fail**

Run: `npm run build && npx playwright test tests/e2e/spotting.spec.ts`
Expected: FAIL (no Spot tab, `/spot` is a 404).

- [ ] **Step 3: Implement**

`src/components/Icons.tsx` — add:

```tsx
export function SpotIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}
```

`src/components/TabBar.tsx` — labels gain `spot`; items become Now · Spot · Members; `active` is `'spot'` when `pathname === '/spot'` (note `/spots/…` belongs to Now):

```tsx
export function TabBar({ labels }: { labels: { main: string; now: string; spot: string; members: string } }) {
  const pathname = usePathname();
  const active = pathname.startsWith('/members') ? 'members' : pathname === '/spot' ? 'spot' : pathname === '/' || pathname.startsWith('/spots') ? 'now' : null;
  const items = [
    { key: 'now', href: '/', label: labels.now, icon: <NowIcon /> },
    { key: 'spot', href: '/spot', label: labels.spot, icon: <SpotIcon /> },
    { key: 'members', href: '/members', label: labels.members, icon: <MembersIcon /> },
  ] as const;
  // …render unchanged
```

Pass `spot: t.nav.spot` wherever `TabBar` labels are built (grep for `<TabBar`).

`src/components/PlaceSearch.tsx`:

```tsx
'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';
import type { PlaceSuggestion } from '@/lib/places/types';

type Labels = { search: string; hint: string; none: string; unavailable: string };
const OBERKASSEL = { lat: 51.2317, lng: 6.7545 };

export function PlaceSearch({ labels }: { labels: Labels }) {
  const session = useMemo(() => crypto.randomUUID(), []);
  const [near, setNear] = useState(OBERKASSEL);
  const [query, setQuery] = useState('');
  const [state, setState] = useState<{ q: string; results: PlaceSuggestion[] | 'error' } | null>(null);

  // Use the member's position only if they already allowed it; never prompt here.
  useEffect(() => {
    navigator.permissions?.query({ name: 'geolocation' }).then((status) => {
      if (status.state === 'granted') navigator.geolocation.getCurrentPosition((p) => setNear({ lat: p.coords.latitude, lng: p.coords.longitude }));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const params = new URLSearchParams({ q, lat: String(near.lat), lng: String(near.lng), session });
        const response = await fetch(`/api/places/autocomplete?${params}`, { signal: controller.signal });
        if (!response.ok) throw new Error(String(response.status));
        const body = (await response.json()) as { suggestions: PlaceSuggestion[] };
        setState({ q, results: body.suggestions });
      } catch (error) {
        if (!controller.signal.aborted) setState({ q, results: 'error' });
      }
    }, 250);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [query, near, session]);

  const q = query.trim();
  const current = state && state.q === q ? state.results : null;

  return (
    <div className="form">
      <label className="field">
        <span className="label">{labels.search}</span>
        <input className="input" type="search" autoFocus autoComplete="off" value={query} onChange={(e) => setQuery(e.target.value)} aria-label={labels.search} />
      </label>
      {q.length < 2 ? (
        <p className="hint hint--flat">{labels.hint}</p>
      ) : current === 'error' ? (
        <p className="notice notice--error" role="alert">{labels.unavailable}</p>
      ) : current && current.length === 0 ? (
        <p className="hint hint--flat">{labels.none}</p>
      ) : (
        <ul className="list">
          {(current ?? []).map((place) => (
            <li key={place.placeId}>
              <Link className="row" href={`/spot?place=${encodeURIComponent(place.placeId)}&session=${session}`}>
                <span className="row-name">{place.name}</span>
                <span className="row-meta">{place.secondary}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

`src/app/(app)/spot/page.tsx`:

```tsx
import Link from 'next/link';
import { PlaceSearch } from '@/components/PlaceSearch';
import { deleteSpot, saveSpot } from '@/lib/actions/spot';
import type { ErrorKey } from '@/lib/errors';
import { lookupPlace, type KnownPlace } from '@/lib/places/store';
import { PlacesUnavailableError } from '@/lib/places/types';
import { requireMember } from '@/lib/viewer';

const one = (v: string | string[] | undefined) => (typeof v === 'string' ? v : '');

export default async function SpotFormPage({ searchParams }: PageProps<'/spot'>) {
  const { supabase, user, t, locale } = await requireMember();
  const params = await searchParams;
  const googleId = one(params.place);
  const errorParam = one(params.error);
  const error = Object.hasOwn(t.errors, errorParam) ? t.errors[errorParam as ErrorKey] : null;
  const labels = { search: t.spotForm.search, hint: t.spotForm.searchHint, none: t.spotForm.noResults, unavailable: t.errors.places_unavailable };

  if (!googleId) {
    return (
      <>
        <h1 className="title">{t.spotForm.title}</h1>
        <PlaceSearch labels={labels} />
      </>
    );
  }

  let place: KnownPlace | null = null;
  let lookupError: string | null = null;
  try {
    place = await lookupPlace(googleId, locale);
    if (!place) lookupError = t.errors.place_not_found;
  } catch (e) {
    if (!(e instanceof PlacesUnavailableError)) throw e;
    lookupError = t.errors.places_unavailable;
  }
  if (!place) {
    return (
      <>
        <h1 className="title">{t.spotForm.title}</h1>
        <p className="notice notice--error" role="alert">{lookupError}</p>
        <Link className="link" href="/spot">{t.spotForm.change}</Link>
      </>
    );
  }

  const [{ data: tags }, { data: mine }, { data: counts }] = await Promise.all([
    supabase.from('tags').select('slug, label_en, label_de').eq('active', true).order('sort_order'),
    place.id
      ? supabase.from('recommendations').select('id, tags, note, known_for(label)').eq('place_id', place.id).eq('user_id', user.id).maybeSingle()
      : Promise.resolve({ data: null }),
    place.id ? supabase.rpc('known_for_counts', { p_place_ids: [place.id] }) : Promise.resolve({ data: [] }),
  ]);
  const chosen = new Set(mine?.tags ?? []);
  const knownFor = (mine?.known_for ?? []).map((k) => k.label);

  return (
    <>
      <Link href={place.id ? `/spots/${place.id}` : '/spot'} className="link link--soft">← {place.id ? t.spot.back : t.spotForm.change}</Link>
      <p className="eyebrow">{mine ? t.spotForm.editTitle : t.spotForm.title}</p>
      <h1 className="title">{place.name}</h1>
      <p className="lede">{place.address}</p>
      {error && <p className="notice notice--error" role="alert">{error}</p>}

      <form action={saveSpot} className="form">
        <input type="hidden" name="place" value={googleId} />
        <input type="hidden" name="session" value={one(params.session)} />
        <fieldset className="field fieldset">
          <legend className="label">{t.spotForm.moods} · {t.spotForm.moodsHint}</legend>
          <div className="chips chips--wrap">
            {(tags ?? []).map((tag) => (
              <label key={tag.slug} className="chip chip--check">
                <input type="checkbox" name="tag" value={tag.slug} defaultChecked={chosen.has(tag.slug)} />
                {locale === 'de' ? tag.label_de : tag.label_en}
              </label>
            ))}
          </div>
        </fieldset>
        <label className="field">
          <span className="label">{t.spotForm.note}</span>
          <textarea className="input textarea" name="note" maxLength={500} rows={4} placeholder={t.spotForm.notePlaceholder} defaultValue={mine?.note ?? ''} />
        </label>
        <fieldset className="field fieldset">
          <legend className="label">{t.spotForm.knownFor}</legend>
          {[0, 1].map((i) => (
            <input key={i} className="input" name="knownFor" maxLength={40} list="known-for-options" aria-label={`${t.spotForm.knownFor} ${i + 1}`} defaultValue={knownFor[i] ?? ''} />
          ))}
          <datalist id="known-for-options">
            {(counts ?? []).map((c) => <option key={c.label} value={c.label} />)}
          </datalist>
          <span className="hint hint--flat">{t.spotForm.knownForHint}</span>
        </fieldset>
        <button className="btn btn--primary btn--block" type="submit">{t.spotForm.save}</button>
      </form>

      {mine && place.id && (
        <form action={deleteSpot}>
          <input type="hidden" name="spotId" value={mine.id} />
          <input type="hidden" name="placeId" value={place.id} />
          <button className="btn btn--danger btn--block" type="submit">{t.spotForm.delete}</button>
        </form>
      )}
    </>
  );
}
```

If `supabase.from('recommendations').select('… known_for(label)')` does not type as an array embed, normalize like `authorOf` in `src/app/(app)/spots/[id]/page.tsx`.

`src/app/globals.css` — append, using existing tokens only:

```css
/* Spot form */
.fieldset { border: 0; margin: 0; padding: 0; min-width: 0; }
.chips--wrap { flex-wrap: wrap; overflow: visible; margin-inline: 0; padding-inline: 0; }
.chip--check { cursor: pointer; }
.chip--check input { position: absolute; opacity: 0; pointer-events: none; }
.chip--check:has(input:checked) { background: var(--accent); color: var(--accent-ink); }
.chip--check:has(input:focus-visible) { outline: 2px solid var(--ink); outline-offset: 2px; }
.textarea { resize: vertical; min-height: 96px; font: inherit; }
.hint--flat { margin: 0; }
```

Check the existing `.chips` and `.chip` rules first and adjust `.chips--wrap` so wrapped chips keep their normal size and spacing.

- [ ] **Step 4: Verify**

Run: `npm run lint && npm run typecheck && npm test && npm run build && npx playwright test tests/e2e/spotting.spec.ts -g "explains|not found" && npx playwright test tests/e2e/now.spec.ts`
Expected: PASS. Then take a 390×844 screenshot of `/spot` (search with "e" and "enzo" typed) and of the form, in light and dark, and look at them: chips wrap cleanly, one primary button, no horizontal scroll.

- [ ] **Step 5: Commit**

```bash
git add src/components src/app/\(app\)/spot src/app/\(app\)/layout.tsx src/app/globals.css tests/e2e/spotting.spec.ts
git commit -m "feat(spot): Spot tab with place search and the spot form"
```

---

### Task 6: Spot page and Now rows show Known for; edit, closed and report

**Files:**
- Modify: `src/app/(app)/spots/[id]/page.tsx`
- Modify: `src/app/(app)/page.tsx`
- Modify: `src/app/globals.css` (known-for list, report disclosure)
- Test: `tests/e2e/spotting.spec.ts` (add report test), `tests/e2e/spot.spec.ts` stays green

**Interfaces:**
- Consumes: `known_for_counts` (Task 1), `reportSpot` (Task 4), strings `t.spot.*`, `t.report.*` (Task 3).
- Produces: `/spots/[id]` understands `?saved=1`, `?deleted=1`, `?reported=1`, `?error=<ErrorKey>`.

- [ ] **Step 1: Add the failing report test** to `tests/e2e/spotting.spec.ts`:

```ts
test('a member reports someone else’s spot', async ({ page }) => {
  await joinAsNewMember(page);
  await page.goto('/?tag=date-night&scope=everyone&lat=51.2317&lng=6.7545');
  await page.getByRole('link', { name: /Bar Nachtfalter/ }).click();
  const annasSpot = page.getByRole('listitem').filter({ hasText: 'Sit at the bar and ask for the house negroni.' });
  await annasSpot.getByText('Report').click();
  await annasSpot.getByLabel('Reason').selectOption('wrong');
  await annasSpot.getByRole('button', { name: 'Send report' }).click();
  await expect(page.getByText('Thank you. We’ll take a look.')).toBeVisible();
});
```

- [ ] **Step 2: Run and see the new and Task 5 tests fail**

Run: `npm run build && npx playwright test tests/e2e/spotting.spec.ts`
Expected: FAIL on known-for, "Spot saved.", edit link and report.

- [ ] **Step 3: Implement**

In `src/app/(app)/spots/[id]/page.tsx`:
- Select `is_closed` with the place, and `user_id` on each spot; read `user` from `requireMember()` and `searchParams` from the page props.
- Load `supabase.rpc('known_for_counts', { p_place_ids: [place.id] })` in the existing `Promise.all`.
- Under the title: if `place.is_closed`, `<p className="eyebrow eyebrow--flat">{t.spot.closed}</p>`.
- Notices (after the facts list): `saved` → `t.spot.saved`, `deleted` → `t.spot.deleted`, `reported` → `t.report.thanks` as `<p className="notice" role="status">`; `error` (validated with `Object.hasOwn(t.errors, …)`) → `notice--error` with `role="alert"`.
- Actions row: primary button link to `/spot?place=${encodeURIComponent(place.google_place_id)}` labelled `t.spot.editMine` when one of the spots has `user_id === user.id`, else `t.spot.spotThis`; keep "Open in Google Maps" as the secondary `btn`. Hide the spot/edit button when the place is closed and the member has no spot there.
- When there are counts: `<h2 className="section-title">{t.spot.knownFor}</h2>` and `<ul className="known-for">` with one `<li>` per entry: `{c.label}<span> · {t.spot.members(Number(c.members))}</span>`.
- On each spot that is not the member's own, after the tags, a report disclosure:

```tsx
<details className="report">
  <summary>{t.report.action}</summary>
  <form action={reportSpot} className="report-form">
    <input type="hidden" name="spotId" value={spot.id} />
    <input type="hidden" name="placeId" value={place.id} />
    <label className="field">
      <span className="label">{t.report.reason}</span>
      <select className="input" name="reason" defaultValue="wrong">
        {(['wrong', 'offensive', 'spam'] as const).map((r) => <option key={r} value={r}>{t.report.reasons[r]}</option>)}
      </select>
    </label>
    <button className="btn btn--small" type="submit">{t.report.send}</button>
  </form>
</details>
```

In `src/app/(app)/page.tsx`, after `discover` succeeds with results, load the top entry per place:

```ts
const placeIds = (results ?? []).map((r) => r.place_id);
const { data: counts } = placeIds.length ? await supabase.rpc('known_for_counts', { p_place_ids: placeIds }) : { data: [] };
const topKnownFor = new Map<string, string>();
for (const c of counts ?? []) if (!topKnownFor.has(c.place_id)) topKnownFor.set(c.place_id, c.label);
```

and render the row meta as `{top ? `${top} · ` : ''}{first?.display_name}{others > 0 ? t.now.and(others) : ''}` with `const top = topKnownFor.get(result.place_id)`.

`src/app/globals.css` — append:

```css
/* Known for + report */
.eyebrow--flat { margin: 0; }
.known-for { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.known-for span { color: var(--ink-soft); font-size: 13px; }
.report { margin-top: 6px; font-size: 13px; color: var(--ink-faint); }
.report summary { cursor: pointer; list-style: none; }
.report summary::-webkit-details-marker { display: none; }
.report-form { display: flex; flex-direction: column; gap: 10px; margin-top: 10px; }
```

- [ ] **Step 4: Verify**

Run: `npm run lint && npm run typecheck && npm test && npm run build && npx playwright test`
Expected: the whole e2e suite passes (spotting, spot, now, members, settings, card, auth, security). Screenshot the spot page with Known for and an open report disclosure, light and dark, and look at it.

- [ ] **Step 5: Commit**

```bash
git add src/app src/app/globals.css tests/e2e/spotting.spec.ts
git commit -m "feat(spot): known-for on spot pages and Now rows, closed label, edit and report"
```

---

### Task 7: Place refresh job, docs and demo data

**Files:**
- Create: `src/lib/places/refresh.ts`, `src/lib/places/refresh.test.ts`
- Create: `src/app/api/cron/refresh-places/route.ts`
- Create: `vercel.json`
- Modify: `README.md`, `scripts/seed-demo.ts` (Known-for entries)

**Interfaces:**
- Consumes: `placesProvider()`, `PlaceDetails`, `PlacesProvider` (Task 2); `createAdminClient()`.
- Produces:
  - `refreshPlace(googleId: string, provider: PlacesProvider): Promise<{ kind: 'update'; name: string; address: string; lat: number; lng: number; closed: boolean } | { kind: 'closed' } | { kind: 'failed' }>`.
  - `GET /api/cron/refresh-places` with `Authorization: Bearer ${CRON_SECRET}` → `200 { refreshed, closed, failed }`; `401` otherwise (also when `CRON_SECRET` is unset).

- [ ] **Step 1: Write the failing test** `src/lib/places/refresh.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest';
import { refreshPlace } from './refresh';
import { PlacesUnavailableError, type PlacesProvider } from './types';

const provider = (details: PlacesProvider['details']): PlacesProvider => ({ autocomplete: vi.fn(), details });

describe('refreshPlace', () => {
  it('returns fresh cached fields', async () => {
    const result = await refreshPlace('g1', provider(async () => ({ placeId: 'g1', name: 'New', address: 'A', lat: 1, lng: 2, closed: false })));
    expect(result).toEqual({ kind: 'update', name: 'New', address: 'A', lat: 1, lng: 2, closed: false });
  });
  it('marks places Google no longer knows as closed (never deletes them)', async () => {
    expect(await refreshPlace('g1', provider(async () => null))).toEqual({ kind: 'closed' });
  });
  it('reports failures without changing anything', async () => {
    expect(await refreshPlace('g1', provider(async () => { throw new PlacesUnavailableError(); }))).toEqual({ kind: 'failed' });
  });
});
```

- [ ] **Step 2: Run and see it fail**

Run: `npx vitest run src/lib/places/refresh.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement**

`src/lib/places/refresh.ts`:

```ts
import type { PlacesProvider } from './types';

export type RefreshResult =
  | { kind: 'update'; name: string; address: string; lat: number; lng: number; closed: boolean }
  | { kind: 'closed' }
  | { kind: 'failed' };

// Google ToS: cached place fields are refreshed at most every 30 days. Places
// are closed, never deleted, because deleting would cascade to members' spots.
export async function refreshPlace(googleId: string, provider: PlacesProvider): Promise<RefreshResult> {
  try {
    const details = await provider.details(googleId, { locale: 'de' });
    if (!details) return { kind: 'closed' };
    return { kind: 'update', name: details.name, address: details.address, lat: details.lat, lng: details.lng, closed: details.closed };
  } catch {
    return { kind: 'failed' };
  }
}
```

`src/app/api/cron/refresh-places/route.ts`:

```ts
import { NextResponse } from 'next/server';
import { placesProvider } from '@/lib/places';
import { refreshPlace } from '@/lib/places/refresh';
import { createAdminClient } from '@/lib/supabase/admin';

const BATCH = 100;

export async function GET(request: Request) {
  const secret = process.env.CRON_SECRET;
  if (!secret || request.headers.get('authorization') !== `Bearer ${secret}`) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const admin = createAdminClient();
  const cutoff = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString();
  const { data: stale, error } = await admin
    .from('places')
    .select('id, google_place_id')
    .eq('is_closed', false)
    .lt('details_refreshed_at', cutoff)
    .order('details_refreshed_at')
    .limit(BATCH);
  if (error) return NextResponse.json({ error: 'db' }, { status: 500 });

  const provider = placesProvider();
  const summary = { refreshed: 0, closed: 0, failed: 0 };
  for (const place of stale ?? []) {
    const result = await refreshPlace(place.google_place_id, provider);
    if (result.kind === 'failed') { summary.failed++; continue; }
    const update = result.kind === 'closed'
      ? { is_closed: true, details_refreshed_at: new Date().toISOString() }
      : { name: result.name, address: result.address, location: `SRID=4326;POINT(${result.lng} ${result.lat})`, is_closed: result.closed, details_refreshed_at: new Date().toISOString() };
    const { error: updateError } = await admin.from('places').update(update).eq('id', place.id);
    if (updateError) summary.failed++;
    else if (result.kind === 'closed' || result.closed) summary.closed++;
    else summary.refreshed++;
  }
  return NextResponse.json(summary);
}
```

Add `/api/cron` to `PUBLIC_PREFIXES` in `src/lib/supabase/proxy.ts` so the proxy does not redirect the cron call to `/login` (the route checks its own secret).

`vercel.json`:

```json
{ "crons": [{ "path": "/api/cron/refresh-places", "schedule": "17 3 * * *" }] }
```

`scripts/seed-demo.ts`: after the spots are written, add Known-for entries with the admin client (it bypasses the revoked grants; `save_spot` needs a signed-in member, so it is not used here). Look up each recommendation id by `(user_id, place_id)` and upsert with `onConflict: 'recommendation_id,label'` so the script stays idempotent:

```ts
const KNOWN_FOR: [username: string, place: string, label: string][] = [
  ['anna', 'p1', 'House negroni'],
  ['mehmet_eats', 'p1', 'House negroni'],
  ['lea', 'p2', 'Tasting menu'],
  ['mehmet_eats', 'p9', 'Dumplings'],
  ['sofia_isst', 'p11', 'Live jazz'],
];
```

`README.md`: add a "Places" section: `PLACES_PROVIDER=fake` for local/CI; production needs `GOOGLE_PLACES_API_KEY` (Places API (New) enabled, key restricted to the Places API and to server use, daily quota/budget cap) and `CRON_SECRET` (Vercel Cron sends it as a Bearer token); the refresh job runs daily and refreshes places older than 30 days in batches of 100. Add to the production checklist: report emails to the owner are not sent yet (reports are visible in the Supabase dashboard).

- [ ] **Step 4: Verify**

Run: `npm run lint && npm run typecheck && npm test && npm run build && npm run seed:demo && npx playwright test`
Then, with the app running locally and `CRON_SECRET=test` in `.env.local`: `curl -s -H 'Authorization: Bearer test' http://127.0.0.1:3000/api/cron/refresh-places` → `{"refreshed":0,"closed":0,"failed":0}` (nothing is stale) and without the header → 401. Remove `CRON_SECRET` from `.env.local` again afterwards.

- [ ] **Step 5: Commit**

```bash
git add src/lib/places/refresh.ts src/lib/places/refresh.test.ts src/app/api/cron src/lib/supabase/proxy.ts vercel.json README.md scripts/seed-demo.ts
git commit -m "feat(places): monthly place refresh job, demo known-for entries and docs"
```

---

## Self-review notes

- Spec coverage: §5.3 add recommendation (Tasks 4–5), §5.2 spot detail with closed label and Recommend/Edit (Task 6), §6 `places/` provider + refresh job + brief cache (Tasks 2, 7), §7 Google down → friendly message (Tasks 4–5), report button (Tasks 4, 6; email deferred and documented), §10 Known for (Tasks 1, 5, 6), §10 notes: places written server-side, closed never deleted, errorKey per table (Tasks 3, 4, 7).
- Not in this plan: live Google details on the spot page (hours, photos), map view, report emails, membership levels and Wallet (Plan 4).
