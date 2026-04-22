{% load static %}
const CACHE_NAME = 'school-pwa-v13'; // v13: + baza_network.js (localhost دون إنترنت عام)
const STATIC_ASSETS = [
    '/canteen/',
    '/canteen/dashboard/',
    '/canteen/ui/',
    '/canteen/management/',
    '/canteen/settings/',
    '/canteen/pending_updates/',
    "{% static 'manifest.json' %}",
    "{% static 'images/logo.png' %}",
    "{% static 'js/clear_app_storage.js' %}",
    "{% static 'js/baza_network.js' %}",
    "{% static 'js/auth_manager.js' %}",
    "{% static 'js/offline_manager.js' %}",
    "{% static 'js/dexie.min.js' %}",
    "{% static 'js/xlsx.full.min.js' %}",
    "{% static 'js/browser-image-compression.js' %}",
    "{% static 'js/html5-qrcode.min.js' %}",
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap',
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.rtl.min.css'
];

self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Service Worker] Pre-caching offline pages');
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

function isSameOrigin(url) {
    return url.origin === self.location.origin;
}

self.addEventListener('fetch', (event) => {
    if (event.request.method !== 'GET') {
        return;
    }

    const url = new URL(event.request.url);

    // موارد خارجية (خطوط، CDN): من الـ cache إن وُجد ثم الشبكة
    if (!isSameOrigin(url)) {
        event.respondWith(
            caches.match(event.request).then((cached) => {
                if (cached) return cached;
                return fetch(event.request).then((networkResponse) => {
                    if (networkResponse && networkResponse.ok) {
                        const copy = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
                    }
                    return networkResponse;
                });
            })
        );
        return;
    }

    // واجهات API والمصادقة: دائماً للشبكة (الأوفلاين يُدار من التطبيق + IndexedDB)
    if (url.pathname.includes('/api/') || url.pathname.includes('/auth/')) {
        return;
    }

    const accept = event.request.headers.get('accept') || '';
    const isNavigate = event.request.mode === 'navigate' || accept.includes('text/html');

    if (isNavigate) {
        event.respondWith(
            fetch(event.request)
                .then((networkResponse) => {
                    if (networkResponse && networkResponse.ok) {
                        const copy = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            try {
                                cache.put(event.request, copy);
                            } catch (e) {
                                console.warn('[SW] cache.put navigate failed', e);
                            }
                        });
                    }
                    return networkResponse;
                })
                .catch(() =>
                    caches.match(event.request).then(
                        (cached) =>
                            cached ||
                            caches.match('/canteen/') ||
                            caches.match('/canteen/dashboard/')
                    )
                )
        );
        return;
    }

    // باقي GET (static، صور، …): stale-while-revalidate
    event.respondWith(
        caches.match(event.request).then((cached) => {
            const networkFetch = fetch(event.request)
                .then((networkResponse) => {
                    if (networkResponse && networkResponse.ok) {
                        const copy = networkResponse.clone();
                        caches.open(CACHE_NAME).then((cache) => {
                            try {
                                cache.put(event.request, copy);
                            } catch (e) {
                                console.warn('[SW] cache.put asset failed', e);
                            }
                        });
                    }
                    return networkResponse;
                })
                .catch(() => cached);
            return cached || networkFetch;
        })
    );
});
