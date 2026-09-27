# Spot — Plan 1: Database Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `spot` repository with a Supabase Postgres schema — profiles, follows, tags, places, recommendations, reports — whose privacy rules and Discover query are enforced and tested in the database.

**Architecture:** A Next.js app skeleton (UI comes in Plan 2) plus a `supabase/` folder holding SQL migrations. All privacy is enforced with Postgres row-level security (RLS); the Discover search is one Postgres function. Every behavior is covered by pgTAP tests run with `supabase test db` against the local Supabase stack (Docker).

**Tech Stack:** Next.js (App Router, TypeScript), Supabase CLI (npm devDependency), Postgres 15+ with PostGIS, pgTAP, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-27-spot-recommendations-app-design.md`

**Roadmap:** Plan 1 (this) — database core. Plan 2 — app shell: auth (magic link, Google, Apple), onboarding, i18n DE/EN, profiles, follow UI, settings, account deletion. Plan 3 — spots: Google Places module, add recommendation, Discover and spot-detail UI, report emails, place refresh job, Playwright end-to-end tests.

## Global Constraints

- Node.js 20 or newer; npm as package manager.
- Every table in `public` has RLS enabled. No table is readable or writable by clients except through an explicit policy.
- Every `security definer` function sets `search_path = ''` and schema-qualifies every name (`public.`, `auth.`, `extensions.`).
- PostGIS lives in the `extensions` schema; always write `extensions.geography`, `extensions.st_dwithin`, etc.
- Errors raised by our triggers/functions use these exact machine-readable messages (Plan 2/3 map them to localized text): `username_reserved`, `invalid_tags`, `rate_limited`, `invalid_scope`, `invalid_radius`, `invalid_page`.
- Username: `^[a-z0-9_]{3,30}$`. Display name: 1–50 chars. Locale: `de` | `en` (default `de`).
- Recommendation: 1–3 tags from the active `tags` list, no duplicates; note ≤ 500 chars; one per user per place.
- Rate limits: 200 follows and 50 recommendations per account per rolling 24 hours.
- Discover: default radius 2000 m, allowed 100–50000 m; page size 1–50 (default 20); scope `following` | `everyone`; the caller's own recommendations are never included.
- Test-only SQL lives in `supabase/test-helpers/` and is loaded as local seed data only; it is never part of a migration.

---

## File Structure

```
spot/
├── package.json                     # scripts: test:db
├── .github/workflows/db-tests.yml   # CI: runs pgTAP suite
├── docs/superpowers/specs/…         # copied spec
├── docs/superpowers/plans/…         # this plan
└── supabase/
    ├── config.toml                  # generated; seed paths edited
    ├── seed.sql                     # local dev seed (empty for now)
    ├── test-helpers/helpers.sql     # tests.* helper functions (local only)
    ├── migrations/
    │   ├── 20260927000001_extensions.sql
    │   ├── 20260927000002_profiles.sql
    │   ├── 20260927000003_follows.sql
    │   ├── 20260927000004_tags_places.sql
    │   ├── 20260927000005_recommendations.sql
    │   ├── 20260927000006_reports.sql
    │   └── 20260927000007_discover.sql
    └── tests/
        ├── 01_smoke.test.sql
        ├── 02_profiles.test.sql
        ├── 03_follows.test.sql
        ├── 04_tags_places.test.sql
        ├── 05_recommendations.test.sql
        ├── 06_reports_deletion.test.sql
        └── 07_discover.test.sql
```

One migration per concern; each has a matching test file.

**Test conventions (all test files):** each file is one transaction (`begin; … rollback;`), starts with `create extension if not exists pgtap with schema extensions;` and `select plan(N);`, and ends with `select * from finish();`. Setup runs as the admin role. `select tests.authenticate_as(<uuid>);` switches to a signed-in user, `select tests.as_anon();` to a signed-out visitor, and `reset role;` back to admin. For expected errors, always use the 4-argument form `throws_ok(sql, errcode, errmsg_or_null, description)`.

---

### Task 1: Repository scaffold, Supabase, PostGIS and test helpers

**Files:**
- Create: the `spot/` repository (via `create-next-app`)
- Create: `supabase/` (via `supabase init`), `supabase/seed.sql`, `supabase/test-helpers/helpers.sql`
- Create: `supabase/migrations/20260927000001_extensions.sql`
- Modify: `supabase/config.toml` (`[db.seed]` section), `package.json` (scripts)
- Test: `supabase/tests/01_smoke.test.sql`

**Interfaces:**
- Consumes: nothing.
- Produces (SQL, schema `tests`, local only):
  - `tests.create_auth_user(p_email text) returns uuid` — auth user without profile
  - `tests.auth_user_id(p_email text) returns uuid`
  - `tests.create_user(p_username text, p_private boolean default false) returns uuid` — auth user + profile (display name = username)
  - `tests.user_id(p_username text) returns uuid`
  - `tests.create_place(p_google_place_id text, p_name text, p_lat double precision, p_lng double precision, p_closed boolean default false) returns uuid`
  - `tests.place_id(p_google_place_id text) returns uuid`
  - `tests.authenticate_as(p_user_id uuid) returns void`
  - `tests.as_anon() returns void`
  - npm script `npm run test:db` = reset local DB (migrations + seed) and run all pgTAP tests.

- [ ] **Step 1: Create the repository**

Requires Docker running (for Supabase) and Node 20+.

```bash
npx create-next-app@latest spot --ts --eslint --tailwind --app --src-dir --import-alias "@/*" --use-npm --yes
cd spot
npm install --save-dev supabase
npx supabase init
mkdir -p docs/superpowers/specs docs/superpowers/plans supabase/tests supabase/test-helpers supabase/migrations
```

Copy the spec and this plan into `docs/superpowers/specs/` and `docs/superpowers/plans/` (same filenames).

- [ ] **Step 2: Add the test script**

In `package.json`, add to `"scripts"`:

```json
"test:db": "supabase db reset && supabase test db"
```

- [ ] **Step 3: Write the failing smoke test**

Create `supabase/tests/01_smoke.test.sql`:

```sql
begin;
create extension if not exists pgtap with schema extensions;
select plan(2);

select has_extension('postgis', 'postgis is installed');
select has_function(
  'tests', 'create_user', array['text', 'boolean'],
  'test helpers are loaded'
);

