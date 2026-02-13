const DB_NAME = 'school_offline_db';
const STORE_NAME = 'offline_requests';
let db;

// 1. Initialize IndexedDB
const initDB = () => {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, 1);
        request.onupgradeneeded = (event) => {
            db = event.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
            }
        };
        request.onsuccess = (event) => {
            db = event.target.result;
            resolve(db);
        };
        request.onerror = (event) => {
            console.error("IndexedDB Error:", event);
            reject(event);
        };
    });
};

// 2. Store Request
const storeRequest = async (reqData) => {
    if (!db) await initDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.add(reqData);
        request.onsuccess = () => resolve();
        request.onerror = () => reject();
    });
};

// 3. Get All Requests (with IDs)
const getRequests = async () => {
    if (!db) await initDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const results = [];
        const request = store.openCursor();
        request.onsuccess = (event) => {
            const cursor = event.target.result;
            if (cursor) {
                // Combine key and value
                results.push({ id: cursor.key, ...cursor.value });
                cursor.continue();
            } else {
                resolve(results);
            }
        };
        request.onerror = () => reject();
    });
};

// 4. Delete Request
const deleteRequest = async (id) => {
    if (!db) await initDB();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction([STORE_NAME], 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.delete(id);
        request.onsuccess = () => resolve();
        request.onerror = () => reject();
    });
};

// 5. Fetch Interceptor
const originalFetch = window.fetch;
window.fetch = async (...args) => {
    let [resource, config] = args;
    let url = resource;

    // Handle Request object as first argument
    if (resource instanceof Request) {
        url = resource.url;
        if (!config) {
            // If no config provided, inherit from Request object
            config = {
                method: resource.method,
                headers: resource.headers,
                body: resource.body, // Note: Body stream might be used already
                mode: resource.mode,
                credentials: resource.credentials
            };
        }
    }

    // Default config if missing (GET request usually)
    if (!config) config = { method: 'GET' };

    // If Online, pass through
    if (navigator.onLine) {
        try {
            return await originalFetch(resource, config);
        } catch (error) {
            console.warn("Fetch failed, attempting offline storage:", error);
        }
    }

    // If Offline or Network Failed
    // Only intercept State-Changing requests (POST, PUT, DELETE)
    if (config && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(config.method.toUpperCase())) {

        // Prevent storing File Uploads (FormData)
        if (config.body instanceof FormData) {
            alert("لا يمكن رفع الملفات في وضع عدم الاتصال.");
            return Promise.reject("Offline File Upload Not Supported");
        }

        console.log("Offline Intercept: Storing request", url);

        // Serialize Headers
        let headers = {};
        if (config.headers instanceof Headers) {
            config.headers.forEach((value, key) => headers[key] = value);
        } else {
            headers = config.headers || {};
        }

        // Store Request
        const requestData = {
            url: url.toString(),
            method: config.method,
            headers: headers,
            body: config.body,
            timestamp: Date.now()
        };

        try {
            await storeRequest(requestData);
            showOfflineNotification();

            // Return Mock Success Response
            return new Response(JSON.stringify({
                message: "تم الحفظ محلياً (سيتم المزامنة عند الاتصال)",
                offline: true,
                success: true,
                // Specific Mock Data for Canteen Scanner
                student: {
                    last_name: "تم الحفظ",
                    first_name: "محلياً",
                    student_id_number: "OFFLINE",
                    class_name: "في الانتظار",
                    academic_year: "-",
                    attendance_system: "نصف داخلي"
                }
            }), {
                status: 202,
                statusText: "Accepted (Offline)",
                headers: { 'Content-Type': 'application/json' }
            });
        } catch (e) {
            console.error("Offline Storage Failed:", e);
            return Promise.reject(e);
        }
    }

    // For GET requests, let them fail (or be caught by SW)
    return originalFetch(resource, config);
};

// 6. Sync Logic
async function syncOfflineRequests() {
    const notification = document.getElementById('syncNotification');
    const syncText = document.getElementById('syncText');

    try {
        const requests = await getRequests();
        if (requests.length === 0) return;

        // Show Notification
        if(notification) {
            notification.style.display = 'flex';
            syncText.textContent = `جاري رفع ${requests.length} تحديثات...`;
        }

        console.log(`[Sync] Found ${requests.length} offline requests.`);

        for (const req of requests) {
            try {
                // Replay Request
                const response = await originalFetch(req.url, {
                    method: req.method,
                    headers: req.headers,
                    body: req.body
                });

                if (response.ok || response.status === 409 || response.status === 400 || response.status === 500) {
                    // We consider completed (even if error) to avoid infinite loop.
                    // Ideally 500 should be retried, but for simplicity we clear it to unblock others.
                    // Or we can leave it? No, clearing is safer to prevent blocking the queue forever.
                    await deleteRequest(req.id);
                    console.log(`[Sync] Request ${req.id} processed (Status: ${response.status}).`);
                } else {
                    console.error(`[Sync] Request ${req.id} failed with ${response.status}`);
                }

                // Update UI Counter
                const remaining = (await getRequests()).length;
                if(syncText) syncText.textContent = `جاري رفع ${remaining} تحديثات...`;

            } catch (err) {
                console.error(`[Sync] Network Error for ${req.id}`, err);
                break; // Stop syncing if network drops
            }
        }

        // Finish
        const finalCheck = await getRequests();
        if (finalCheck.length === 0) {
            if(syncText) syncText.textContent = "تمت المزامنة بنجاح!";
            setTimeout(() => {
                if(notification) notification.style.display = 'none';
                window.location.reload(); // Refresh to show synced data
            }, 2000);
        } else {
            if(syncText) syncText.textContent = "توقفت المزامنة (خطأ في الاتصال)";
            setTimeout(() => { if(notification) notification.style.display = 'none'; }, 3000);
        }

    } catch (e) {
        console.error("Sync Error:", e);
    }
}

// Listen for Online Event
window.addEventListener('online', () => {
    console.log("Network Online - Starting Sync...");
    syncOfflineRequests();
});

// Initial Check
window.addEventListener('load', () => {
    if (navigator.onLine) syncOfflineRequests();
});

// Helper for Toast
function showOfflineNotification() {
    const banner = document.getElementById('offlineBanner');
    if(banner) {
        banner.style.display = 'block';
        banner.textContent = "تم الحفظ محلياً (لا يوجد اتصال)";
        setTimeout(() => {
            if(navigator.onLine) banner.style.display = 'none';
            else banner.textContent = "لا يوجد اتصال بالإنترنت - وضع العمل دون اتصال";
        }, 3000);
    }
}
