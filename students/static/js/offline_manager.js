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
            token: localStorage.getItem('session_token')
        };

        store.add(request);
        console.log('Saved to outbox', request);

        // Show notification
        if(window.alert) {
             // Optional: visual feedback
             const div = document.createElement('div');
             div.textContent = 'تم حفظ البيانات محلياً (Offline)';
             div.style.cssText = 'position:fixed;bottom:20px;left:20px;background:orange;color:white;padding:10px;border-radius:5px;z-index:10000;';
             document.body.appendChild(div);
             setTimeout(() => div.remove(), 3000);
        }
    }

    async syncData() {
        if (!this.db) await this.initDB();
        if (!navigator.onLine) return;

        const transaction = this.db.transaction(['outbox'], 'readwrite');
        const store = transaction.objectStore('outbox');
        const request = store.openCursor();

        request.onsuccess = async (e) => {
            const cursor = e.target.result;
            if (cursor) {
                const req = cursor.value;
                const currentToken = localStorage.getItem('session_token');

                // Verify session matches
                if (req.token !== currentToken) {
                    console.error("Skipping sync item from different session");
                    cursor.delete();
                    cursor.continue();
                    return;
                }

                try {
                    const headers = {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    };

                    const response = await fetch(req.url, {
                        method: req.method,
                        headers: headers,
                        body: JSON.stringify(req.data)
                    });

                    if (response.ok || response.status === 400 || response.status === 500) {
                        // If 400/500, it reached server. We delete to prevent infinite loop of bad requests.
                        console.log("Synced item:", req.url);
                        cursor.delete();

                        // Notify
                        const div = document.createElement('div');
                        div.textContent = 'تمت مزامنة البيانات بنجاح';
                        div.style.cssText = 'position:fixed;bottom:20px;left:20px;background:green;color:white;padding:10px;border-radius:5px;z-index:10000;';
                        document.body.appendChild(div);
                        setTimeout(() => div.remove(), 3000);
                    } else {
                        console.error("Sync failed (network?) for", req.url, response.status);
                    }
                } catch (err) {
                    console.error("Sync error", err);
                }

                cursor.continue();
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
        options.headers['X-CSRFToken'] = getCookie('csrftoken');
    }
    if (!options.headers['Content-Type']) {
        options.headers['Content-Type'] = 'application/json';
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
