/**
 * تفريغ تخزين PWA/دون اتصال — يُستدعى فقط عند تبديل المستخدم أو طلب الخادم (إجراءات المدير).
 */
window.clearSchoolAppOfflineCaches = async function () {
    if ('caches' in window) {
        try {
            const keys = await caches.keys();
            await Promise.all(keys.map((k) => caches.delete(k)));
        } catch (e) {
            console.warn('[clearSchoolAppOfflineCaches] caches', e);
        }
    }
    if ('serviceWorker' in navigator) {
        try {
            const regs = await navigator.serviceWorker.getRegistrations();
            await Promise.all(regs.map((r) => r.unregister()));
        } catch (e) {
            console.warn('[clearSchoolAppOfflineCaches] sw', e);
        }
    }
    try {
        indexedDB.deleteDatabase('SchoolOfflineDB');
    } catch (e) {
        console.warn('[clearSchoolAppOfflineCaches] idb', e);
    }
};
