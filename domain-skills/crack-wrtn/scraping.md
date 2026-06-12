# crack.wrtn.ai (뤼튼 크랙 — AI character chat)

Next.js (pages router) with full SSR. **You rarely need a browser** for structure/catalog work — `http_get` + `__NEXT_DATA__` gives everything below. Logged-out works for browse/detail; chat/payment/my-page require the wrtn SSO session.

## The goldmine: `__NEXT_DATA__`

Every SSR page embeds `<script id="__NEXT_DATA__">` (~1MB on home). Parse `props.pageProps`:

- `env` — all public endpoints: API gateway `https://crack-api.wrtn.ai`, socket path `/character-chat/socket.io` (chat is socket.io), login `https://login.wrtn.ai` (SSO, cookie domain `.wrtn.ai`), store `https://wrtn.ai/crack-store`.
- `fallback` — SWR-prefetched data, keyed by API path. The keys ARE the private API routes:
  - `/genre-navigations/web?home=story` — nav tabs (each: `name`, `pageId`, `isAdultOnly`, `hasHeroBannerSection`)
  - `/pages/{pageId}/web?home=story` — home feed: `data.sections[]`, server-driven section types: `HeroBanner`/`WelcomeMission`/`HeadLineAnnouncement`/`CharacterCarousel`/`TagCarousel` + ranked grid
  - `/stories/{id}` — full character detail (on `/info/{id}` pages)

Use a **mobile UA** (iPhone Safari) — the site is mobile-first and `isMobileAgent` switches the layout.

## Routes

```
/                 home (story mode)        /characters   same page system, home=character
/info/{id}        character/story detail   /original     official IP
/party-chat       multi-character chat     /cracker      creator hub
/welcome-mission  onboarding missions      /my, /image/generate  (wrtn shell, client-rendered)
```

Deep links: `wrtncharacter://info/{id}` (app), short share links `https://share.crack.wrtn.ai/{slug}`.

## Character data model (40 fields, card & `/stories/{id}` shared)

Most useful: `name`, `simpleDescription`, `description` (markdown — external images/links allowed), `tags[]`, `genre{name,type}`, `chatType{name}` (e.g. 시뮬레이션), `target{name}` (남성향/여성향), `isAdult`, `creator{nickname,isCertifiedCreator}`, social proof (`totalMessageCount`, `chatUserCount`, `likeCount`, `commentCount`), `startingSets[]` (multiple start scenarios: `name`, long markdown `initialMessages`, `playGuide`), `endingCount`, `series{...}`, `promptTemplate{name,template}`, `defaultCrackerModel` (e.g. `superchat_2_0`), `shareUrl`.

## Traps

- **Direct API calls 404**: `crack-api.wrtn.ai/stories/{id}` etc. return 404 without the SSR context/auth headers — scrape the embedded `fallback` from the page HTML instead of calling the API.
- `/my` and `/image/generate` render the generic 뤼튼 shell (`<title>뤼튼</title>`, empty fallback) when logged out — don't mistake it for the real page.
- Popular characters implement affinity/emotion HUDs *inside prompts* (patterns like `서지안|♥️:0|😐🤔|💬:`) — that's creator content, not platform UI.
