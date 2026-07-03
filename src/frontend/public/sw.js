/* ProCare service worker.
 *
 * Strategy:
 *  - API calls (/api/*): network only — live pharmacy data must never be stale.
 *  - Navigations: network first, falling back to the cached shell when offline.
 *  - Static assets (icons, _next/static): cache first (immutable by content hash).
 */
const CACHE = "procare-v1";
const SHELL = ["/", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return; // live data: network only

  if (url.pathname.startsWith("/_next/static/") || url.pathname.match(/\.(png|ico|svg|woff2?)$/)) {
    // Content-hashed / immutable: cache first.
    event.respondWith(
      caches.match(event.request).then(
        (hit) =>
          hit ||
          fetch(event.request).then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(event.request, copy));
            return res;
          })
      )
    );
    return;
  }

  if (event.request.mode === "navigate") {
    // Pages: network first, cached shell offline.
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
          return res;
        })
        .catch(() => caches.match(event.request).then((hit) => hit || caches.match("/")))
    );
  }
});
