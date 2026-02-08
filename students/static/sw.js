const CACHE_NAME = 'school-sys-v4-stale-revalidate';
const ASSETS_TO_CACHE = [
    '/canteen/',  // Landing
    '/canteen/dashboard/',
    '/canteen/ui/',
    '/canteen/library/',
    '/canteen/management/',
    '/canteen/list/',
    '/canteen/archive/',
    '/static/js/auth_manager.js',
    '/static/js/offline_manager.js',
    '/static/manifest.json',
    '/static/styles.css',
    '/static/images/logo.png',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap'
];

// Install Event: Pre-cache core assets
self.addEventListener('install', (event) => {
    self.skipWaiting(); // Force activation
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Service Worker] Pre-caching offline pages');
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
});

// Activate Event: Clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keyList) => {
            return Promise.all(keyList.map((key) => {
                if (key !== CACHE_NAME) {
                    console.log('[Service Worker] Removing old cache', key);
                    return caches.delete(key);
                }
            }));
        })
    );
    self.clients.claim(); // Control all clients immediately
});

// Sync Event: Try to sync outbox when connection returns
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-outbox') {
        console.log('[Service Worker] Syncing outbox...');
        // We can't easily access IndexedDB here without importing logic,
        // but we can signal the clients or rely on the 'online' event in the window.
        // However, a proper background sync implementation would go here.
        // For now, we rely on the client-side 'online' event which is robust enough for this use case.
    }
});

// Fetch Event: Stale-While-Revalidate Strategy for Assets, Network First for HTML
self.addEventListener('fetch', (event) => {
    // Only cache GET requests
    if (event.request.method !== 'GET') return;

    const url = new URL(event.request.url);

    // Ignore API calls and Auth calls (Network First or Custom Offline Logic handled by App)
    if (url.pathname.includes('/api/') || url.pathname.includes('/auth/')) {
        return;
    }

    // Check if it's a navigation request (HTML page)
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request)
                .then((networkResponse) => {
                    return caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, networkResponse.clone());
                        return networkResponse;
                    });
                })
                .catch(async () => {
                    // Network failed, try cache
                    const cachedResponse = await caches.match(event.request);
                    if (cachedResponse) return cachedResponse;

                    // Fallback to landing or dashboard if specific page not cached
                    const landing = await caches.match('/canteen/');
                    return landing || caches.match('/canteen/dashboard/');
                })
        );
        return;
    }

    // For other assets (CSS, JS, Images) - Stale While Revalidate
    event.respondWith(
        caches.open(CACHE_NAME).then(async (cache) => {
            const cachedResponse = await cache.match(event.request);

            const networkFetch = fetch(event.request).then((networkResponse) => {
                if (networkResponse.ok) {
                    cache.put(event.request, networkResponse.clone());
                }
                return networkResponse;
            }).catch(() => {
                return cachedResponse;
            });

            return cachedResponse || networkFetch;
        })
    );
});
