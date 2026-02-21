// offline_manager.js - Powered by Dexie.js for Robust Offline Storage
const db = new Dexie("SchoolOfflineDB");
db.version(1).stores({
    offlineQueue: '++id, url, method, body, timestamp' // Removed 'type' index
});

const API_BASE = '/canteen/api/';

// Status Indicator
function updateStatus(status) {
    const banner = document.getElementById('offlineBanner');
    const syncNotif = document.getElementById('syncNotification');

    if (status === 'offline') {
        if(banner) banner.style.display = 'block';
        if(syncNotif) syncNotif.style.display = 'none';
        console.log("App is Offline");
    } else if (status === 'syncing') {
        if(banner) banner.style.display = 'none';
        if(syncNotif) syncNotif.style.display = 'flex';
        console.log("Syncing...");
    } else {
        if(banner) banner.style.display = 'none';
        if(syncNotif) syncNotif.style.display = 'none';
        console.log("App is Online");
    }
}

// Check online status initially and on change
window.addEventListener('online', () => {
    updateStatus('online');
    processOfflineQueue();
});
window.addEventListener('offline', () => updateStatus('offline'));
if (!navigator.onLine) updateStatus('offline');

// Helper to serialize FormData (because IndexedDB can't store FormData directly)
async function serializeBody(body) {
    if (!body) return null;
    if (typeof body === 'string') return body; // Already JSON
    if (body instanceof FormData) {
        const obj = {};
        for (let [key, value] of body.entries()) {
            if (value instanceof File || value instanceof Blob) {
                // Convert File/Blob to Base64
                obj[key] = await new Promise((resolve) => {
                    const reader = new FileReader();
                    reader.onload = () => resolve(reader.result);
                    reader.readAsDataURL(value);
                });
            } else {
                obj[key] = value;
            }
        }
        return JSON.stringify(obj);
    }
    return JSON.stringify(body);
}

// Global fetch wrapper to intercept failed requests
const originalFetch = window.fetch;
window.fetch = async (...args) => {
    let [resource, config] = args;

    // Only intercept mutations (POST, PUT, DELETE) to our API
    if (config && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(config.method) && resource.includes(API_BASE)) {
        if (!navigator.onLine) {
            // Queue it
            try {
                const serializedBody = await serializeBody(config.body);
                await db.offlineQueue.add({
                    url: resource,
                    method: config.method,
                    body: serializedBody,
                    timestamp: Date.now()
                });
                alert("لا يوجد اتصال. تم حفظ العملية محلياً وسيتم إرسالها عند عودة الاتصال.");

                // Return a fake successful response to keep UI happy (Optimistic UI)
                return new Response(JSON.stringify({ message: "Saved offline (Pending)" }), {
                    status: 202,
                    headers: { 'Content-Type': 'application/json' }
                });
            } catch (e) {
                console.error("Offline Save Failed", e);
                throw e;
            }
        }
    }

    // Normal request
    return originalFetch(...args).catch(async (error) => {
        // Double check: if network error on mutation, queue it
        if (config && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(config.method) && resource.includes(API_BASE)) {
             try {
                const serializedBody = await serializeBody(config.body);
                await db.offlineQueue.add({
                    url: resource,
                    method: config.method,
                    body: serializedBody,
                    timestamp: Date.now()
                });
                alert("فشل الاتصال. تم حفظ العملية محلياً.");
                return new Response(JSON.stringify({ message: "Saved offline (Pending)" }), {
                    status: 202,
                    headers: { 'Content-Type': 'application/json' }
                });
            } catch (e) { throw error; }
        }
        throw error;
    });
};

async function processOfflineQueue() {
    const count = await db.offlineQueue.count();
    if (count === 0) return;

    updateStatus('syncing');

    // Get all items
    const items = await db.offlineQueue.toArray();

    // Prepare bulk sync payload
    // We send them to a special sync endpoint to handle them in bulk
    // OR we process one by one. Bulk is safer for order but requires backend support.
    // Let's use the existing 'sync_offline' endpoint we added to PendingUpdateViewSet.

    try {
        const response = await originalFetch('/canteen/api/pending_updates/sync/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('baza_school_csrf_v2') // Ensure we have this helper
            },
            body: JSON.stringify(items)
        });

        if (response.ok) {
            console.log("Sync Successful");
            await db.offlineQueue.clear();
            alert("تمت مزامنة جميع العمليات المعلقة بنجاح.");
        } else {
            console.error("Sync Failed", await response.text());
        }
    } catch (e) {
        console.error("Sync Error", e);
    } finally {
        updateStatus('online');
    }
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
