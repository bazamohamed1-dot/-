const CACHE_NAME = 'school-sys-v3';
const ASSETS = [
    '/canteen/dashboard/',
    '/static/js/auth_manager.js',
    '/static/js/offline_manager.js',
    '/static/manifest.json',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap'
];

self.addEventListener('install', (event) => {
    self.skipWaiting();
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(ASSETS);
        })
    );
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
});

self.addEventListener('fetch', (event) => {
    // Skip non-GET requests for caching
    if (event.request.method !== 'GET') {
        return;
    }

    // API & Auth: Network First
    if (event.request.url.includes('/api/') || event.request.url.includes('/auth/')) {
        event.respondWith(
            fetch(event.request).catch(() => {
                return new Response(JSON.stringify({error: 'Offline'}), {
                    headers: {'Content-Type': 'application/json'}
                });
            })
        );
        return;
    }

    // HTML/Static: Stale-While-Revalidate or Cache First
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            const fetchPromise = fetch(event.request).then((networkResponse) => {
                caches.open(CACHE_NAME).then((cache) => {
                    cache.put(event.request, networkResponse.clone());
                });
                return networkResponse;
            });
            return cachedResponse || fetchPromise;
        })
    );
});
