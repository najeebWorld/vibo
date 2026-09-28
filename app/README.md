# app/ – VIBO mobile (Expo SDK 57, TypeScript, iOS + Android)

```bash
cd app
cp .env.example .env          # EXPO_PUBLIC_API_PORT (Expo Go on the LAN) or EXPO_PUBLIC_API_URL (builds)
npm install --legacy-peer-deps
npx expo start                # scan the QR with Expo Go (iOS / Android) — phone and laptop on the same Wi-Fi
npm test                      # jest: batcher, chapter cards, session renewal, watch tracking
npm run typecheck             # tsc --noEmit
npm run doctor                # expo-doctor: SDK / dependency / config sanity
```
With Expo Go the API host is derived from the dev server, so only the port is needed. Make sure the
backend's `API_BASE` in the repo root `.env` is your LAN IP (e.g. `http://192.168.1.20:8010`), otherwise
video URLs point at `localhost` and won't play on the phone.

## What it does
- Vertical full-screen pager (`FlatList` paging), one `expo-video` player per on-screen item, sound on, loop.
- Prefetches the next 3 videos into the cache directory; plays the local file when it is there.
- Events (`impression`, `watch|swipe|rewatch`, `save`, `share`, `pause`) are batched and POSTed every 5 s
  and whenever the app goes to background. Failed posts are retried on the next tick.
- Session id renews after 30 min in the background (the server's session TTL).
- Every 12 videos a **chapter-end card** shows what this chapter added to the trail, then "Keep going" /
  "See your trail". The **Trail** screen lists everything you finished, saved or unlocked.
- Every video shows *why* it is there, straight from the ranker's score breakdown.
- **Creator feedback**: Trail → *My videos* lists your uploads; tapping one (or *Stats* in the ⋯ menu on your own
  video) shows the retention curve and the watch-ratio histogram at 10% buckets, live, refreshed every 30 s.
- No login: a random install id (UUID in the keychain / keystore) is the user id. Not a hardware id.

## Store readiness (iOS + Android)
| Requirement | Where |
|---|---|
| Bundle id / package, version, build number | `app.config.ts` (`BUNDLE_ID`, `version`, `buildNumber`, `versionCode`) |
| No dev network exceptions in production | `APP_ENV=production` (set by `eas.json`) removes `NSAllowsArbitraryLoads` and `usesCleartextTraffic` |
| Minimal permissions | `android.permissions: []`; no location, contacts, camera, storage, tracking |
| UGC rules (Apple 1.2, Google UGC policy) | First-launch terms (`ConsentScreen`), **Report** with reasons, **Block creator**, both hidden immediately (`MoreSheet`, `POST /videos/{id}/report`, `POST /users/block`) |
| Export compliance | `ios.config.usesNonExemptEncryption: false` |
| Privacy labels | Data collected: in-app usage (watch/skip/save), linked to an app-generated id, not used for tracking. No ATT prompt needed. |
| Splash / icons | `expo-splash-screen` plugin, adaptive icon (placeholders in `assets/`, replace before submission) |
| Build & submit | `eas build --profile production --platform all`, then `eas submit` (fill `ascAppId` / service-account path in `eas.json`) |

Before the first submission: run `eas init` (sets `extra.eas.projectId`), replace the placeholder icons,
set `EXPO_PUBLIC_API_URL` to the https API, and write the privacy policy URL + support URL into App Store
Connect / Play Console (both stores require them for UGC apps). Because there is no account, add
"Delete my data" as a support-email flow until an in-app deletion exists (Apple 5.1.1(v) applies only to
apps with account creation; we have none, but Google asks for a data-deletion path in the Data safety form).

## Layout
```
app.config.ts             one config for Expo Go, dev/preview builds and the stores
eas.json                  build profiles (development / preview / production)
src/app/_layout.tsx       install id, consent gate, providers, splash
src/app/index.tsx         the feed (pager, refill, prefetch, report/block)
src/app/trail.tsx         Trail screen
src/components/           VideoCard, ChapterCard, MoreSheet, ConsentScreen
src/lib/events.ts         EventBatcher (5 s / background flush)
src/lib/feed.ts           chapter cards every 12, refill when 3 left, dedupe
src/lib/session.ts        session id + 30-min renewal
src/lib/watch.ts          watched-ms tracking -> swipe / watch / rewatch
src/lib/prefetch.ts       next-3 cache (expo-file-system)
src/lib/store.ts          what this session added to the trail (chapter card)
src/lib/labels.ts         all user-facing strings (translate here)
src/lib/api.ts, config.ts backend client and base URL
```

## Not yet
- Uploading from the phone (phase 2: camera roll picker → `POST /videos` → PUT to the presigned URL).
- HLS: the server serves the source mp4 until the transcoder exists; `expo-video` plays HLS as-is later.
- Hebrew / RTL: strings are centralized in `labels.ts`; layout uses logical `left/right` and would need `I18nManager` for RTL.
