// offline_manager.js - Powered by Dexie.js for Robust Offline Storage

// 1. Initialize Dexie Database
const db = new Dexie('SchoolOfflineDB');
db.version(1).stores({
    requests: '++id, url, method, timestamp' // keys to index
});

// 2. Helper: Serialize Request Body
async function serializeBody(body) {
    if (body instanceof FormData) {
        const entries = [];
        for (const [key, value] of body.entries()) {
            // Dexie can store Blobs/Files directly
            entries.push({ key, value });
        }
        return { type: 'formData', entries };
    }
    // For JSON strings or other bodies, return as is
    return body;
}

// 3. Helper: Deserialize Request Body
function deserializeBody(storedBody) {
    if (storedBody && typeof storedBody === 'object' && storedBody.type === 'formData') {
        const fd = new FormData();
        storedBody.entries.forEach(entry => {
            fd.append(entry.key, entry.value);
        });
        return fd;
    }
    return storedBody;
}

// 4. Fetch Interceptor
const originalFetch = window.fetch;
window.fetch = async (...args) => {
    let [resource, config] = args;
    let url = resource;

    // Handle Request object
    if (resource instanceof Request) {
        url = resource.url;
        if (!config) {
            config = {
                method: resource.method,
                headers: resource.headers,
                body: resource.body,
                mode: resource.mode,
                credentials: resource.credentials
            };
        }
    }

    // Default config
    if (!config) config = { method: 'GET' };

    // Pass through GET requests (handled by Service Worker cache)
    if (config.method === 'GET' || config.method === 'HEAD') {
        return originalFetch(resource, config);
    }

    // If Online, try network first
    if (navigator.onLine) {
        try {
            return await originalFetch(resource, config);
        } catch (error) {
            console.warn("Network failed, switching to offline storage...", error);
        }
    }

    // If Offline or Network Failed -> Store in IndexedDB
    console.log(`[Offline] Intercepting ${config.method} to ${url}`);

    // Serialize Headers
    let headers = {};
    if (config.headers instanceof Headers) {
        config.headers.forEach((value, key) => headers[key] = value);
    } else {
        headers = config.headers || {};
    }

    try {
        const serializedBody = await serializeBody(config.body);

        // Save to Dexie
        await db.requests.add({
            url: url.toString(),
            method: config.method,
            headers: headers,
            body: serializedBody,
            timestamp: Date.now()
        });

        showOfflineNotification("تم الحفظ محلياً. سيتم التأكيد النهائي من طرف المدير عند توفر الإنترنت.");

        // Return Mock Success Response
        return new Response(JSON.stringify({
            success: true,
            offline: true,
            message: "تم الحفظ محلياً (في انتظار المزامنة)"
        }), {
            status: 202,
            headers: { 'Content-Type': 'application/json' }
        });

    } catch (e) {
        console.error("Offline Storage Failed:", e);
        alert("فشل الحفظ المحلي: " + e.message);
        throw e;
    }
};

// 5. Sync Logic
async function syncOfflineRequests() {
    const notification = document.getElementById('syncNotification');
    const syncText = document.getElementById('syncText');

    try {
        const count = await db.requests.count();
        if (count === 0) return;

        // Show sync notification
        if(notification) {
             notification.style.display = 'flex';
             if (syncText) syncText.textContent = `جاري رفع ${count} تحديثات...`;
            console.log(`[Sync] Background syncing ${count} items...`);
        }

        const requests = await db.requests.toArray();

        for (const req of requests) {
            try {
                console.log(`[Sync] Replaying ${req.method} ${req.url}`);
                const body = deserializeBody(req.body);

                const response = await originalFetch(req.url, {
                    method: req.method,
                    headers: req.headers,
                    body: body
                });

                // If success or handled error (409 conflict, 400 bad request), remove from queue
                // We don't want to block the queue forever for a bad request
                if (response.ok || response.status === 409 || response.status === 400 || response.status === 500) {
                     await db.requests.delete(req.id);
                }

            } catch (networkError) {
                console.error(`[Sync] Network error for req ${req.id}, keeping in queue.`);
                // Stop syncing to preserve order/bandwidth
                break;
            }
        }

        const remaining = await db.requests.count();
        if (remaining === 0) {
            if(syncText) syncText.textContent = "تمت المزامنة بنجاح!";
            console.log("[Sync] Complete");
             if(notification) {
                 setTimeout(() => { notification.style.display = 'none'; }, 2000);
             }
            // Reload page to reflect changes (optional, maybe distracting)
            // window.location.reload();
        } else {
            if(syncText) syncText.textContent = `تبقي ${remaining} تحديثات (خطأ في الاتصال)`;
            console.log(`[Sync] Remaining: ${remaining}`);
        }

    } catch (e) {
        console.error("Sync Error:", e);
    }
}

// 6. Listeners
window.addEventListener('online', syncOfflineRequests);
window.addEventListener('load', () => {
    if (navigator.onLine) syncOfflineRequests();
});

// UI Helper
function showOfflineNotification(msg) {
    const banner = document.getElementById('offlineBanner');
    if(banner) {
        banner.style.display = 'block';
        banner.textContent = msg || "تم الحفظ محلياً";
        setTimeout(() => {
            if(navigator.onLine) banner.style.display = 'none';
            else banner.textContent = "لا يوجد اتصال بالإنترنت - وضع العمل دون اتصال";
        }, 4000);
    }
}
