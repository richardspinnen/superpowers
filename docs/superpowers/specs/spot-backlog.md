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
9. **Instagram connection** (owner: "there needs to be a certain connection").
   Meta closed most of the API: no "Sign in with Instagram", no importing
   saved posts. What works:
   - "Share to Story" card for spots and profiles via the phone share sheet
     (with the share cards, item 5).
   - Member's @handle on the profile (trust; gives tastemakers followers).
   - Place's Instagram as a button on the spot page next to Website / Call /
     Directions; added by the first spotter or taken from the website.
   - Monthly / yearly recap designed as a Story.
   - Invitation links with a proper preview image for DMs.
   - Not: auto-posting to Instagram, embedded Instagram feeds.
   - Order: handle + place Instagram with the spot-page redesign; Story
     cards with share cards; recap later.

## Recaps — owner favourite (2026-09-28)

- **Monthly "Your October in spots"**: swipeable story-sized cards
  (black/white): new spots; new neighbourhoods with the map filling in;
  "Your taste this month" from moods; Known-for by you; quiet impact
  ("4 members went because of you"); First to spot. Hint in the app on the
  1st, also in the weekly email.
- **Yearly "Your 2026 in spots"** (Wrapped-style): numbers ("23 of 50
  neighbourhoods"), place of the year, distinctions earned, taste profile
  line, final card "Share your year" for Instagram Stories.
- Rules: only the member's own data; sharing always opt-in; no comparisons
  with others; small spot. logo doubles as invitation.
- Tech: images rendered server-side with Next.js's built-in image
  generation (no new dependency). Needs neighbourhoods and quiet impact
  first → after the social plan.

## Visual and product reference: VSCO (2026-09-28)

Owner: make Spot "VSCO-like". MICHELIN is the reference for the spot page;
VSCO for profiles, feed and the overall feel.

- Profile as a gallery: calm grid of the member's spots (photo + small
  name); neighbourhood map and distinctions quietly above.
- Circle feed as an image stream: large photo, one line ("Anna · Trattoria
  Da Enzo · Truffle pasta"); no likes, no counters.
- No public numbers anywhere (followers, circle size, spot counts); members
  see their own numbers only (recaps).
- Even more white space, small quiet labels, photos carry the page.
- Membership model like VSCO: free core, paid membership for extras
  (Wallet card, recaps, travel, more invitations).
- **Decided (owner): members MUST add their own photo to every spot.**
  Proposed rules: 1–3 own photos per spot, first is the gallery cover; no
  Google photo as a substitute on profiles (Google photos stay as background
  on the spot page); onboarding exception — favourites can be spotted now and
  get their photo within 7 days (visible only to the member until then);
  guidelines: place / dish / drink / view, no strangers' faces (privacy);
  uploads resized, GPS metadata stripped, moderation check. Tastemakers need
  photos for the ~200 launch spots. Tech: Supabase Storage (EU), resizing,
  EXIF removal, moderation → its own plan. Decided (owner): camera roll
  allowed, as well as the in-app camera.

## Profile link in Instagram bios (2026-09-28)

Owner: members put `spotdomain.co/profilename` in their Instagram bio to
showcase their finds — Spot as "link in bio" for people with taste.

- Today: profiles already work at `/@username`, visible signed out with a
  join prompt. Add top-level `/username` too (both lead to the same profile);
  app routes are protected via reserved usernames (keep the list complete
  when adding routes).
- Public profile for visitors as a VSCO-style gallery (photos, Known-for,
  neighbourhood map, distinctions); at the bottom "Spot is members only.
  Request an invitation." → waiting list.
- Link preview image (name, cover photo, "12 spots in Düsseldorf").
- Private profiles: name, photo, "shared by introduction" only.
- Needs a short domain (bio-friendly) → name/domain decision matters more.
- Decided (owner): visitors see a preview only (e.g. first 6 spots with
  photos, no notes), then "See all of Richard's spots — members only";
  full profiles require membership.

## Name (2026-09-28)

- Criteria: one short word, easy in DE/EN, about places + belonging,
  ownable (domain, Instagram, trademark). Bio-friendly short domain (.co or
  .club; .co preferred if the name itself says enough).
- **Favourite candidate (owner): "mise."** — from *mise en place*
  ("everything in its place"); chef/bartender insider code; logo "mise." on
  the black card. Tagline idea: "mise. Everything in its place." /
  "Alles an seinem Platz."
  - Risk: pronounced like German "mies" (= lousy). Mitigation: always written
    "mise." with the dot, tagline, insider launch audience. **Test**: ask 3–5
    Germans from the target group "Bist du schon auf mise?" unexplained.
  - Check: mise.co / mise.club / mise.app / joinmise.com (price incl.
    renewal), Instagram @mise / @mise.club / @joinmise, trademark EUIPO + DPMA
    classes 9 (apps) and 43 (restaurant services).
- **Collision found (owner, 2026-09-28):** mise.co is taken by "Mise — a
  mobile app connecting you to people and events nearby" (pre-launch page,
  early access on Google Play, no HTTPS — possibly abandoned). Similar
  category → confusion and trademark risk. Next: EUIPO/DPMA search "Mise",
  class 9; if an active app registration exists, drop mise.
- Name must be international (owner). Rejected: Haunt, Zirkel, Cercle (known
  electronic-music brand), CIRCL (dated, typo risk, existing CIRCL), MEEZ.
- Backups: Salon, Tavola, Palate; invented words (Myse, Spota, Voya) are
  easier to own.
