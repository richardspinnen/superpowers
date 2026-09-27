# "Spot" — Restaurant & Bar Recommendation App — Design

**Status:** Draft for review
**Date:** 2026-09-27
**Working title:** `spot` (final name TBD by product owner; nothing in the code depends on it)

## 1. Summary

A mobile-friendly web app (PWA) that helps guests decide where to eat or drink.
Users follow people — friends or curators — and see the restaurants and bars
those people recommend, filtered by mood/occasion and distance.

Core query: *"Show me spots near me tagged `date night` by people I follow."*

### Decisions

| Topic | Decision |
|---|---|
| Audience | Guests / diners |
| Primary value | Friends' picks; mood/occasion tags and curated picks built around it |
| Social model | Asymmetric follow; profiles can be private (follow requests need approval) |
| Curated picks | No separate feature — curators are accounts you follow |
| Spot data | Hybrid: places come from Google Places; users add recommendation + tags + note |
| Tags | Fixed list (~15–20), 1–3 per recommendation, plus optional free-text note |
| Platform | Web-first PWA; native app later |
| Geography | Location-agnostic code; launch focused on one city |
| Languages | German and English (i18n from day one) |
| Login | Email magic link, Google, Apple |
| Stack | Next.js (React) + Supabase (Postgres, PostGIS, Auth, RLS), EU region; Vercel hosting |

### Out of scope for v1

Star ratings, comments, likes, user photo uploads, "want to go" lists,
moderation tooling beyond a report button, native apps, push notifications.

## 2. Data model

All tables live in Supabase Postgres (EU/Frankfurt region). PostGIS enabled.

**`profiles`**
- `id` (uuid, = auth user id), `username` (unique, lowercase, 3–30 chars,
  `[a-z0-9_]`), `display_name`, `avatar_url`, `locale` (`de` | `en`),
  `is_private` (bool, default false), `created_at`.

**`follows`**
- `follower_id`, `followee_id` (both → profiles), `status`
  (`accepted` | `pending`), `created_at`.
- Primary key `(follower_id, followee_id)`; a user cannot follow themselves.
- Following a public profile → `accepted` immediately. Following a private
  profile → `pending` until the followee approves; rejecting deletes the row.
- Switching a profile from private to public auto-accepts all pending requests.

**`places`**
- `id` (uuid), `google_place_id` (unique), `name`, `location`
  (`geography(Point)`), `address`, `is_closed` (bool), `details_refreshed_at`.
- Only `google_place_id` is kept permanently (Google ToS). Cached fields
  (`name`, `location`, `address`) are refreshed by a scheduled job at most
  every 30 days; the job also sets `is_closed` when Google reports the place
  permanently closed.

**`tags`**
- `slug` (pk, e.g. `date-night`), `label_de`, `label_en`, `sort_order`,
  `active` (bool). Seeded list; managed by the app owner, not users.
- Initial set: date night, quiet drinks, big group, cheap eats, late night,
  outdoor seating, brunch, business lunch, cocktails, wine, craft beer,
  family-friendly, solo, special occasion, quick bite, live music.

**`recommendations`**
- `id`, `user_id` (→ profiles), `place_id` (→ places), `tags` (text[] of tag
  slugs), `note` (text, ≤ 500 chars, optional), `created_at`, `updated_at`.
- Unique `(user_id, place_id)`: one recommendation per user per place,
  editable.
- `tags`: 1–3 entries (check constraint); a trigger rejects unknown,
  inactive or duplicate slugs. Stored as an array (GIN-indexed) rather than
  a join table so a recommendation and its tags are always written
  atomically.

**`reports`**
- `id`, `reporter_id`, `target_type` (`profile` | `recommendation`),
  `target_id`, `reason`, `created_at`. Insert triggers an email to the owner.

## 3. Privacy (Row-Level Security)

Privacy is enforced in the database, not in application code.

- A recommendation is readable if:
  its author is the requester, **or** the author is public, **or** the
  requester has an `accepted` follow of the author.
- Profile basics (username, display name, avatar, is_private, counts) are
  readable by everyone, so private profiles can be found and requested.
- `follows` rows are readable by the two parties; accepted follows where
  **both** profiles are public are readable by everyone (for
  follower/following lists). Follower/following counts are public for all
  profiles via a function.
- Users may only insert/update/delete their own recommendations, their own
  outgoing follows, and approve/reject follows targeting themselves.

## 4. Discover query

