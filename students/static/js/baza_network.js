/**
 * navigator.onLine يصبح false في Windows عند غياب المسار الافتراضي للإنترنت،
 * بينما طلبات same-origin إلى Django على localhost أو LAN ما تزال تعمل.
 */
function bazaNetworkOkForSameOrigin() {
    if (typeof navigator !== 'undefined' && navigator.onLine) return true;
    try {
        const h = window.location.hostname || '';
        if (h === 'localhost' || h === '127.0.0.1' || h === '[::1]') return true;
        if (/^192\.168\.\d{1,3}\.\d{1,3}$/.test(h)) return true;
        if (/^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(h)) return true;
        const m = /^172\.(\d{1,3})\./.exec(h);
        if (m) {
            const oct = parseInt(m[1], 10);
            if (oct >= 16 && oct <= 31) return true;
        }
        if (h.endsWith('.local')) return true;
        return false;
    } catch (e) {
        return false;
    }
}
