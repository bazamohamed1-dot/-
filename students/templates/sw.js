const CACHE_NAME = 'school-management-v1';
const ASSETS_TO_CACHE = [
    '/',
    '/canteen/',
    '/canteen/ui/',
    '/canteen/list/',
    '/canteen/management/',
    '/static/js/auth_manager.js',
    '/static/js/offline_manager.js',
    '/static/images/logo.png',
    '/static/manifest.json',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap',
    'https://unpkg.com/html5-qrcode'
];

// Install Event: Cache critical assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Service Worker] Pre-caching offline pages');
            return cache.addAll(ASSETS_TO_CACHE);
        })
    );
    self.skipWaiting();
});

// Activate Event: Cleanup old caches
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
    self.clients.claim();
});

// Fetch Event: Network First, then Cache (for pages)
// Stale-While-Revalidate (for static assets)
self.addEventListener('fetch', (event) => {
    // Skip non-GET requests (POST requests handled by offline_manager.js logic or specific sync logic)
    if (event.request.method !== 'GET') {
        return;
    }

    const url = new URL(event.request.url);

    // API Caching Strategy (Network First, Fallback to Cache?)
    // Actually, for student lists, we might want Stale-While-Revalidate
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            caches.open(CACHE_NAME).then(async (cache) => {
                try {
                    const response = await fetch(event.request);
                    cache.put(event.request, response.clone());
                    return response;
                } catch (error) {
                    const cachedResponse = await cache.match(event.request);
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    // Return empty JSON or error to prevent UI crash
                    return new Response(JSON.stringify({ offline: true, error: 'Network Error' }), {
                        headers: { 'Content-Type': 'application/json' }
                    });
                }
            })
        );
        return;
    }

    // Static Assets Strategy (Cache First)
    if (url.pathname.startsWith('/static/') || url.hostname.includes('cdnjs') || url.hostname.includes('fonts')) {
        event.respondWith(
            caches.match(event.request).then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse;
                }
                return fetch(event.request).then((response) => {
                    // Don't cache if response is not valid
                    if (!response || response.status !== 200 || response.type !== 'basic') {
                        return response;
                    }
                    const responseToCache = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseToCache);
                    });
                    return response;
                });
            })
        );
        return;
    }

    // HTML Pages Strategy (Network First, Fallback to Cache)
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                // Check if we received a valid response
                if (!response || response.status !== 200 || response.type !== 'basic') {
                    return response;
                }
                // Clone the response
                const responseToCache = response.clone();
                caches.open(CACHE_NAME).then((cache) => {
                    cache.put(event.request, responseToCache);
                });
                return response;
            })
            .catch(() => {
                // If offline, try cache
                return caches.match(event.request).then((cachedResponse) => {
                    if (cachedResponse) {
                        return cachedResponse;
                    }
                    // If not in cache, fallback to a generic offline page?
                    // Or just return the cached Landing page
                    if (event.request.mode === 'navigate') {
                         return caches.match('/canteen/');
                    }
                });
            })
    );
});

// Background Sync (Simple Implementation)
// Usually triggered by 'sync' event, but Safari/Firefox support is spotty.
// We will rely more on client-side JS (offline_manager.js) to push data when online event fires.
self.addEventListener('sync', (event) => {
    if (event.tag === 'sync-data') {
        console.log('[Service Worker] Background Sync Triggered');
        // Logic to replay requests could go here, but doing it in Window context is often easier for UI feedback.
    }
});