select * from finish();
rollback;
```

- [ ] **Step 4: Run it to verify it fails**

```bash
npx supabase start      # first run downloads Docker images; takes a few minutes
npm run test:db
```

Expected: FAIL — `postgis is installed` and `test helpers are loaded` both fail.

- [ ] **Step 5: Add the PostGIS migration**

Create `supabase/migrations/20260927000001_extensions.sql`:

```sql
create extension if not exists postgis with schema extensions;
```

- [ ] **Step 6: Add the test helpers**

Create `supabase/test-helpers/helpers.sql`:

```sql
-- Test-only helpers. Loaded as local seed data (see config.toml); never deployed.
-- Bodies are plpgsql so table references resolve at call time, not load time.
create schema if not exists tests;
grant usage on schema tests to anon, authenticated;

create or replace function tests.create_auth_user(p_email text)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_id uuid := gen_random_uuid();
begin
  insert into auth.users (id, email) values (v_id, p_email);
  return v_id;
end;
$$;

create or replace function tests.auth_user_id(p_email text)
returns uuid
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  return (select id from auth.users where email = p_email);
end;
$$;

create or replace function tests.create_user(p_username text, p_private boolean default false)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_id uuid := tests.create_auth_user(p_username || '@test.local');
begin
  insert into public.profiles (id, username, display_name, is_private)
  values (v_id, p_username, p_username, p_private);
  return v_id;
end;
$$;

create or replace function tests.user_id(p_username text)
returns uuid
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  return (select id from public.profiles where username = p_username);
end;
$$;

create or replace function tests.create_place(
  p_google_place_id text,
  p_name text,
  p_lat double precision,
  p_lng double precision,
  p_closed boolean default false
)
returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_id uuid;
begin
  insert into public.places (google_place_id, name, location, is_closed)
  values (
    p_google_place_id,
    p_name,
    extensions.st_setsrid(extensions.st_makepoint(p_lng, p_lat), 4326)::extensions.geography,
    p_closed
  )
  returning id into v_id;
  return v_id;
end;
$$;

create or replace function tests.place_id(p_google_place_id text)
returns uuid
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  return (select id from public.places where google_place_id = p_google_place_id);
end;
$$;

create or replace function tests.authenticate_as(p_user_id uuid)
returns void
language plpgsql
as $$
begin
  perform set_config(
    'request.jwt.claims',
    json_build_object('sub', p_user_id, 'role', 'authenticated')::text,
    true
  );
  perform set_config('role', 'authenticated', true);
end;
$$;

create or replace function tests.as_anon()
returns void
language plpgsql
as $$
begin
  perform set_config('request.jwt.claims', '', true);
  perform set_config('role', 'anon', true);
end;
$$;
```

Create `supabase/seed.sql`:

```sql
-- Local development seed data. Intentionally empty for now.
```

In `supabase/config.toml`, find the `[db.seed]` section and set:

```toml
[db.seed]
enabled = true
sql_paths = ["./seed.sql", "./test-helpers/helpers.sql"]
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
npm run test:db
```

Expected: `01_smoke.test.sql .. ok`, `All tests successful.`

- [ ] **Step 8: Verify the Next.js app still builds**

```bash
npm run build
```

Expected: build completes without errors.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "chore: scaffold Next.js app with Supabase, PostGIS and pgTAP test helpers"
```

---

### Task 2: Profiles and reserved usernames

**Files:**
- Create: `supabase/migrations/20260927000002_profiles.sql`
- Test: `supabase/tests/02_profiles.test.sql`

**Interfaces:**
- Consumes: `tests.*` helpers (Task 1).
- Produces: table `public.profiles (id uuid pk → auth.users on delete cascade, username text unique, display_name text, avatar_url text, locale text, is_private boolean, created_at timestamptz)`; table `public.reserved_usernames (username text pk)`; error `username_reserved`.

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/02_profiles.test.sql`:

```sql
begin;
create extension if not exists pgtap with schema extensions;
select plan(8);

select has_table('public', 'profiles', 'profiles table exists');

select tests.create_user('alice');

select tests.as_anon();
select results_eq(
  $$ select username from public.profiles $$,
  $$ values ('alice'::text) $$,
  'signed-out visitors can read profiles'
);
reset role;

-- Onboarding: a signed-in user without a profile creates their own.
select tests.create_auth_user('bob@test.local');
select tests.authenticate_as(tests.auth_user_id('bob@test.local'));

select lives_ok(
  $$ insert into public.profiles (id, username, display_name)
     values (tests.auth_user_id('bob@test.local'), 'bob', 'Bob') $$,
  'user can create their own profile'
);

select throws_ok(
  $$ insert into public.profiles (id, username, display_name)
     values (tests.user_id('alice'), 'mallory', 'Mallory') $$,
  '42501', null,
  'user cannot create a profile for someone else'
);

reset role;
select tests.create_auth_user('carol@test.local');
select tests.authenticate_as(tests.auth_user_id('carol@test.local'));

select throws_ok(
  $$ insert into public.profiles (id, username, display_name)
     values (tests.auth_user_id('carol@test.local'), 'Carol X', 'Carol') $$,
  '23514', null,
  'username must match ^[a-z0-9_]{3,30}$'
);

select throws_ok(
  $$ insert into public.profiles (id, username, display_name)
     values (tests.auth_user_id('carol@test.local'), 'admin', 'Carol') $$,
  'P0001', 'username_reserved',
  'reserved usernames are rejected'
);

select throws_ok(
  $$ insert into public.profiles (id, username, display_name, locale)
     values (tests.auth_user_id('carol@test.local'), 'carol', 'Carol', 'fr') $$,
  '23514', null,
  'locale must be de or en'
);

-- Bob tries to edit Alice's profile: silently affects zero rows.
select tests.authenticate_as(tests.user_id('bob'));
update public.profiles set display_name = 'hacked' where username = 'alice';
update public.profiles set display_name = 'Bobby' where username = 'bob';
reset role;

select results_eq(
  $$ select username, display_name from public.profiles order by username $$,
  $$ values ('alice'::text, 'alice'::text), ('bob', 'Bobby') $$,
  'users can update only their own profile'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:db`
Expected: `02_profiles.test.sql` FAILS (`profiles table exists` fails; later statements error with `relation "public.profiles" does not exist`).

- [ ] **Step 3: Write the migration**

Create `supabase/migrations/20260927000002_profiles.sql`:

```sql
create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  username text not null unique check (username ~ '^[a-z0-9_]{3,30}$'),
  display_name text not null check (char_length(display_name) between 1 and 50),
  avatar_url text,
  locale text not null default 'de' check (locale in ('de', 'en')),
  is_private boolean not null default false,
  created_at timestamptz not null default now()
);

