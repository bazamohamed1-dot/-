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

    // Handle FormData
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

    // Handle Regular Object
    return JSON.stringify(body);
}

// Global fetch wrapper to intercept failed requests
const originalFetch = window.fetch;
window.fetch = async (...args) => {
    let [resource, config] = args;

    // Ensure we are dealing with a URL string, Request object handled less gracefully here but standard usage passes string
    const url = resource instanceof Request ? resource.url : resource;

    // Only intercept mutations (POST, PUT, DELETE) to our API
    if (config && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(config.method) && url.includes(API_BASE)) {

        // 1. Explicit Offline Check
        if (!navigator.onLine) {
            console.log("Offline interception triggered for:", url);
            return await queueRequest(url, config);
        }
    }

    // 2. Try Network, Catch Failure (Flaky Connection)
    try {
        return await originalFetch(...args);
    } catch (error) {
        // Double check: if network error on mutation, queue it
        if (config && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(config.method) && url.includes(API_BASE)) {
             console.log("Network error interception triggered for:", url);
             return await queueRequest(url, config);
        }
        throw error;
    }
};

async function queueRequest(url, config) {
    try {
        const serializedBody = await serializeBody(config.body);
        await db.offlineQueue.add({
            url: url,
            method: config.method,
            body: serializedBody,
            timestamp: Date.now()
        });

        // Return a fake successful response to keep UI happy (Optimistic UI)
        return new Response(JSON.stringify({ message: "Saved offline (Pending)" }), {
            status: 202,
            statusText: "Accepted",
            headers: { 'Content-Type': 'application/json' }
        });
    } catch (e) {
        console.error("Offline Save Failed", e);
        throw e;
    }
}

async function processOfflineQueue() {
    const count = await db.offlineQueue.count();
    if (count === 0) return;

    updateStatus('syncing');

    // Get all items
    const items = await db.offlineQueue.toArray();

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
            // Don't alert on automatic sync, just update UI
            const syncNotif = document.getElementById('syncNotification');
            if(syncNotif) {
                syncNotif.innerHTML = '<i class="fas fa-check"></i> تمت المزامنة';
                setTimeout(() => { updateStatus('online'); }, 2000);
            }
        } else {
            console.error("Sync Failed", await response.text());
            updateStatus('online'); // Reset status even if failed to hide spinner
        }
    } catch (e) {
        console.error("Sync Error", e);
        updateStatus('offline'); // Probably still offline
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
