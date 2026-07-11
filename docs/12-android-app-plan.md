# ProCare OS — Android App Plan

Goal: ProCare on every pharmacist's and manager's Android phone — installable,
branded, fast — without forking the codebase. ProCare is already a PWA
(manifest + service worker + offline shell), which makes the phased path below
cheap and low-risk.

## Recommendation: three phases, each shippable on its own

### Phase 1 — PWA install (available TODAY, zero work)

The app is already installable: open **https://procare.prospices.net** in
Chrome on Android → menu → **Add to Home screen / Install app**. It gets the
ProCare icon, its own window, and the app shortcuts (POS / Inventory /
Reports).

- Cost: none. Ship: today.
- Limits: no Play Store listing; install is manual per device; notifications
  limited to Web Push.

### Phase 2 — TWA package for the Play Store (recommended next, ~1–2 days)

Wrap the same PWA in a **Trusted Web Activity** with
[Bubblewrap](https://github.com/GoogleChromeLabs/bubblewrap) — a real
`.aab`/`.apk` whose only content is the verified web app, full-screen (no
browser chrome).

Steps:
1. `npx @bubblewrap/cli init --manifest https://procare.prospices.net/manifest.webmanifest`
2. Host `/.well-known/assetlinks.json` on the domain (Next.js `public/`
   folder) with the app's signing-key fingerprint — this is what removes the
   browser bar.
3. `bubblewrap build` → upload to Play Console (internal track first) **or**
   install the APK directly on pharmacy devices (no store needed).

Considerations:
- **Cloudflare Access**: the TWA shares Chrome's cookies, so the Access login
  works once per device. For smoother UX, either exempt the app's routes with
  an Access *service token* baked into a bypass policy, or scope Access to a
  one-week session.
- The site must stay reachable (tunnel always-on — already configured as a
  Windows service). On the pharmacy LAN, devices can also use the LAN URL.

### Phase 3 — Capacitor wrapper (only when native features are needed)

If/when the team needs what the web can't do well, wrap the same Next.js app
in [Capacitor](https://capacitorjs.com) instead of rewriting:

| Native need | Plugin/approach |
|---|---|
| Push notifications (expiry alerts, transfer approvals, daily report) | `@capacitor/push-notifications` (FCM) |
| Fast barcode scanning at POS | `@capacitor-mlkit/barcode-scanning` (try the web `BarcodeDetector` API in Phase 1/2 first — Chrome Android supports it) |
| Bluetooth receipt printers (ESC/POS) | `capacitor-thermal-printer` or Web Bluetooth in Phase 2 |
| Offline POS queue | same service-worker/IndexedDB work as the web — not actually native |

- Cost: ~1–2 weeks including CI signing + update flow.
- Keep ONE codebase: Capacitor points at the served URL (`server.url`) so web
  deploys update the app instantly; only plugin code lives in the wrapper.

## What NOT to do

- **No native rewrite (Kotlin/Flutter/React Native).** 19 screens ×
  bilingual × RTL × constant iteration = permanent double maintenance for no
  user-visible gain over Phases 2–3.

## Sequence & effort summary

| Phase | Deliverable | Effort | When |
|---|---|---|---|
| 1 | Install from Chrome (PWA) | 0 | today |
| 2 | Play-Store/APK app (TWA + assetlinks) | 1–2 days | next |
| 3 | Capacitor + push + ML-Kit barcode + printer | 1–2 weeks | when needed |

Prerequisites for Phase 2: a Google Play developer account ($25 one-time,
optional if side-loading APKs), an Android signing key (Bubblewrap generates
it), and `assetlinks.json` in `src/frontend/public/.well-known/`.
