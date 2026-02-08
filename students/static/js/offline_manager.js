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