create table public.reserved_usernames (
  username text primary key
);

-- RLS on with no policies: clients cannot read or write this table.
alter table public.reserved_usernames enable row level security;

insert into public.reserved_usernames (username) values
  ('about'), ('admin'), ('administrator'), ('api'), ('discover'), ('help'),
  ('login'), ('logout'), ('moderator'), ('privacy'), ('root'), ('settings'),
  ('signup'), ('spot'), ('staff'), ('support'), ('terms'), ('www');

create function public.check_username_not_reserved()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if exists (select 1 from public.reserved_usernames where username = new.username) then
    raise exception 'username_reserved';
  end if;
  return new;
end;
$$;

create trigger profiles_username_not_reserved
  before insert or update of username on public.profiles
  for each row execute function public.check_username_not_reserved();

alter table public.profiles enable row level security;

create policy "profiles are readable by everyone"
  on public.profiles for select
  to anon, authenticated
  using (true);

create policy "users create their own profile"
  on public.profiles for insert
  to authenticated
  with check (id = (select auth.uid()));

create policy "users update their own profile"
  on public.profiles for update
  to authenticated
  using (id = (select auth.uid()))
  with check (id = (select auth.uid()));
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:db`
Expected: all files ok, `All tests successful.`

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20260927000002_profiles.sql supabase/tests/02_profiles.test.sql
git commit -m "feat(db): profiles with reserved usernames and RLS"
```

---

### Task 3: Follows (requests, approval, private→public, counts, rate limit)

**Files:**
- Create: `supabase/migrations/20260927000003_follows.sql`
- Test: `supabase/tests/03_follows.test.sql`

**Interfaces:**
- Consumes: `public.profiles` (Task 2), `tests.*` helpers.
- Produces: table `public.follows (follower_id uuid, followee_id uuid, status text 'pending'|'accepted', created_at timestamptz)`, pk `(follower_id, followee_id)`; function `public.follow_counts(p_user_id uuid) returns table (followers bigint, following bigint)`; error `rate_limited`. Clients insert follows with only `follower_id` and `followee_id`; the database decides `status`. Only `status` is client-updatable (followee approves by setting `accepted`). Unfollow / reject / remove follower = delete.

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/03_follows.test.sql`:

```sql
begin;
create extension if not exists pgtap with schema extensions;
select plan(19);

select tests.create_user('alice');
select tests.create_user('bob');
select tests.create_user('carol', true);
select tests.create_user('dave');
select tests.create_user('erin', true);

-- Following and requesting
select tests.authenticate_as(tests.user_id('bob'));

select lives_ok(
  $$ insert into public.follows (follower_id, followee_id)
     values (tests.user_id('bob'), tests.user_id('alice')) $$,
  'bob can follow public alice'
);

select lives_ok(
  $$ insert into public.follows (follower_id, followee_id, status)
     values (tests.user_id('bob'), tests.user_id('carol'), 'accepted') $$,
  'bob can request to follow private carol'
);

select results_eq(
  $$ select status from public.follows
     where follower_id = tests.user_id('bob') order by status $$,
  $$ values ('accepted'::text), ('pending') $$,
  'public follow is accepted; private follow is pending even if the client sends accepted'
);

select throws_ok(
  $$ insert into public.follows (follower_id, followee_id)
     values (tests.user_id('alice'), tests.user_id('dave')) $$,
  '42501', null,
  'cannot create a follow on behalf of someone else'
);

select throws_ok(
  $$ insert into public.follows (follower_id, followee_id)
     values (tests.user_id('bob'), tests.user_id('bob')) $$,
  '23514', null,
  'cannot follow yourself'
);

-- Approval
select lives_ok(
  $$ update public.follows set status = 'accepted'
     where follower_id = tests.user_id('bob') and followee_id = tests.user_id('carol') $$,
  'follower approving their own request is a silent no-op'
);

select tests.authenticate_as(tests.user_id('carol'));

select is(
  (select status from public.follows
   where follower_id = tests.user_id('bob') and followee_id = tests.user_id('carol')),
  'pending',
  'request is still pending after the follower tried to approve it'
);

select lives_ok(
  $$ update public.follows set status = 'accepted'
     where follower_id = tests.user_id('bob') and followee_id = tests.user_id('carol') $$,
  'followee can approve a request'
);

select is(
  (select status from public.follows
   where follower_id = tests.user_id('bob') and followee_id = tests.user_id('carol')),
  'accepted',
  'request is accepted after approval'
);

-- Private -> public accepts pending requests
select tests.authenticate_as(tests.user_id('dave'));

select lives_ok(
  $$ insert into public.follows (follower_id, followee_id)
     values (tests.user_id('dave'), tests.user_id('erin')) $$,
  'dave requests to follow private erin'
);

select tests.authenticate_as(tests.user_id('erin'));

select lives_ok(
  $$ update public.profiles set is_private = false where id = tests.user_id('erin') $$,
  'erin makes her profile public'
);

select is(
  (select status from public.follows
   where follower_id = tests.user_id('dave') and followee_id = tests.user_id('erin')),
  'accepted',
  'pending requests are accepted when a profile becomes public'
);

-- Visibility of follow relationships
select tests.authenticate_as(tests.user_id('dave'));

select results_eq(
  $$ select p.username from public.follows f
     join public.profiles p on p.id = f.followee_id
     where f.follower_id = tests.user_id('bob') $$,
  $$ values ('alice'::text) $$,
  'strangers see follows between public profiles only'
);

select results_eq(
  $$ select followers, following from public.follow_counts(tests.user_id('carol')) $$,
  $$ values (1::bigint, 0::bigint) $$,
  'follow counts are available for private profiles'
);

-- Unfollow and remove follower
select tests.authenticate_as(tests.user_id('bob'));

select lives_ok(
  $$ delete from public.follows
     where follower_id = tests.user_id('bob') and followee_id = tests.user_id('alice') $$,
  'bob can unfollow alice'
);

select is(
  (select count(*) from public.follows
   where follower_id = tests.user_id('bob') and followee_id = tests.user_id('alice')),
  0::bigint,
  'unfollow removes the follow'
);

select tests.authenticate_as(tests.user_id('carol'));

select lives_ok(
  $$ delete from public.follows
     where follower_id = tests.user_id('bob') and followee_id = tests.user_id('carol') $$,
  'carol can remove bob as a follower'
);

