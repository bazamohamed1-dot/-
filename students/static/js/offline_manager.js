// Offline Manager for School Management System
// Handles Service Worker Registration, IndexedDB, and Sync logic

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('ServiceWorker registration successful with scope: ', registration.scope);
            })
            .catch(err => {
                console.log('ServiceWorker registration failed: ', err);
            });
    });
}

// IndexedDB Setup
const DB_NAME = 'SchoolOfflineDB';
const DB_VERSION = 1;
const STORE_NAME = 'pending_actions';

let db;

const openDB = () => {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
            }
        };

        request.onsuccess = (event) => {
            db = event.target.result;
            resolve(db);
        };

        request.onerror = (event) => {
            reject('Database error: ' + event.target.errorCode);
        };
    });
};

// Add Action to Queue
const queueAction = async (url, method, data) => {
    const db = await openDB();
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);

    const action = {
        url: url,
        method: method,
        data: data,
        timestamp: new Date().toISOString()
    };

    store.add(action);

    tx.oncomplete = () => {
        console.log('Action queued locally:', action);
        showOfflineNotification();
    };
};

// Sync Queue with Server
const syncQueue = async () => {
    if (!navigator.onLine) return;

    const db = await openDB();
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const request = store.getAll();

    request.onsuccess = async () => {
        const actions = request.result;
        if (actions.length === 0) return;

        console.log(`Attempting to sync ${actions.length} actions...`);
        showSyncingNotification();

        // Process sequentially to maintain order
        for (const action of actions) {
            try {
                // Get CSRF Token
                const csrfToken = getCookie('csrftoken');

                const response = await fetch(action.url, {
                    method: action.method,
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': csrfToken
                    },
                    body: JSON.stringify(action.data)
                });

                if (response.ok || response.status === 409 || response.status === 400) {
                    // Success or handled error (duplicate), remove from queue
                    await removeAction(action.id);
                } else {
                    console.error('Sync failed for action:', action, response.status);
                    // Keep in queue for retry? Or move to 'failed' store?
                    // For now, keep in queue until success or manual clear.
                }
            } catch (error) {
                console.error('Network error during sync:', error);
                // Stop syncing if network fails again
                return;
            }
        }

        hideSyncingNotification();
        console.log('Sync complete.');
    };
};

const removeAction = async (id) => {
    const db = await openDB();
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    store.delete(id);
};

// Helpers
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

// Notifications
function showOfflineNotification() {
    const banner = document.getElementById('offlineBanner');
    if (banner) {
        banner.innerHTML = '<i class="fas fa-save"></i> تم حفظ العمل محلياً. سيتم المزامنة عند الاتصال.';
        banner.style.background = '#f59e0b';
        setTimeout(() => {
            if (!navigator.onLine) {
                 banner.innerHTML = '<i class="fas fa-wifi-slash"></i> لا يوجد اتصال بالإنترنت - وضع العمل دون اتصال';
                 banner.style.background = '#dc2626';
            } else {
                banner.style.display = 'none';
            }
        }, 3000);
    }
}

function showSyncingNotification() {
    const banner = document.getElementById('offlineBanner');
    if (banner) {
        banner.style.display = 'block';
        banner.style.background = '#3b82f6';
        banner.innerHTML = '<i class="fas fa-sync fa-spin"></i> جاري المزامنة مع الخادم...';
    }
}

function hideSyncingNotification() {
    const banner = document.getElementById('offlineBanner');
    if (banner) {
        banner.style.display = 'none';
    }
}

// Event Listeners
window.addEventListener('online', syncQueue);

// Export/Import Logic (Manual File Sync)
async function exportOfflineData() {
    const db = await openDB();
    const tx = db.transaction(STORE_NAME, 'readonly');
    const store = tx.objectStore(STORE_NAME);
    const request = store.getAll();

    request.onsuccess = () => {
        const actions = request.result;
        if (actions.length === 0) {
            alert('لا توجد بيانات غير متزامنة للتصدير.');
            return;
        }

        const dataStr = JSON.stringify(actions, null, 2);
        const blob = new Blob([dataStr], { type: "application/json" });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = `offline_data_${new Date().toISOString().slice(0,10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };
}

// Expose functions globally for UI buttons
window.queueAction = queueAction;
window.exportOfflineData = exportOfflineData;
window.syncQueue = syncQueue; // Allow manual trigger