Implemented as a single Postgres function
`discover(tag_slug, lat, lng, radius_m, scope)` where `scope` is
`following` (default) or `everyone`.

1. Candidate authors: `following` → accepted followees of the caller;
   `everyone` → all public profiles plus the caller's accepted followees.
   The caller's own recommendations are never included.
2. Their recommendations carrying `tag_slug`.
3. Join places within `radius_m` of `(lat, lng)`, excluding `is_closed`.
4. Group by place. Return place fields, distance, recommender count, up to
   3 recommender profiles (followees first), and the aggregated tags.
5. Order by recommender count desc, then distance asc. Paginate (20/page).

Default radius 2 km; user can widen to 5 km / 10 km / whole city.

## 5. Screens and flows

1. **Discover (home)** — tag chips; list/map toggle; results per §4.
   Location via browser geolocation; if denied, search a city/area.
   Empty state: "None of the people you follow have tagged *X* nearby yet"
   with actions *widen radius* and *show public picks* (`scope=everyone`).
2. **Spot detail** — Google details (address, hours, photos; fetched live,
   not stored), all visible recommendations with notes, *Recommend* /
   *Edit my recommendation*, *Open in Google Maps*. Closed places show a
   *closed* label.
3. **Add recommendation** — Google Places autocomplete biased to current
   location → pick 1–3 tags → optional note → save. Selecting a place
   upserts `places`.
4. **Profile** — avatar, name, follower/following counts, recommendations
   filterable by tag, Follow / Request / Following / Requested button.
   Private and not accepted: lock icon + "Follow to see picks".
5. **Find people** — username search; share link `/@username` that works
   for signed-out visitors (preview of public profile + sign-up prompt).
6. **Settings** — language, private toggle, pending follow requests
   (approve/reject), log out, delete account.

**Onboarding:** sign in (magic link / Google / Apple) → choose username →
empty-feed screen with suggested curator accounts and own share link.

## 6. Architecture

```
Browser (PWA, Next.js/React)
   ├── Supabase — auth, Postgres (+PostGIS), RLS          (EU region)
   └── Next.js server routes ──► Google Places API (key server-side only)
```

Modules (each with one purpose, testable in isolation):

- **`places/`** — the only code that talks to Google: autocomplete, details,
  upsert into `places`, refresh job. Exposes a provider interface so
  Foursquare can replace Google by changing only this module. Caches
  autocomplete/details responses briefly to limit cost.
- **`recommendations/`** — create/edit/delete own recommendation; tag
  validation.
- **`discover/`** — thin client over the `discover()` DB function.
- **`social/`** — follow, unfollow, request, approve/reject, share links.
- **`auth/`** — Supabase Auth with email magic link, Google, Apple;
  username selection.
- **`i18n/`** — DE/EN message files; tag labels come from `tags`.

**Hosting:** Vercel (app), Supabase EU region (data).
**Apple Sign-In** requires an Apple Developer account (99 USD/year).

## 7. Error handling

- **Google Places down or quota exhausted:** Discover unaffected (reads only
  stored places). Adding a spot shows a friendly "temporarily unavailable"
  message. Google API key has a daily spend cap.
- **Geolocation denied or unavailable:** fall back to manual city/area search.
- **Closed places:** hidden from Discover, labeled on profiles/detail.
- **Account deletion:** cascades to profile, follows, recommendations,
  reports filed by the user (GDPR).
- **Abuse:** username blocklist; per-account daily limits (e.g. 200 follows,
  50 recommendations); report button emails the owner.
- **Validation errors** (tags count, note length, username format) are
  checked in the DB and surfaced as localized form errors.

## 8. Testing

Test-driven development throughout.

- **Database tests** (highest priority), run against a local Supabase:
  - RLS: stranger cannot read a private user's recommendations; pending
    follower cannot; accepted follower can; owner can; public readable by all.
  - Follow state transitions, including private → public auto-accept.
  - `discover()` ranking, radius filter, closed-place exclusion, scope.
  - Tag constraint (1–3, active only) and uniqueness per user/place.
- **Unit tests:** `places/` with a fake provider (no network, no cost);
  recommendation validation; i18n key completeness (DE and EN have the same
  keys).
- **End-to-end (Playwright):** sign up → follow a user → they recommend a
  spot with a tag → it appears in my Discover for that tag; private profile
  request/approve flow.

## 9. Open items for the product owner

- Final app name and domain.
- Launch city (affects autocomplete bias default and seed curators).
- Where the code will live: a new dedicated repository (this spec will move
  there).
