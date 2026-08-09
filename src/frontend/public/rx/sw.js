/* ProCare RX service worker — scoped to /rx/.
 *
 * Registered with { scope: "/rx/" }. The root worker's scope "/" overlaps, but
 * the longest matching scope wins, so /rx/* navigations come here.
 *
 * NOTE: scope matching is by REQUEST url, not by the page that made the
 * request — so /api/* calls from an RX page are still handled by the root
 * worker. That is one reason the offline write queue lives in the page rather
 * than in a fetch handler here: a queue in this worker would silently never
 * fire for API calls.
 *
 * Strategy mirrors the root worker: API is network-only (live pharmacy data
 * must never be stale), static assets cache-first, navigations network-first
 * with the /rx shell as the offline fallback.
 */
const CACHE = "procare-rx-v1";
const SHELL = ["/rx"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      // allSettled, not addAll: addAll is atomic, so one missing asset would
      // reject the install and the worker would never register (exactly the
      // bug that stopped the main PWA installing at all).
      .then((c) => Promise.allSettled(SHELL.map((u) => c.add(u))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      // Only ever delete OUR own older versions. A blanket sweep would evict
      // the root worker's cache, and the two would fight on every activation.
      .then((keys) =>
        Promise.all(keys.filter((k) => k.startsWith("procare-rx-") && k !== CACHE).map((k) => caches.delete(k)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return; // live data: network only

  if (url.pathname.startsWith("/_next/static/") || url.pathname.match(/\.(png|ico|svg|woff2?)$/)) {
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
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(event.request, copy));
          return res;
        })
        // Fall back to the RX shell, never to "/" — landing a phone user in the
        // desktop app because the network blipped would be worse than useless.
        .catch(() => caches.match(event.request).then((hit) => hit || caches.match("/rx")))
    );
  }
});