select is(
  (select count(*) from public.follows
   where follower_id = tests.user_id('bob') and followee_id = tests.user_id('carol')),
  0::bigint,
  'removing a follower deletes the follow'
);

-- Rate limit: 200 follows per 24 hours
reset role;
do $$
declare
  i integer;
begin
  for i in 1..201 loop
    perform tests.create_user('fan' || i);
  end loop;
  insert into public.follows (follower_id, followee_id)
  select tests.user_id('alice'), id
  from public.profiles
  where username like 'fan%' and username <> 'fan201';
end;
$$;

select tests.authenticate_as(tests.user_id('alice'));

select throws_ok(
  $$ insert into public.follows (follower_id, followee_id)
     values (tests.user_id('alice'), tests.user_id('fan201')) $$,
  'P0001', 'rate_limited',
  'the 201st follow within 24 hours is rejected'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:db`
Expected: `03_follows.test.sql` FAILS with `relation "public.follows" does not exist`.

- [ ] **Step 3: Write the migration**

Create `supabase/migrations/20260927000003_follows.sql`:

```sql
create table public.follows (
  follower_id uuid not null references public.profiles (id) on delete cascade,
  followee_id uuid not null references public.profiles (id) on delete cascade,
  status text not null default 'pending' check (status in ('pending', 'accepted')),
  created_at timestamptz not null default now(),
  primary key (follower_id, followee_id),
  check (follower_id <> followee_id)
);

create index follows_followee_idx on public.follows (followee_id, status);

-- The database, not the client, decides whether a follow is accepted.
create function public.follows_before_insert()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (
    select count(*) from public.follows
    where follower_id = new.follower_id
      and created_at > now() - interval '24 hours'
  ) >= 200 then
    raise exception 'rate_limited';
  end if;

  new.status := case
    when (select is_private from public.profiles where id = new.followee_id) then 'pending'
    else 'accepted'
  end;
  new.created_at := now();
  return new;
end;
$$;

create trigger follows_before_insert
  before insert on public.follows
  for each row execute function public.follows_before_insert();

create function public.accept_pending_follows_when_public()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.follows
  set status = 'accepted'
  where followee_id = new.id and status = 'pending';
  return new;
end;
$$;

create trigger profiles_became_public
  after update of is_private on public.profiles
  for each row
  when (old.is_private and not new.is_private)
  execute function public.accept_pending_follows_when_public();

-- Counts are public even for private profiles.
create function public.follow_counts(p_user_id uuid)
returns table (followers bigint, following bigint)
language sql
stable
security definer
set search_path = ''
as $$
  select
    (select count(*) from public.follows
     where followee_id = p_user_id and status = 'accepted'),
    (select count(*) from public.follows
     where follower_id = p_user_id and status = 'accepted');
$$;

alter table public.follows enable row level security;

create policy "follows are visible to both parties, and publicly between public profiles"
  on public.follows for select
  to anon, authenticated
  using (
    (select auth.uid()) in (follower_id, followee_id)
    or (
      status = 'accepted'
      and exists (select 1 from public.profiles p where p.id = followee_id and not p.is_private)
      and exists (select 1 from public.profiles p where p.id = follower_id and not p.is_private)
    )
  );

create policy "users follow as themselves"
  on public.follows for insert
  to authenticated
  with check (follower_id = (select auth.uid()));

-- Only the status column is client-updatable, and only by the followee, only to accept.
revoke update on public.follows from anon, authenticated;
grant update (status) on public.follows to authenticated;

create policy "followees approve requests"
  on public.follows for update
  to authenticated
  using (followee_id = (select auth.uid()))
  with check (followee_id = (select auth.uid()) and status = 'accepted');

create policy "either party can end a follow"
  on public.follows for delete
  to authenticated
  using ((select auth.uid()) in (follower_id, followee_id));
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:db`
Expected: `All tests successful.`

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20260927000003_follows.sql supabase/tests/03_follows.test.sql
git commit -m "feat(db): follows with private requests, approval, counts and rate limit"
```

---

### Task 4: Tags and places

**Files:**
- Create: `supabase/migrations/20260927000004_tags_places.sql`
- Test: `supabase/tests/04_tags_places.test.sql`

**Interfaces:**
- Consumes: `tests.create_place`, `tests.as_anon`, `tests.authenticate_as`, `tests.create_user`.
- Produces: table `public.tags (slug text pk, label_de text, label_en text, sort_order integer, active boolean)` seeded with 16 tags; table `public.places (id uuid pk, google_place_id text unique, name text, address text, location extensions.geography(point, 4326), is_closed boolean, details_refreshed_at timestamptz)`. Both are read-only for clients; places are written only by the server with the service role (Plan 3).

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/04_tags_places.test.sql`:

```sql
begin;
create extension if not exists pgtap with schema extensions;
select plan(6);

select tests.create_user('alice');
select tests.create_place('g-1', 'One', 52.52, 13.405);

select tests.as_anon();

select is(
  (select count(*) from public.tags where active),
  16::bigint,
  'the 16 launch tags are seeded and readable by visitors'
);

select is(
  (select count(*) from public.places),
  1::bigint,
  'places are readable by visitors'
);

select tests.authenticate_as(tests.user_id('alice'));

select throws_ok(
  $$ insert into public.tags (slug, label_de, label_en, sort_order)
     values ('new-tag', 'Neu', 'New', 999) $$,
  '42501', null,
  'users cannot create tags'
);

select throws_ok(
  $$ insert into public.places (google_place_id, name, location)
     values ('g-x', 'X', 'SRID=4326;POINT(13.4 52.5)'::extensions.geography) $$,
  '42501', null,
  'users cannot create places directly'
);

reset role;

select throws_ok(
  $$ select tests.create_place('g-1', 'Duplicate', 52.52, 13.405) $$,
  '23505', null,
  'google_place_id is unique'
);

select results_eq(
  $$ select label_en, label_de from public.tags where slug = 'date-night' $$,
  $$ values ('Date night'::text, 'Date Night'::text) $$,
  'tags have English and German labels'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:db`
Expected: `04_tags_places.test.sql` FAILS with `relation "public.places" does not exist`.

- [ ] **Step 3: Write the migration**

Create `supabase/migrations/20260927000004_tags_places.sql`:

```sql
create table public.tags (
  slug text primary key check (slug ~ '^[a-z0-9-]+$'),
  label_de text not null,
  label_en text not null,
  sort_order integer not null,
  active boolean not null default true
);

alter table public.tags enable row level security;

create policy "tags are readable by everyone"
  on public.tags for select
  to anon, authenticated
  using (true);

insert into public.tags (slug, label_en, label_de, sort_order) values
  ('date-night',       'Date night',       'Date Night',          10),
  ('quiet-drinks',     'Quiet drinks',     'Ruhige Drinks',       20),
  ('big-group',        'Big group',        'Große Gruppe',        30),
  ('cheap-eats',       'Cheap eats',       'Günstig essen',       40),
  ('late-night',       'Late night',       'Spät geöffnet',       50),
  ('outdoor-seating',  'Outdoor seating',  'Draußen sitzen',      60),
  ('brunch',           'Brunch',           'Brunch',              70),
  ('business-lunch',   'Business lunch',   'Geschäftsessen',      80),
  ('cocktails',        'Cocktails',        'Cocktails',           90),
  ('wine',             'Wine',             'Wein',               100),
  ('craft-beer',       'Craft beer',       'Craft Beer',         110),
  ('family-friendly',  'Family-friendly',  'Familienfreundlich', 120),
  ('solo',             'Solo',             'Allein',             130),
  ('special-occasion', 'Special occasion', 'Besonderer Anlass',  140),
  ('quick-bite',       'Quick bite',       'Schneller Snack',    150),
  ('live-music',       'Live music',       'Livemusik',          160);

-- Google ToS: only google_place_id may be stored permanently; the other
-- fields are a cache refreshed by a scheduled job (Plan 3).
create table public.places (
  id uuid primary key default gen_random_uuid(),
  google_place_id text not null unique,
  name text not null,
  address text,
  location extensions.geography(point, 4326) not null,
  is_closed boolean not null default false,
  details_refreshed_at timestamptz not null default now()
);

create index places_location_idx on public.places using gist (location);

alter table public.places enable row level security;

create policy "places are readable by everyone"
  on public.places for select
  to anon, authenticated
  using (true);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:db`
Expected: `All tests successful.`

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20260927000004_tags_places.sql supabase/tests/04_tags_places.test.sql
git commit -m "feat(db): seeded mood tags and places with PostGIS location"
```

---

### Task 5: Recommendations with privacy, validation and rate limit

**Files:**
- Create: `supabase/migrations/20260927000005_recommendations.sql`
- Test: `supabase/tests/05_recommendations.test.sql`

**Interfaces:**
- Consumes: `public.profiles`, `public.follows`, `public.tags`, `public.places`, `tests.*`.
- Produces: table `public.recommendations (id uuid pk, user_id uuid, place_id uuid, tags text[], note text, created_at timestamptz, updated_at timestamptz)`, unique `(user_id, place_id)`; function `public.can_see_picks_of(p_author uuid) returns boolean`; errors `invalid_tags`, `rate_limited`.

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/05_recommendations.test.sql`:

```sql
begin;
create extension if not exists pgtap with schema extensions;
select plan(18);

do $$
begin
  perform tests.create_user('alice');
  perform tests.create_user('bob');
  perform tests.create_user('carol', true);
  perform tests.create_user('dave');
  perform tests.create_user('erin');

  insert into public.follows (follower_id, followee_id) values
    (tests.user_id('dave'), tests.user_id('carol')),
    (tests.user_id('erin'), tests.user_id('carol'));
  update public.follows set status = 'accepted'
  where follower_id = tests.user_id('dave');

  perform tests.create_place('g-1', 'One', 52.52, 13.405);
  perform tests.create_place('g-2', 'Two', 52.53, 13.405);

  insert into public.recommendations (user_id, place_id, tags, note) values
    (tests.user_id('alice'), tests.place_id('g-1'), array['date-night'], 'Ask for the corner table'),
    (tests.user_id('carol'), tests.place_id('g-1'), array['cocktails'], null);

  update public.tags set active = false where slug = 'live-music';
end;
$$;

-- Visibility
select tests.as_anon();
select results_eq(
  $$ select p.username from public.recommendations r
     join public.profiles p on p.id = r.user_id order by 1 $$,
  $$ values ('alice'::text) $$,
  'visitors see only public users'' picks'
);

select tests.authenticate_as(tests.user_id('bob'));
select results_eq(
  $$ select p.username from public.recommendations r
     join public.profiles p on p.id = r.user_id order by 1 $$,
  $$ values ('alice'::text) $$,
  'strangers cannot see a private user''s picks'
);

select tests.authenticate_as(tests.user_id('erin'));
select results_eq(
  $$ select p.username from public.recommendations r
     join public.profiles p on p.id = r.user_id order by 1 $$,
  $$ values ('alice'::text) $$,
  'pending followers cannot see a private user''s picks'
);

select tests.authenticate_as(tests.user_id('dave'));
select results_eq(
  $$ select p.username from public.recommendations r
     join public.profiles p on p.id = r.user_id order by 1 $$,
  $$ values ('alice'::text), ('carol') $$,
  'accepted followers see a private user''s picks'
);

select tests.authenticate_as(tests.user_id('carol'));
select results_eq(
  $$ select p.username from public.recommendations r
     join public.profiles p on p.id = r.user_id order by 1 $$,
  $$ values ('alice'::text), ('carol') $$,
  'private users see their own picks'
);

-- Writing
select tests.authenticate_as(tests.user_id('bob'));

select lives_ok(
  $$ insert into public.recommendations (user_id, place_id, tags, note)
     values (tests.user_id('bob'), tests.place_id('g-2'), array['date-night', 'cocktails'], 'Great negroni') $$,
  'user can recommend a place with valid tags'
);

select throws_ok(
  $$ insert into public.recommendations (user_id, place_id, tags)
     values (tests.user_id('bob'), tests.place_id('g-1'), array[]::text[]) $$,
  '23514', null,
  'at least one tag is required'
);

select throws_ok(
  $$ insert into public.recommendations (user_id, place_id, tags)
     values (tests.user_id('bob'), tests.place_id('g-1'), array['date-night', 'cocktails', 'wine', 'brunch']) $$,
  '23514', null,
  'at most three tags are allowed'
);

select throws_ok(
  $$ insert into public.recommendations (user_id, place_id, tags)
     values (tests.user_id('bob'), tests.place_id('g-1'), array['not-a-tag']) $$,
  'P0001', 'invalid_tags',
  'unknown tags are rejected'
);

select throws_ok(
  $$ insert into public.recommendations (user_id, place_id, tags)
     values (tests.user_id('bob'), tests.place_id('g-1'), array['wine', 'wine']) $$,
  'P0001', 'invalid_tags',
  'duplicate tags are rejected'
);

select throws_ok(
  $$ insert into public.recommendations (user_id, place_id, tags)
     values (tests.user_id('bob'), tests.place_id('g-1'), array['live-music']) $$,
  'P0001', 'invalid_tags',
  'inactive tags are rejected'
);

select throws_ok(
  $$ insert into public.recommendations (user_id, place_id, tags)
     values (tests.user_id('bob'), tests.place_id('g-2'), array['wine']) $$,
  '23505', null,
  'one recommendation per user per place'
);

select throws_ok(
  $$ insert into public.recommendations (user_id, place_id, tags)
     values (tests.user_id('alice'), tests.place_id('g-2'), array['wine']) $$,
  '42501', null,
  'cannot recommend on behalf of someone else'
);

select throws_ok(
  $$ insert into public.recommendations (user_id, place_id, tags, note)
     values (tests.user_id('bob'), tests.place_id('g-1'), array['wine'], repeat('x', 501)) $$,
  '23514', null,
  'note is limited to 500 characters'
);

select lives_ok(
  $$ update public.recommendations set tags = array['wine'], note = 'Changed'
     where user_id = tests.user_id('bob') and place_id = tests.place_id('g-2') $$,
  'user can edit their own recommendation'
);

select lives_ok(
  $$ update public.recommendations set note = 'hacked'
     where user_id = tests.user_id('alice') $$,
  'editing someone else''s recommendation is a silent no-op'
);

reset role;

select is(
  (select note from public.recommendations where user_id = tests.user_id('alice')),
  'Ask for the corner table',
  'someone else''s recommendation is unchanged'
);

-- Rate limit: 50 recommendations per 24 hours
do $$
declare
  i integer;
begin
  for i in 1..51 loop
    perform tests.create_place('bulk-' || i, 'Bulk ' || i, 52.5, 13.4);
  end loop;
  insert into public.recommendations (user_id, place_id, tags)
  select tests.user_id('erin'), id, array['brunch']
  from public.places
  where google_place_id like 'bulk-%' and google_place_id <> 'bulk-51';
end;
$$;

select tests.authenticate_as(tests.user_id('erin'));

select throws_ok(
  $$ insert into public.recommendations (user_id, place_id, tags)
     values (tests.user_id('erin'), tests.place_id('bulk-51'), array['brunch']) $$,
  'P0001', 'rate_limited',
  'the 51st recommendation within 24 hours is rejected'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:db`
Expected: `05_recommendations.test.sql` FAILS with `relation "public.recommendations" does not exist`.

- [ ] **Step 3: Write the migration**

Create `supabase/migrations/20260927000005_recommendations.sql`:

```sql
create table public.recommendations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles (id) on delete cascade,
  place_id uuid not null references public.places (id) on delete cascade,
  tags text[] not null check (cardinality(tags) between 1 and 3),
  note text check (char_length(note) <= 500),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (user_id, place_id)
);

create index recommendations_tags_idx on public.recommendations using gin (tags);
create index recommendations_place_idx on public.recommendations (place_id);

create function public.recommendations_before_write()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  -- Every tag must exist, be active, and appear once (duplicates lower the count).
  if (
    select count(*) from public.tags
    where slug = any (new.tags) and active
  ) <> cardinality(new.tags) then
    raise exception 'invalid_tags';
  end if;

  if tg_op = 'INSERT' then
    if (
      select count(*) from public.recommendations
      where user_id = new.user_id
        and created_at > now() - interval '24 hours'
    ) >= 50 then
      raise exception 'rate_limited';
    end if;
    new.created_at := now();
  end if;

  new.updated_at := now();
  return new;
end;
$$;

create trigger recommendations_before_write
  before insert or update on public.recommendations
  for each row execute function public.recommendations_before_write();

-- The single definition of "who may see whose picks".
create function public.can_see_picks_of(p_author uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(p_author = auth.uid(), false)
    or exists (
      select 1 from public.profiles
      where id = p_author and not is_private
    )
    or exists (
      select 1 from public.follows
      where follower_id = auth.uid()
        and followee_id = p_author
        and status = 'accepted'
    );
$$;

alter table public.recommendations enable row level security;

create policy "picks are visible per the author's privacy"
  on public.recommendations for select
  to anon, authenticated
  using (public.can_see_picks_of(user_id));

create policy "users recommend as themselves"
  on public.recommendations for insert
  to authenticated
  with check (user_id = (select auth.uid()));

create policy "users edit their own recommendations"
  on public.recommendations for update
  to authenticated
  using (user_id = (select auth.uid()))
  with check (user_id = (select auth.uid()));

create policy "users delete their own recommendations"
  on public.recommendations for delete
  to authenticated
  using (user_id = (select auth.uid()));
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:db`
Expected: `All tests successful.`

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20260927000005_recommendations.sql supabase/tests/05_recommendations.test.sql
git commit -m "feat(db): recommendations with tag validation, privacy RLS and rate limit"
```

---

### Task 6: Reports and account deletion

**Files:**
- Create: `supabase/migrations/20260927000006_reports.sql`
- Test: `supabase/tests/06_reports_deletion.test.sql`

**Interfaces:**
- Consumes: all tables above, `tests.*`.
- Produces: table `public.reports (id uuid pk, reporter_id uuid, target_type text 'profile'|'recommendation', target_id uuid, reason text, created_at timestamptz)`, insert-only for clients. Verified guarantee: deleting a row from `auth.users` removes that user's profile, follows (both directions), recommendations and filed reports. (The email to the owner on new reports is Plan 3.)

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/06_reports_deletion.test.sql`:

```sql
begin;
create extension if not exists pgtap with schema extensions;
select plan(8);

do $$
begin
  perform tests.create_user('alice');
  perform tests.create_user('bob');
  perform tests.create_user('carol', true);

  insert into public.follows (follower_id, followee_id) values
    (tests.user_id('bob'), tests.user_id('carol')),
    (tests.user_id('carol'), tests.user_id('alice'));
  update public.follows set status = 'accepted';

  perform tests.create_place('g-1', 'One', 52.52, 13.405);
  insert into public.recommendations (user_id, place_id, tags)
  values (tests.user_id('carol'), tests.place_id('g-1'), array['wine']);

  insert into public.reports (reporter_id, target_type, target_id, reason)
  values (tests.user_id('carol'), 'profile', tests.user_id('alice'), 'Spam');
end;
$$;

-- Reports
select tests.authenticate_as(tests.user_id('bob'));

select lives_ok(
  $$ insert into public.reports (reporter_id, target_type, target_id, reason)
     values (tests.user_id('bob'), 'profile', tests.user_id('alice'), 'Fake account') $$,
  'user can file a report'
);

select throws_ok(
  $$ insert into public.reports (reporter_id, target_type, target_id, reason)
     values (tests.user_id('alice'), 'profile', tests.user_id('bob'), 'Framed') $$,
  '42501', null,
  'cannot file a report as someone else'
);

select throws_ok(
  $$ insert into public.reports (reporter_id, target_type, target_id, reason)
     values (tests.user_id('bob'), 'profile', tests.user_id('alice'), '') $$,
  '23514', null,
  'a reason is required'
);

select is(
  (select count(*) from public.reports),
  0::bigint,
  'users cannot read reports'
);

-- Account deletion cascades
reset role;
select set_config('test.carol', tests.user_id('carol')::text, true);
delete from auth.users where id = current_setting('test.carol')::uuid;

select is(
  (select count(*) from public.profiles where id = current_setting('test.carol')::uuid),
  0::bigint,
  'deleting the account deletes the profile'
);

select is(
  (select count(*) from public.follows
   where current_setting('test.carol')::uuid in (follower_id, followee_id)),
  0::bigint,
  'deleting the account deletes follows in both directions'
);

select is(
  (select count(*) from public.recommendations where user_id = current_setting('test.carol')::uuid),
  0::bigint,
  'deleting the account deletes recommendations'
);

select is(
  (select count(*) from public.reports where reporter_id = current_setting('test.carol')::uuid),
  0::bigint,
  'deleting the account deletes reports filed by the user'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:db`
Expected: `06_reports_deletion.test.sql` FAILS with `relation "public.reports" does not exist`.

- [ ] **Step 3: Write the migration**

Create `supabase/migrations/20260927000006_reports.sql`:

```sql
create table public.reports (
  id uuid primary key default gen_random_uuid(),
  reporter_id uuid not null references public.profiles (id) on delete cascade,
  target_type text not null check (target_type in ('profile', 'recommendation')),
  target_id uuid not null,
  reason text not null check (char_length(reason) between 1 and 500),
  created_at timestamptz not null default now()
);

-- Insert-only for clients; reports are read by the owner via the dashboard.
alter table public.reports enable row level security;

create policy "users file reports as themselves"
  on public.reports for insert
  to authenticated
  with check (reporter_id = (select auth.uid()));
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:db`
Expected: `All tests successful.`

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20260927000006_reports.sql supabase/tests/06_reports_deletion.test.sql
git commit -m "feat(db): insert-only reports; verify account deletion cascades"
```

---

### Task 7: Discover function

**Files:**
- Create: `supabase/migrations/20260927000007_discover.sql`
- Test: `supabase/tests/07_discover.test.sql`

**Interfaces:**
- Consumes: all tables above, `tests.*`.
- Produces: `public.discover(p_tag text, p_lat double precision, p_lng double precision, p_radius_m integer default 2000, p_scope text default 'following', p_limit integer default 20, p_offset integer default 0) returns table (place_id uuid, google_place_id text, name text, address text, lat double precision, lng double precision, distance_m double precision, recommender_count bigint, recommenders jsonb, tags text[])`. `recommenders` is a JSON array of up to 3 `{id, username, display_name, avatar_url}` objects, followed users first. Callable by signed-in users only. Errors: `invalid_scope`, `invalid_radius`, `invalid_page`. Plan 3's UI calls it via `supabase.rpc('discover', {...})`.

- [ ] **Step 1: Write the failing test**

Create `supabase/tests/07_discover.test.sql`. Distances are measured from (52.52, 13.405); 0.0009° latitude ≈ 100 m.

```sql
begin;
create extension if not exists pgtap with schema extensions;
select plan(11);

do $$
begin
  perform tests.create_user('me');
  perform tests.create_user('friend1');
  perform tests.create_user('friend2');
  perform tests.create_user('stranger');
  perform tests.create_user('hidden', true);

  insert into public.follows (follower_id, followee_id) values
    (tests.user_id('me'), tests.user_id('friend1')),
    (tests.user_id('me'), tests.user_id('friend2'));

  perform tests.create_place('g-a', 'A', 52.5245, 13.405);        -- 500 m
  perform tests.create_place('g-b', 'B', 52.5218, 13.405);        -- 200 m
  perform tests.create_place('g-c', 'C', 52.5290, 13.405);        -- 1 km
  perform tests.create_place('g-d', 'D', 52.5650, 13.405);        -- 5 km
  perform tests.create_place('g-e', 'E', 52.5227, 13.405, true);  -- 300 m, closed
  perform tests.create_place('g-f', 'F', 52.5227, 13.405);        -- 300 m
  perform tests.create_place('g-g', 'G', 52.5236, 13.405);        -- 400 m

  insert into public.recommendations (user_id, place_id, tags) values
    (tests.user_id('friend1'),  tests.place_id('g-a'), array['date-night']),
    (tests.user_id('friend2'),  tests.place_id('g-a'), array['date-night', 'cocktails']),
    (tests.user_id('friend1'),  tests.place_id('g-b'), array['date-night']),
    (tests.user_id('me'),       tests.place_id('g-b'), array['date-night']),
    (tests.user_id('friend1'),  tests.place_id('g-c'), array['brunch']),
    (tests.user_id('friend1'),  tests.place_id('g-d'), array['date-night']),
    (tests.user_id('friend2'),  tests.place_id('g-e'), array['date-night']),
    (tests.user_id('stranger'), tests.place_id('g-f'), array['date-night']),
    (tests.user_id('hidden'),   tests.place_id('g-g'), array['date-night']);
end;
$$;

select tests.authenticate_as(tests.user_id('me'));

select results_eq(
  $$ select name from public.discover('date-night', 52.52, 13.405) $$,
  $$ values ('A'::text), ('B') $$,
  'following scope: followed users'' open places within 2 km, most recommended first'
);

select is(
  (select recommender_count from public.discover('date-night', 52.52, 13.405) where name = 'A'),
  2::bigint,
  'recommender_count counts distinct recommenders'
);

select is(
  (select recommender_count from public.discover('date-night', 52.52, 13.405) where name = 'B'),
  1::bigint,
  'the caller''s own recommendation is not counted'
);

select is(
  (select jsonb_array_length(recommenders) from public.discover('date-night', 52.52, 13.405) where name = 'A'),
  2,
  'recommenders lists who recommended the place'
);

select is(
  (select tags from public.discover('date-night', 52.52, 13.405) where name = 'A'),
  array['cocktails', 'date-night'],
  'tags are aggregated across recommenders, sorted'
);

select results_eq(
  $$ select name from public.discover('date-night', 52.52, 13.405, 10000) $$,
  $$ values ('A'::text), ('B'), ('D') $$,
  'a wider radius includes farther places'
);

select results_eq(
  $$ select name from public.discover('date-night', 52.52, 13.405, 2000, 'everyone') $$,
  $$ values ('A'::text), ('B'), ('F') $$,
  'everyone scope adds public users but never private non-followed users'
);

select results_eq(
  $$ select name from public.discover('brunch', 52.52, 13.405) $$,
  $$ values ('C'::text) $$,
  'results are filtered by tag'
);

select results_eq(
  $$ select name from public.discover('date-night', 52.52, 13.405, 2000, 'following', 1, 1) $$,
  $$ values ('B'::text) $$,
  'results are paginated'
);

select throws_ok(
  $$ select * from public.discover('date-night', 52.52, 13.405, 2000, 'nearby') $$,
  'P0001', 'invalid_scope',
  'unknown scopes are rejected'
);

select tests.as_anon();

select throws_ok(
  $$ select * from public.discover('date-night', 52.52, 13.405) $$,
  '42501', null,
  'signed-out visitors cannot call discover'
);

select * from finish();
rollback;
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:db`
Expected: `07_discover.test.sql` FAILS with `function public.discover(...) does not exist`.

- [ ] **Step 3: Write the migration**

Create `supabase/migrations/20260927000007_discover.sql`:

```sql
-- Security invoker: RLS on recommendations applies, so private users' picks
-- are only ever returned to their accepted followers.
create function public.discover(
  p_tag text,
  p_lat double precision,
  p_lng double precision,
  p_radius_m integer default 2000,
  p_scope text default 'following',
  p_limit integer default 20,
  p_offset integer default 0
)
returns table (
  place_id uuid,
  google_place_id text,
  name text,
  address text,
  lat double precision,
  lng double precision,
  distance_m double precision,
  recommender_count bigint,
  recommenders jsonb,
  tags text[]
)
language plpgsql
stable
security invoker
set search_path = ''
as $$
#variable_conflict use_column
declare
  v_me uuid := auth.uid();
  v_origin extensions.geography :=
    extensions.st_setsrid(extensions.st_makepoint(p_lng, p_lat), 4326)::extensions.geography;
begin
  if p_scope is null or p_scope not in ('following', 'everyone') then
    raise exception 'invalid_scope';
  end if;
  if p_radius_m is null or p_radius_m not between 100 and 50000 then
    raise exception 'invalid_radius';
  end if;
  if p_limit is null or p_limit not between 1 and 50 or p_offset is null or p_offset < 0 then
    raise exception 'invalid_page';
  end if;

  return query
  with candidates as (
    select v.user_id, v.place_id, v.tags, v.created_at, v.is_followed
    from (
      select
        r.user_id,
        r.place_id,
        r.tags,
        r.created_at,
        exists (
          select 1 from public.follows f
          where f.follower_id = v_me
            and f.followee_id = r.user_id
            and f.status = 'accepted'
        ) as is_followed
      from public.recommendations r
      where p_tag = any (r.tags)
        and r.user_id is distinct from v_me
    ) v
    where p_scope = 'everyone' or v.is_followed
  ),
  nearby as (
    select
      p.id,
      p.google_place_id,
      p.name,
      p.address,
      extensions.st_y(p.location::extensions.geometry) as lat,
      extensions.st_x(p.location::extensions.geometry) as lng,
      extensions.st_distance(p.location, v_origin) as distance_m
    from public.places p
    where not p.is_closed
      and extensions.st_dwithin(p.location, v_origin, p_radius_m)
  )
  select
    n.id,
    n.google_place_id,
    n.name,
    n.address,
    n.lat,
    n.lng,
    n.distance_m,
    count(*),
    (
      select jsonb_agg(
        jsonb_build_object(
          'id', pr.id,
          'username', pr.username,
          'display_name', pr.display_name,
          'avatar_url', pr.avatar_url
        )
        order by x.is_followed desc, x.created_at desc
      )
      from (
        select c2.user_id, c2.is_followed, c2.created_at
        from candidates c2
        where c2.place_id = n.id
        order by c2.is_followed desc, c2.created_at desc
        limit 3
      ) x
      join public.profiles pr on pr.id = x.user_id
    ),
    (
      select array_agg(distinct u.tag order by u.tag)
      from candidates c3
      cross join lateral unnest(c3.tags) as u(tag)
      where c3.place_id = n.id
    )
  from nearby n
  join candidates c on c.place_id = n.id
  group by n.id, n.google_place_id, n.name, n.address, n.lat, n.lng, n.distance_m
  order by count(*) desc, n.distance_m asc, n.id
  limit p_limit
  offset p_offset;
end;
$$;

revoke execute on function public.discover(text, double precision, double precision, integer, text, integer, integer)
  from public, anon;
grant execute on function public.discover(text, double precision, double precision, integer, text, integer, integer)
  to authenticated;
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:db`
Expected: `All tests successful.`

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20260927000007_discover.sql supabase/tests/07_discover.test.sql
git commit -m "feat(db): discover function ranking followed users' picks by count and distance"
```

---

### Task 8: Continuous integration

**Files:**
- Create: `.github/workflows/db-tests.yml`

**Interfaces:**
- Consumes: `npm run test:db` (Task 1).
- Produces: a GitHub Actions check named `Database tests` on every push and pull request.

- [ ] **Step 1: Write the workflow**

Create `.github/workflows/db-tests.yml`:

```yaml
name: Database tests

on:
  push:
  pull_request:

jobs:
  db:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: npm
      - run: npm ci
      - run: npx supabase db start
      - run: npm run test:db
```

- [ ] **Step 2: Verify the full suite locally one more time**

Run: `npm run test:db`
Expected: 7 test files, `All tests successful.`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/db-tests.yml
git commit -m "ci: run pgTAP database tests on push and pull request"
```

- [ ] **Step 4: Verify CI (only once the repo has a GitHub remote)**

Push the branch and confirm the `Database tests` check passes on GitHub.
