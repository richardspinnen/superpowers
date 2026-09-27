# Spot — Ideas Backlog

Collected with the product owner. Newest first within each section. Not yet
planned unless marked.

## Next up (agreed order)

1. **Spot page redesign, inspired by the MICHELIN Guide app** (2026-09-28)
   - Full-width hero photo (Google Places photos, live, with required credit),
     floating back / map / share buttons.
   - Name + one quiet line: area · cuisine; price level (€–€€€€) if Google has it.
   - Action tiles: Spot · Map · Share · Call.
   - Social proof with faces: "Anna, Lea + 3 members spotted this" (circle first).
   - Known for right under the header.
   - Spotted by: members' notes as quotes, with moods.
   - Hours grid (today highlighted, "Open now / Closed now"), small map preview,
     Directions / Website / Call buttons.
   - Bottom: "Something outdated or wrong? Let us know" replaces per-spot Report links.
   - Floating primary button: "Spot this place" / "Edit your spot".
   - Skip: nearby hotels, long critic text, card lists.
   - Step 1: update the clickable mockup artifact; step 2: Plan 3.5.
2. **Real place search**: Google Places API key walkthrough for the owner.
3. **Lock file for npm 11**: `npm ci` fails with Node 24 / npm 11
   (esbuild optional deps missing from package-lock.json); regenerate so both
   npm 10 (CI, Node 22) and npm 11 work.
4. **Go live privately**: Supabase EU project, Vercel, domain, Google + Apple
   sign-in, email sender (e.g. Resend), launch checklist from README.

## Later

- **Plan 4**: membership levels (Graphite / Silver / Gold / Black) and
  Apple / Google Wallet card.
- **Founding memberships** sold directly (e.g. 100 founding members), instead
  of Kickstarter; Kickstarter only with a physical product (metal card) and for
  expanding to more cities.
- Restaurant partnerships (perks, events, "spotted" window sticker).
- Member photo uploads (needs storage, resizing, moderation).
- Map view.
- Report emails to the owner.

## Positioning (2026-09-28)

- USP: *Only the people you trust, for exactly this moment.* Trust instead of
  stars; moment-first home screen; "Known for" says what to order; members'
  club feel.
- Closest competitor: Beli (social ranking, US-focused). Difference: Beli is a
  game for people who rank restaurants; Spot is a quiet, premium club for
  people others ask where to go. Owner's take: "Beli looks so uncool" — design
  and brand are part of the product.
- First members: tastemakers (chefs, bartenders, designers, creatives, boutique
  owners) in Düsseldorf.
- Validation test: 20 invited members, 2–3 weeks; ≥5 spots each, come back on
  their own, willing to pay for a founding membership.
- Later: travel — "your circle's spots in Lisbon" as a premium feature.
- Homework: owner tries Beli for 10 minutes and notes likes / dislikes.
- **Product definition (owner): "Spot is a small social network for
  connoisseurs."** Implications:
  - Circle feed: quiet timeline of the circle's new spots and notes.
  - Profiles as a taste portfolio (spots, Known-for, typical moods, level).
  - "Want to go": save a place from someone's spot, credited to them.
  - Quiet acknowledgment instead of likes ("Noted" / "Went because of you").
  - Introductions and private profiles stay central; invite rights as a
    later privilege (e.g. Black level).
  - Avoid: public follower counts as headline, leaderboards, streaks,
    comments/chat (noise, moderation), posting pressure.
  - Proposed order: after the spot-page redesign, circle feed + Want to go
    come before Plan 4 (levels, Wallet).
- **Gamification (owner: needed for growth and retention)** — status, not
  points (Amex, not Duolingo):
  - Growth: limited invitations as a reward (e.g. 3 on joining; Silver 5,
    Gold 10, Black unlimited); Wallet card as a status symbol; "Invited by
    Anna" on profiles.
  - Retention: levels as moments ("You're now Silver"); "First to spot" —
    "Discovered by Richard" on the spot page permanently; quiet impact shown
    only to the member ("7 members went because of you"); neighbourhood
    collection ("12 of 50 neighbourhoods"); monthly recap and a shareable year
    recap; weekly email digest of the circle's new spots.
  - **Owner favourite: neighbourhood collection.** Minimal Düsseldorf map on
    the profile, neighbourhoods fill in when spotted ("12 of 50
    neighbourhoods"); tap for spots there; quiet moment on a first spot in a
    new neighbourhood ("First spot in Pempelfort"). Later: each city is a
    passport page (bridge to travel). Data: Düsseldorf boundaries from city
    open data / OpenStreetMap (credit the source) in PostGIS, place →
    neighbourhood by point-in-polygon. Decided: ~50 Stadtteile (owner, 2026-09-28).
  - **Profile badges ("Distinctions")** (owner idea): few, earned,
    monochrome line marks; member shows up to 3 on the profile, the rest in a
    Distinctions section; no numbers or progress bars. Candidates: Founding
    Member (first 100, never again), Discoverer (first to spot 5 places),
    "<Neighbourhood> Local" (10 spots in one Stadtteil), Düsseldorf Complete
    (all ~50), Trusted (25 members went because of you), Night Owl (10 late
    night / club night spots), Wine / Cocktails / Coffee Connoisseur (10 spots
    in a mood with Known-for others agreed with), Host (invited 5 members who
    became active). Builds on neighbourhoods and First to spot.
  - Later: real partner perks per level (e.g. welcome drink for Gold).
  - Not: points, public leaderboards, streaks, daily pushes.
  - Order: invitations, First to spot and quiet impact with the circle-feed
    plan; levels and Wallet in Plan 4; recap and digest after.

## What makes it superb (2026-09-28)

Priority for the first 20 testers: 1, 2 and the spot-page redesign.

1. **Content before launch**: 5–10 Düsseldorf tastemakers spot ~200 great
   places before the first invitation; no empty club on day one.
2. **Onboarding against the empty circle**: starter circle of tastemakers
   (removable); "Spot your 3 favourite places" in ~60 seconds.
3. **Final name, logo and domain** before going live.
4. **Native feel**: installable PWA (icon, splash), instant transitions,
   subtle animation, loading skeletons; App Store app later for credibility.
5. **Beautiful share cards** (WhatsApp, Instagram Stories) for spots and
   profiles: black/white, name, Known for, "Spotted by".
6. **"Ask the circle"** — **owner favourite, candidate signature feature.**
   Ask a short question with optional moods, date, party size, area; members
   answer only with a spot plus one sentence (no open comments); the asker
   closes the loop ("We went to Da Enzo") → quiet impact for the answerer
   ("Richard went because of you"); questions expire after the date or 48 h;
   shown in the circle feed. Feeds badges (Host, Trusted). Open decision:
   audience — circle by default, optional "Ask all members" when the circle
   is small.
7. **Care in details**: "Open now / closes in 40 min", reservation link,
   native German copy, an empty state on every screen.
8. **Trust as brand**: no ads, no data selling, EU hosting, clear privacy page.

## Ideas inbox

<!-- New ideas from the product owner land here first. -->
