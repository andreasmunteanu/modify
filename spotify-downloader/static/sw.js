const CACHE_NAME = "moodify-v1";
const STATIC_ASSETS = [
    "/",
    "/static/style.css",
    "/static/app.js",
    "/static/manifest.json",
];

self.addEventListener("install", e => {
    e.waitUntil(
        caches.open(CACHE_NAME).then(c => c.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener("activate", e => {
    e.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
    self.clients.claim();
});

self.addEventListener("fetch", e => {
    const url = new URL(e.request.url);

    // Don't cache API calls or audio files
    if (url.pathname.startsWith("/api/")) return;

    e.respondWith(
        caches.match(e.request).then(cached => {
            if (cached) return cached;
            return fetch(e.request).then(resp => {
                // Cache static assets on first load
                if (resp.ok && url.pathname.match(/\.(css|js|json|png|svg|woff2?)$/)) {
                    const clone = resp.clone();
                    caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
                }
                return resp;
            });
        }).catch(() => caches.match("/"))
    );
});
