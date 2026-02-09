const DB_NAME = 'SchoolSysDB';
const DB_VERSION = 2; // Bump version for new stores

class OfflineManager {
    constructor() {
        this.db = null;
        this.initDB();
        window.addEventListener('online', () => {
            console.log("Online detected, syncing...");
            this.syncData();
        });
    }

    async initDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);
            request.onerror = (e) => reject(e);
            request.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains('outbox')) {
                    db.createObjectStore('outbox', { autoIncrement: true });
                }
                if (!db.objectStoreNames.contains('manifest')) {
                    db.createObjectStore('manifest'); // Key-Value store (key: 'offline_manifest')
                }
            };
            request.onsuccess = (e) => {
                this.db = e.target.result;
                resolve(this.db);
                if (navigator.onLine) this.syncData();
            };
        });
    }

    async addToOutbox(url, method, data) {
        if (!this.db) await this.initDB();
        const transaction = this.db.transaction(['outbox'], 'readwrite');
        const store = transaction.objectStore('outbox');
        const request = {
            url: url,
            method: method,
            data: data,
            timestamp: Date.now(),
            token: sessionStorage.getItem('session_token')
        };
        store.add(request);
        console.log('Saved to outbox', request);
    }

    // New optimized Blob saver
    async saveStudentOffline(payload) {
        if (!this.db) await this.initDB();
        const transaction = this.db.transaction(['outbox'], 'readwrite');
        const store = transaction.objectStore('outbox');

        // Payload has { url, method, data, file }
        // We store the file separately in the record so it's not JSON stringified
        const request = {
            url: payload.url,
            method: payload.method,
            data: payload.data, // This has 'photo_path': 'base64...' usually, but we overwrite/ignore it in sync
            blob: payload.file, // The raw File/Blob object
            timestamp: Date.now(),
            token: sessionStorage.getItem('session_token')
        };

        return new Promise((resolve, reject) => {
            const req = store.add(request);
            req.onsuccess = () => resolve();
            req.onerror = (e) => reject(e);
        });
    }

    async saveOfflineManifest(data) {
        if (!this.db) await this.initDB();
        try {
            const tx = this.db.transaction(['manifest'], 'readwrite');
            const store = tx.objectStore('manifest');
            store.put(data, 'offline_manifest'); // Key is 'offline_manifest'

            return new Promise((resolve, reject) => {
                tx.oncomplete = () => {
                    console.log("Manifest saved to IndexedDB");
                    resolve();
                };
                tx.onerror = (e) => {
                    console.error("IndexedDB Manifest Error", e);
                    reject(e);
                };
            });
        } catch(e) {
            console.error("Storage Error", e);
            throw new Error("فشل حفظ البيانات محلياً (IndexedDB Error)");
        }
    }

    async getOfflineManifest() {
        if (!this.db) await this.initDB();
        return new Promise((resolve, reject) => {
            const tx = this.db.transaction(['manifest'], 'readonly');
            const store = tx.objectStore('manifest');
            const req = store.get('offline_manifest');
            req.onsuccess = (e) => resolve(e.target.result);
            req.onerror = (e) => reject(e);
        });
    }

    async syncData() {
        if (!this.db) await this.initDB();
        if (!navigator.onLine) return;

        const transaction = this.db.transaction(['outbox'], 'readwrite');
        const store = transaction.objectStore('outbox');
        const request = store.getAll();

        request.onsuccess = async (e) => {
            const items = e.target.result;
            if (!items || items.length === 0) return;

            const currentToken = sessionStorage.getItem('session_token');
            // Filter valid items for current session
            const validItems = items.filter(i => i.token === currentToken);

            if (validItems.length === 0) {
                 // Clear old junk?
                 // Maybe later.
                 return;
            }

            try {
                // Pre-process items: Convert Blobs to Base64 for JSON transmission
                // We do this lazily HERE, not at save time, to save memory during operation.
                const processedItems = await Promise.all(validItems.map(async (item) => {
                    if (item.blob) {
                        // Convert Blob to Base64
                        const base64 = await new Promise((resolve) => {
                            const reader = new FileReader();
                            reader.onloadend = () => resolve(reader.result);
                            reader.readAsDataURL(item.blob);
                        });

                        // Update the data payload
                        item.data.photo_path = base64;
                        // Remove blob from the object sent to server (it's not serializable anyway)
                        delete item.blob;
                    }
                    return item;
                }));

                const headers = {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                };

                // Add Device ID
                const deviceId = localStorage.getItem('device_id');
                if (deviceId) headers['X-Device-ID'] = deviceId;

                // Send to Sync Endpoint
                const response = await fetch('/canteen/api/sync/', {
                    method: 'POST',
                    headers: headers,
                    body: JSON.stringify(processedItems)
                });

                if (response.ok) {
                    console.log("Synced items successfully");
                    // Clear Outbox
                    const clearTrans = this.db.transaction(['outbox'], 'readwrite');
                    clearTrans.objectStore('outbox').clear();
                } else {
                    console.error("Sync failed", response.status);
                }
            } catch (err) {
                console.error("Sync error", err);
            }
        };
    }
}

const offlineManager = new OfflineManager();