- 2026-09-28 morning: owner wants a members'-club / slightly mysterious feel,
  international, "like a cool modern restaurant in Amsterdam or Munich"; not
  playful (Spood rejected as too playful). **Keeper: UNDR** ("under the
  radar", owner likes it). Shortlist: UNDR, Chez (every profile "chez
  Richard"), Voisin (neighbour — spot + hood idea), Onyx, Sotto, Clave.
  Idea: "hood" can live inside the app (neighbourhood collection) while the
  brand carries the club vibe.
- **Favourite names (owner, 2026-09-28): SUPR and SUPA** — from "supper
  club" (members' dining format), shortened to be catchy and ownable.
  Criteria confirmed: elegant, cool, catchy, international, easy and certain
  pronunciation, name should say restaurants/bars/going out. Rejected this
  morning: Spood (too playful), Onyx (video-game feel), Tag.
  - Web check (2026-09-28, not a trademark search): **SUPR** used by Supr
    Daily (Indian grocery/milk delivery, acquired by Swiggy), "Supr: Camera
    & Stories Editor" (photo/Stories app), supr (Mexican mobile carrier);
    similar-sounding Supra (footwear). → medium risk; "SUPR Club" + logo may
    still work. **SUPA** used by Supaorder (restaurant ordering platform),
    supa banana (restaurant), Supa / Supa Foods (grocery apps), and "Supa" ≈
    Supabase in tech → high risk, drop. Next: official search EUIPO eSearch,
    DPMA, WIPO Global Brand Database, classes 9 and 43; consider a
    trademark lawyer's search before committing.

## Partner perks with the Wallet card (2026-09-28)

Owner goal: showing the membership / Wallet card at partner venues earns a
reward (e.g. a free aperitif).

- Member: partner spot pages show a quiet note ("Members' perk: a welcome
  aperitif"); Apple Wallet pass relevant locations make the card appear on
  the lock screen near a partner; perks by level (Graphite aperitif, Gold
  + best table, Black chef's surprise).
- Venue: staff scan the card's QR → simple page "Valid member · Gold ·
  Perk · Redeem"; one tap redeems (limit per visit/month); rotating/dynamic
  QR so photos of cards don't work.
- Why venues join: curated, connected guests who post and bring friends; a
  €2–3 aperitif for a €100+ table; later a small partner dashboard.
- Business model later: free at first; then paid visibility or a fee per
  redeemed perk, or perks justify a paid membership.
- Depends on the Wallet card (Plan 4); pilot with 3–5 Oberkassel venues
  during the 20-member test.

## Positioning update: showing off through taste (owner, 2026-09-28)

- "It's like Instagram, but smarter": people join because they want the cool
  spots and want to show where they are — "I got this reservation", "best
  truffle pasta ever". A bit of showing off is the engine; FOMO pulls people
  in. Status through taste and places, not through likes or numbers.
- Feature implications: 24-hour "I'm here" live posts with a photo; optional
  "Tonight: a table at …" reservation flex; dish posts that feed Known for;
  "Discovered by" gains weight.
- Name direction from this: SEEN ("see and be seen"), SCENE, SPTD
  ("spotted"), Booked, Plated — top: SEEN, SPTD (availability unchecked).
- Web check SEEN (2026-09-28): SEEN APP (@seen_app, ~18k Instagram
  followers) — real-time connecting with people at bars/restaurants (same
  space); "Bar Seen" iOS app; Seen Arabic social platform; SeenU; Seen
  Agency (UK restaurant social-media agency); SeenAfter (social network,
  own trademark); US "SEEN" (Seen Media Group) cancelled 2025. → high risk,
  don't use alone; keep "Where the scene is seen" as a tagline idea. Scena
  rejected (three pronunciations). Lesson: short real English words are
  taken in our space → aim for an invented word (e.g. Skeen) or a
  distinctive combination.
- Web check seen/scene inventions (2026-09-28): **Zeen** — Zeen App
  "discover the best restaurants, powered by real recommendations from real
  friends" (= our concept, **competitor to study**), plus Zeeën (nearby
  people); **Sceno** — photo app with gallery profiles and Explore (close to
  our VSCO idea); **Skeen** — Skeen.io skincare app, FotoFinder skeen
  dermatoscope; **Seeno** — several AI companies. → seen/scene family too
  crowded; drop it. Next: one pre-checked list of ~10 invented names.
- **Naming brief (2026-09-28 midday).** Likes: VSCO, UNDR, SUPR, sound of
  ROIA / RAYA, seen/scene, Den, Mise. Dislikes: playful (Spood), video-game
  (Onyx), generic/obvious (Fresco, Olio, Tuck, domain hacks), hard to
  pronounce (Scena, Voisin). Needs: short, cool AND niche, international,
  one clear pronunciation, going-out vibe, ownable. Checked and taken in our
  space: RAYA (invite-only members app), ROIA (restaurants), Rova (travel
  journal + "social network where you get seen"), Oria (restaurant site
  builder, members café, social club). Homework for owner: name 3–5 brands
  with names they find cool. Next: pre-checked list of ~10 names (evening).
- Checks (2026-09-28 midday): **Fiko** — FIKO Italian restaurant in
  Amsterdam Oud-West (own ordering app) + Fiko Gurme restaurant group in
  Istanbul → high risk. **VIKA** — Vika restaurant (~6.4k IG), Vika's BBQ,
  Vik Restaurant & Bar (Norway), Vik Restaurants reservation software →
  medium-high. **UNDR** — undr (UAE fashion resale), Undr (French rap
  discovery), Undr Construction Fitness, undr.com owned by an app studio;
  nothing in restaurants / going out → medium risk, **strongest candidate
  so far**. Next: owner checks EUIPO classes 9 and 43 for UNDR; domains
  undr.club / undr.co.
- Earlier "quiet club" notes still apply to design (no public likes/counts),
  but the product is more expressive than "quiet".

## Ideas inbox

<!-- New ideas from the product owner land here first. -->
