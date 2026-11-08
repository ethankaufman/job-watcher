// Service worker: lets the site install and open offline.
//
// Online: every file is fetched from the network (and a copy is saved), so the pages always
// get the latest data files. Offline: the saved copy is used, so the site still opens and
// shows the last data it loaded.

const CACHE = "job-watcher-v1";

// Saved when the worker installs, so the site opens offline even before every page was visited.
const SHELL = [
  "./",
  "index.html",
  "browse.html",
  "market.html",
  "guide.html",
  "manifest.webmanifest",
  "assets/style.css",
  "assets/data.mjs",
  "assets/stats.mjs",
  "assets/ui.mjs",
  "assets/charts.mjs",
  "assets/today.mjs",
  "assets/browse.mjs",
  "assets/market.mjs",
  "data/status.json",
  "data/history.csv",
  "icons/icon.svg",
  "icons/icon-192.png",
  "icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((n) => n !== CACHE).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;

  event.respondWith(
    fetch(request, { cache: "no-cache" })
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(async () => {
        // Offline (or the server is unreachable): answer from the saved copy.
        const saved = (await caches.match(request, { ignoreSearch: true })) ?? (request.mode === "navigate" ? await caches.match("index.html") : undefined);
        return saved ?? Response.error();
      }),
  );
});
