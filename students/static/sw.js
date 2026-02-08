const CACHE_NAME = 'school-sys-v3-stale-revalidate';
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

// Fetch Event: Stale-While-Revalidate Strategy
self.addEventListener('fetch', (event) => {
    // Only cache GET requests
    if (event.request.method !== 'GET') return;

    // Ignore API calls and Auth calls (Network First or Custom Offline Logic handled by App)
    if (event.request.url.includes('/api/') || event.request.url.includes('/auth/')) {
        return;
    }

    event.respondWith(
        caches.open(CACHE_NAME).then(async (cache) => {
            const cachedResponse = await cache.match(event.request);

            // Network request for update
            const networkFetch = fetch(event.request).then((networkResponse) => {
                // Update cache with new response
                if (networkResponse.ok) {
                    cache.put(event.request, networkResponse.clone());
                }
                return networkResponse;
            }).catch(() => {
                // Network failed?
                return cachedResponse;
            });

            // Return cached response immediately if available (Stale), otherwise wait for network
            return cachedResponse || networkFetch;
        })
    );
});
