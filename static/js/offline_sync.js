const dbName = "SchoolDB";
const storeName = "offlineQueue";

let db;

const request = indexedDB.open(dbName, 1);

request.onerror = (event) => {
  console.error("Database error: " + event.target.errorCode);
};

request.onupgradeneeded = (event) => {
  db = event.target.result;
  if (!db.objectStoreNames.contains(storeName)) {
      db.createObjectStore(storeName, { keyPath: "id", autoIncrement: true });
  }
};

request.onsuccess = (event) => {
  db = event.target.result;
  console.log("Local Database Ready");
  if (navigator.onLine) {
    syncQueue();
  }
};

function addToQueue(url, data, method = 'POST') {
  if (!db) return;
  const transaction = db.transaction([storeName], "readwrite");
  const objectStore = transaction.objectStore(storeName);
  const reqData = {
    url: url,
    data: data,
    method: method,
    timestamp: new Date().getTime()
  };
  objectStore.add(reqData);
  console.log("Added to offline queue", reqData);
}

async function syncQueue() {
  if (!db) return;
  const transaction = db.transaction([storeName], "readonly");
  const objectStore = transaction.objectStore(storeName);
  const getAllRequest = objectStore.getAll();

  getAllRequest.onsuccess = async (event) => {
    const items = event.target.result;
    if (items && items.length > 0) {
      console.log(`Syncing ${items.length} items...`);

      for (const item of items) {
        try {
          const response = await fetch(item.url, {
            method: item.method,
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': getCookie('csrftoken')
            },
            body: JSON.stringify(item.data)
          });

          if (response.ok) {
            // Remove from DB
            deleteFromQueue(item.id);
            console.log("Synced item", item.id);
          } else {
            console.error("Sync failed for item", item);
          }
        } catch (error) {
          console.error("Sync error", error);
        }
      }
    }
  };
}

function deleteFromQueue(id) {
  const transaction = db.transaction([storeName], "readwrite");
  const objectStore = transaction.objectStore(storeName);
  objectStore.delete(id);
}

window.addEventListener('online', syncQueue);

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
