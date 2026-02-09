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
        // Silent save (User Requirement: "لا تضع أي أزرار للمزامنة... تتم في الخلفية تماماً")
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
                    body: JSON.stringify(validItems)
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

    if (navigator.onLine) {
        try {
            const response = await fetch(url, options);
            if (!response.ok && !response.status.toString().startsWith('4')) {
                throw new Error("Server Error");
            }
            return response;
        } catch (e) {
            console.log("Online fetch failed, checking if POST to save offline...", e);
            if (options.method === 'POST') {
                const body = typeof options.body === 'string' ? JSON.parse(options.body) : options.body;
                await offlineManager.addToOutbox(url, options.method, body);
                // Fake a successful response
                return new Response(JSON.stringify({message: 'Saved offline'}), {status: 200, statusText: 'Offline Saved'});
            }
            throw e;
        }
    } else {
         if (options.method === 'POST') {
            const body = typeof options.body === 'string' ? JSON.parse(options.body) : options.body;
            await offlineManager.addToOutbox(url, options.method, body);
            return new Response(JSON.stringify({message: 'Saved offline'}), {status: 200, statusText: 'Offline Saved'});
        }
        throw new Error("Offline and not a POST request");
    }
};
