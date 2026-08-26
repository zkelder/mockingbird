// MockingBird's service worker: bounded, safe "static shell" caching only
// (see docs/mobile-remote-experience-v1-report.md, "PWA decision").
//
// What this deliberately does and does not do:
// - Caches ONLY Vite's own content-hashed `/assets/*` bundle files
//   (immutable by construction: a code change always produces a new
//   hashed URL, never the same URL with different content), cache-first.
// - Never intercepts navigation requests, `/index.html`, or anything
//   under `/api/`/`/health` -- those always go straight to the network,
//   exactly as if this service worker did not exist. This is the whole
//   safety property: the installed app can never show stale Visits,
//   evidence, or Today/Story data, because this worker never has the
//   opportunity to serve any of that from a cache in the first place.
// - No offline fallback page, no background sync, no push. Installing
//   MockingBird to a home screen makes it launch faster and look like an
//   app; it does not make MockingBird work without a network connection
//   to its own Host.
//
// Cache name is versioned so a future change to this file's own caching
// policy can cleanly discard the old cache on activate -- bump
// CACHE_NAME, not the logic below it, when that's ever needed.
const CACHE_NAME = "mockingbird-shell-v1";

self.addEventListener("install", (event) => {
  // No precaching: the current build's exact asset URLs are only known at
  // request time (they are content-hashed per build), so there is nothing
  // safe to precache eagerly here. Take over immediately so a page open
  // during an update does not keep an old worker pinned.
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") {
    return;
  }
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith("/assets/")) {
    // Every other request (navigations, /api/*, /health, anything else)
    // is left completely untouched -- no event.respondWith(...) at all --
    // so it behaves exactly as if this service worker were not installed.
    return;
  }

  event.respondWith(
    caches.open(CACHE_NAME).then(async (cache) => {
      const cached = await cache.match(request);
      if (cached) {
        return cached;
      }
      const response = await fetch(request);
      // Only a genuinely successful, basic (same-origin) response is
      // cached -- never an opaque/error response.
      if (response.ok && response.type === "basic") {
        cache.put(request, response.clone());
      }
      return response;
    }),
  );
});
