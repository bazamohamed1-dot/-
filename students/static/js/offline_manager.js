const DB_NAME = 'SchoolSysDB';
const DB_VERSION = 1;

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
        // Store the manifest (Students list, etc) for offline usage
        // We'll create a new store 'manifest' in next version upgrade,
        // but for now let's reuse 'outbox' or just upgrade.
        // Upgrading IDB version is tricky if DB is open.
        // Alternative: Use LocalStorage for the manifest JSON (it's small < 1MB usually)
        // 1000 students * 200 chars = 200KB. Safe for LocalStorage.
        try {
            const strData = JSON.stringify(data);
            try {
                localStorage.setItem('offline_manifest', strData);
                console.log("Manifest saved to LocalStorage");
            } catch(e) {
                if (e.name === 'QuotaExceededError' || e.name === 'NS_ERROR_DOM_QUOTA_REACHED') {
                     // Try IndexedDB Fallback
                     if (!this.db) await this.initDB();
                     const tx = this.db.transaction(['outbox'], 'readwrite');
                     // Using outbox temporarily or create new store
                     // Since schema upgrade is hard on the fly, let's just warn user for now.
                     // Or clear old data?
                     alert("مساحة التخزين المحلية ممتلئة. لا يمكن حفظ البيانات دون اتصال.");
                }
                throw e;
            }
        } catch(e) {
            console.error("Storage Error", e);
            throw new Error("فشل حفظ البيانات محلياً (المساحة ممتلئة؟)");
        }
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

// Global function for the "Download Data" button
window.downloadOfflineData = async () => {
    const btn = document.getElementById('downloadOfflineBtn');
    const originalText = btn.innerHTML;

    if (!navigator.onLine) {
        alert("يجب أن تكون متصلاً بالإنترنت لتحميل البيانات.");
        return;
    }

    try {
        btn.disabled = true;
        btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> جاري التحميل...`;

        // 1. Fetch Manifest
        // Using window.apiFetch which injects CSRF/Device-ID
        const response = await fetch('/api/offline_manifest/', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
                // Note: Auth session cookie is sent automatically by browser for same-origin requests
            }
        });

        if (!response.ok) {
            const txt = await response.text();
            throw new Error(`Failed to fetch manifest: ${response.status} - ${txt}`);
        }

        const data = await response.json();

        // 2. Save Data locally
        await offlineManager.saveOfflineManifest(data);

        // 3. Cache Images
        if ('caches' in window) {
            const cache = await caches.open('offline-images-v1');
            const students = data.students || [];
            const total = students.length;
            let count = 0;

            // Collect URLs
            const urls = students
                .map(s => s.photo_path)
                .filter(url => url && url.startsWith('http')); // Only valid HTTP URLs

            // Batch process
            const BATCH_SIZE = 5;
            for (let i = 0; i < urls.length; i += BATCH_SIZE) {
                const batch = urls.slice(i, i + BATCH_SIZE);
                await Promise.all(batch.map(url =>
                    cache.add(url).catch(e => console.warn("Failed to cache image:", url))
                ));
                count += batch.length;
                btn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> صور (${Math.min(count, urls.length)}/${urls.length})`;
            }
        }

        btn.innerHTML = `<i class="fas fa-check"></i> تم التحديث`;
        btn.classList.replace('btn-primary', 'btn-success');
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.classList.replace('btn-success', 'btn-primary');
            btn.disabled = false;
        }, 3000);

    } catch (e) {
        console.error(e);
        btn.innerHTML = `<i class="fas fa-exclamation-triangle"></i> فشل`;
        btn.classList.replace('btn-primary', 'btn-danger');
        setTimeout(() => {
            btn.innerHTML = originalText;
            btn.classList.replace('btn-danger', 'btn-primary');
            btn.disabled = false;
        }, 3000);
    }
};

// Show/Hide Download Button based on connectivity
function updateDownloadButton() {
    const btn = document.getElementById('downloadOfflineBtn');
    if (btn) {
        btn.style.display = navigator.onLine ? 'inline-block' : 'none';
    }
}
window.addEventListener('online', updateDownloadButton);
window.addEventListener('offline', updateDownloadButton);
document.addEventListener('DOMContentLoaded', updateDownloadButton);

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
