// Minimal app-shell service worker.
// Static assets: cache-first. Page navigations: network-first with an
// offline fallback (this is a server-rendered app — pages must stay fresh).
const CACHE = "bbyu-shell-v1";
const PRECACHE = [
  "/static/css/styles.css",
  "/static/js/main.js",
  "/static/icons/icon-192.png",
  "/static/offline.html",
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;

  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req).catch(() => caches.match("/static/offline.html"))
    );
    return;
  }

  const url = new URL(req.url);
  if (url.origin === location.origin && url.pathname.startsWith("/static/")) {
    e.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((resp) => {
            const copy = resp.clone();
            caches.open(CACHE).then((c) => c.put(req, copy));
            return resp;
          })
      )
    );
  }
});