// Automated Background Download
window.downloadOfflineData = async (silent = true) => {
    if (!navigator.onLine) {
        if (!silent) alert("يجب أن تكون متصلاً بالإنترنت لتحميل البيانات.");
        return;
    }

    // Check if we logged in
    const token = sessionStorage.getItem('session_token');
    if (!token) return;

    // Update Status UI
    const indicator = document.getElementById('offlineStatusIndicator');
    if (indicator) {
        indicator.innerHTML = '<i class="fas fa-sync fa-spin"></i> جاري التحديث...';
        indicator.style.background = '#e0f2fe';
        indicator.style.color = '#0369a1';
    }

    try {
        console.log("Starting background data download...");

        // 1. Fetch Manifest
        const response = await fetch('/canteen/api/offline_manifest/', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
            }
        });

        if (!response.ok) {
            console.error("Background Download Failed:", response.status);
            if(indicator) {
                indicator.innerHTML = '<i class="fas fa-exclamation-circle"></i> فشل التحديث';
                indicator.style.background = '#fee2e2';
                indicator.style.color = '#991b1b';
            }
            return;
        }

        const data = await response.json();

        // 2. Save Data locally
        await offlineManager.saveOfflineManifest(data);

        // 3. Cache Images
        if ('caches' in window) {
            try {
                const cache = await caches.open('offline-images-v1');
                const students = data.students || [];

                // Collect URLs
                const urls = students
                    .map(s => s.photo_path)
                    .filter(url => url && url.startsWith('http'));

                // Batch process
                const BATCH_SIZE = 5;
                for (let i = 0; i < urls.length; i += BATCH_SIZE) {
                    const batch = urls.slice(i, i + BATCH_SIZE);
                    await Promise.all(batch.map(async (url) => {
                        try {
                            const match = await cache.match(url);
                            if (!match) await cache.add(url);
                        } catch(e) { /* ignore */ }
                    }));
                }
            } catch (e) {
                console.error("Cache Error:", e);
            }
        }

        console.log("Background Data Download Completed.");
        if (indicator) {
            indicator.innerHTML = '<i class="fas fa-check-circle"></i> جاهز للعمل';
            indicator.style.background = '#dcfce7';
            indicator.style.color = '#166534';
        }

    } catch (e) {
        console.error("Background Sync Error:", e);
        if(indicator) {
            indicator.innerHTML = '<i class="fas fa-wifi-slash"></i> وضع دون اتصال';
            indicator.style.background = '#f3f4f6';
            indicator.style.color = '#4b5563';
        }
    }
};

// Hard Reset Function (Fix "Failed" Updates)
window.resetApp = async () => {
    if (!confirm("سيتم تحديث التطبيق وإصلاح أخطاء التخزين. هل تريد المتابعة؟")) return;

    const btn = document.getElementById('downloadOfflineBtn');
    if(btn) btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري التنظيف...';

    try {
        // 1. Unregister Service Workers
        if ('serviceWorker' in navigator) {
            const registrations = await navigator.serviceWorker.getRegistrations();
            for (let registration of registrations) {
                await registration.unregister();
            }
        }

        // 2. Clear Caches
        if ('caches' in window) {
            const keys = await caches.keys();
            for (let key of keys) {
                await caches.delete(key);
            }
        }

        // 3. Clear IndexedDB (Manifest only, keep outbox/pending if possible?
        // User asked to fix "Stuck" files. Clearing everything is safest for a "Repair" button).
        // But we want to preserve "Pending" data if possible.
        // Let's try to preserve 'outbox'.
        // Actually, "Update Software" implies clearing assets. IndexedDB is data.
        // We will leave IndexedDB alone to prevent data loss, unless the DB structure itself is corrupted.
        // We will ONLY clear the 'manifest' store if we can, but simpler to just reload SW and Cache.

        alert("تم تنظيف الذاكرة المؤقتة. سيتم إعادة تحميل الصفحة.");
        window.location.reload(true); // Hard Reload

    } catch (e) {
        console.error("Reset failed", e);
        alert("فشل التنظيف الآلي. يرجى مسح بيانات المتصفح يدوياً.");
    }
};

// Auto-trigger on load if online
document.addEventListener('DOMContentLoaded', () => {
    // Wait a bit to let the page load
    setTimeout(() => {
        if (navigator.onLine) {
            window.downloadOfflineData(true);
        }
    }, 2000);
});

// Trigger when coming online
window.addEventListener('online', () => {
    setTimeout(() => window.downloadOfflineData(true), 1000);
});

// Wrapper for Fetch to handle offline automatically
window.apiFetch = async (url, options = {}) => {
    // Inject CSRF if missing
    if (!options.headers) options.headers = {};
    if (!options.headers['X-CSRFToken']) {
        const token = getCookie('csrftoken');
        if(token) options.headers['X-CSRFToken'] = token;
    }
    if (!options.headers['Content-Type']) {
        options.headers['Content-Type'] = 'application/json';
    }

    // Inject Device ID
    const deviceId = localStorage.getItem('device_id');
    if (deviceId) {
        options.headers['X-Device-ID'] = deviceId;
    }

    // ALWAYS try network first, then fall back to offline store on failure
    try {
        const response = await fetch(url, options);

        // If server error (5xx), treat as offline scenario for reliability
        if (response.status >= 500) {
            throw new Error(`Server Error: ${response.status}`);
        }

        return response;
    } catch (e) {
        console.log("Network/Server request failed, attempting offline save...", e);

        // Only save POST/PUT/PATCH/DELETE requests (data modification)
        if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(options.method)) {
            try {
                const body = typeof options.body === 'string' ? JSON.parse(options.body) : options.body;
                await offlineManager.addToOutbox(url, options.method, body);

                // Return a fake success response to the UI
                console.log("Data saved locally to Outbox");
                return new Response(JSON.stringify({message: 'تم الحفظ محلياً (سيتم المزامنة عند عودة الاتصال)'}), {
                    status: 200,
                    statusText: 'Offline Saved',
                    headers: {'Content-Type': 'application/json'}
                });
            } catch (saveError) {
                console.error("Failed to save offline:", saveError);
                throw e; // Rethrow original error if we can't save locally either
            }
        }

        // For GET requests, we might want to return cached data here if not handled elsewhere
        // But usually GET handling is view-specific (like in management.html)
        throw e;
    }
};
