const CACHE_NAME = 'school-pwa-v2'; // Incremented version
const STATIC_ASSETS = [
    '/canteen/',
    '/canteen/dashboard/',
    '/canteen/ui/',
    '/canteen/management/',
    '/canteen/settings/',
    '/static_v2/manifest.json', // Updated path
    '/static_v2/images/logo.png', // Updated path
    '/static_v2/js/auth_manager.js',
    '/static_v2/js/xlsx.full.min.js',
    '/static_v2/js/browser-image-compression.js',
    '/static_v2/js/html5-qrcode.min.js',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Service Worker] Pre-caching offline pages');
            // Use addAll with error handling to avoid one failure breaking everything
            return Promise.all(
                STATIC_ASSETS.map(url => {
                    return cache.add(url).catch(err => console.warn('Failed to cache:', url, err));
                })
            );
        })
    );
    self.skipWaiting();
});

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

self.addEventListener('fetch', (event) => {
    // 1. Handle Navigation Requests (HTML Pages)
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request)
                .then((response) => {
                    return caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, response.clone());
                        return response;
                    });
                })
                .catch(() => {
                    return caches.match(event.request)
                        .then((response) => {
                            if(response) return response;
                            // Fallback to landing if specific page not cached
                            return caches.match('/canteen/');
                        });
                })
        );
        return;
    }

    // 2. Handle GET API Requests (Data) - Network First, Cache Fallback
    // This ensures we always try to get fresh data (like student lists) but fallback if offline.
    if (event.request.method === 'GET' && (event.request.url.includes('/api/') || event.request.url.includes('/canteen/'))) {
         event.respondWith(
            fetch(event.request)
                .then((response) => {
                    if(!response || response.status !== 200) return response;
                    const responseToCache = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseToCache);
                    });
                    return response;
                })
                .catch(() => {
                    return caches.match(event.request);
                })
        );
        return;
    }

    // 3. Handle Static Assets (Images, JS, CSS) - Cache First or Stale-While-Revalidate
    // For simplicity and speed, we use Stale-While-Revalidate
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            const fetchPromise = fetch(event.request).then((networkResponse) => {
                if(networkResponse && networkResponse.status === 200) {
                     caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, networkResponse.clone());
                    });
                }
                return networkResponse;
            }).catch(e => cachedResponse); // If offline and cached, return cached
            return cachedResponse || fetchPromise;
        })
    );
});
