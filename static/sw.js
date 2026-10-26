
const CACHE_NAME = "titulacion-ita-pwa-v1";

const OFFLINE_URL = "/static/offline.html";

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.add(OFFLINE_URL))
            .then(() => self.skipWaiting())
    );
});

self.addEventListener("activate", (event) => {
    event.waitUntil(
        caches.keys()
            .then((keys) => Promise.all(
                keys
                    .filter((key) =>
                        key.startsWith("titulacion-ita-pwa-") &&
                        key !== CACHE_NAME
                    )
                    .map((key) => caches.delete(key))
            ))
            .then(() => self.clients.claim())
    );
});

self.addEventListener("fetch", (event) => {
    const request = event.request;
    const url = new URL(request.url);

    // No interceptar solicitudes que no sean GET
    // ni solicitudes a otros sitios.
    if (
        request.method !== "GET" ||
        url.origin !== self.location.origin
    ) {
        return;
    }

    // Solo ofrecer una alternativa sin conexión para
    // navegaciones HTML. No almacenar páginas privadas.
    if (request.mode === "navigate") {
        event.respondWith(
            fetch(request).catch(async () => {
                const cache = await caches.open(CACHE_NAME);
                return await cache.match(OFFLINE_URL);
            })
        );
    }
});
