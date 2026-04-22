// offline_manager.js — طابور الطلبات + نسخة محلية للطلاب حسب صلاحيات offline_cache_*
// يُحمَّل baza_network.js قبل هذا الملف؛ الاحتياط يُسقط إلى navigator.onLine.
function bazaNetOk() {
    return typeof bazaNetworkOkForSameOrigin === 'function'
        ? bazaNetworkOkForSameOrigin()
        : navigator.onLine;
}

const db = new Dexie('SchoolOfflineDB');
db.version(3).stores({
    offlineQueue: '++id, url, method, body, timestamp',
    cache: 'key, data, timestamp',
});

const API_BASE = '/canteen/api/';
const BOOTSTRAP_KEY = 'offline_bootstrap_v1';
const PAGE_SIZE = 20;

function parseSessionPermissionsList() {
    try {
        const raw = sessionStorage.getItem('user_permissions');
        if (!raw || !raw.trim()) return [];
        const p = JSON.parse(raw);
        return Array.isArray(p) ? p : [];
    } catch (e) {
        return [];
    }
}

/**
 * يطابق من يمنحه الخادم نسخة محلية: offline_cache_students + (تسيير أو مطعم).
 * القالب يضبط data-offline-bootstrap من إعدادات المدير؛ الجلسة احتياط بعد تسجيل الدخول.
 */
function userEligibleForOfflineBootstrapUi() {
    if (document.body && document.body.getAttribute('data-offline-bootstrap') === '1') {
        return true;
    }
    const perms = parseSessionPermissionsList();
    if (perms.indexOf('offline_cache_students') < 0) return false;
    return (
        perms.indexOf('access_management') >= 0 || perms.indexOf('access_canteen') >= 0
    );
}

function showOfflineBootstrapCompleteToast(studentCount) {
    const el = document.getElementById('offlineBootstrapDoneToast');
    if (!el) return;
    const span = el.querySelector('.ob-toast-text');
    const n = typeof studentCount === 'number' ? studentCount : -1;
    if (span) {
        span.textContent =
            n >= 0
                ? `اكتمل تحميل النسخة المحلية (${n} تلميذ). يمكنك العمل دون اتصال؛ سيتم مزامنة التحديثات تلقائياً عند توفر الإنترنت.`
                : 'اكتمل تحميل النسخة المحلية. يمكنك العمل دون اتصال؛ سيتم مزامنة التحديثات تلقائياً عند توفر الإنترنت.';
    }
    el.style.display = 'flex';
    if (window.__offlineBootstrapToastTimer) {
        clearTimeout(window.__offlineBootstrapToastTimer);
    }
    window.__offlineBootstrapToastTimer = setTimeout(() => {
        el.style.display = 'none';
    }, 6000);
}

function setOfflineBootstrapLoaderVisible(visible) {
    const el = document.getElementById('offlineBootstrapLoader');
    if (!el) return;
    el.style.display = visible ? 'block' : 'none';
    el.setAttribute('aria-busy', visible ? 'true' : 'false');
}

function updateStatus(status) {
    const banner = document.getElementById('offlineBanner');
    const syncNotif = document.getElementById('syncNotification');

    if (status === 'offline') {
        if (banner) banner.style.display = 'block';
        if (syncNotif) syncNotif.style.display = 'none';
    } else if (status === 'syncing') {
        if (banner) banner.style.display = 'none';
        if (syncNotif) syncNotif.style.display = 'flex';
    } else {
        if (banner) banner.style.display = 'none';
        if (syncNotif) syncNotif.style.display = 'none';
    }
}

window.addEventListener('online', () => {
    updateStatus('online');
    processOfflineQueue();
    refreshOfflineBootstrap();
});
window.addEventListener('offline', () => updateStatus('offline'));
if (!bazaNetOk()) updateStatus('offline');

setInterval(() => {
    if (bazaNetOk()) {
        processOfflineQueue();
    }
}, 30000);

async function serializeBody(body) {
    if (!body) return null;
    if (typeof body === 'string') return body;

    if (body instanceof FormData) {
        const obj = {};
        for (let [key, value] of body.entries()) {
            if (value instanceof File || value instanceof Blob) {
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

const originalFetch = window.fetch;

function parseStudentsListUrl(urlStr) {
    try {
        const u = new URL(urlStr, window.location.origin);
        if (!u.pathname.includes('/canteen/api/students/')) return null;
        if (/\/students\/\d+(\/|$)/.test(u.pathname)) return null;
        if (u.pathname.includes('bulk') || u.pathname.includes('filters')) return null;
        const p = u.searchParams;
        return {
            page: Math.max(1, parseInt(p.get('page') || '1', 10) || 1),
            academic_year: p.get('academic_year') || '',
            class_name: p.get('class_name') || '',
            search: (p.get('search') || '').trim(),
        };
    } catch (e) {
        return null;
    }
}

function norm(s) {
    return (s || '').toString().toLowerCase();
}

function filterStudents(all, params) {
    let rows = all || [];
    if (params.academic_year) {
        rows = rows.filter((s) => (s.academic_year || '') === params.academic_year);
    }
    if (params.class_name) {
        const c = params.class_name;
        rows = rows.filter(
            (s) => (s.class_name || '') === c || (s.class_code || '') === c
        );
    }
    if (params.search) {
        const q = norm(params.search);
        rows = rows.filter(
            (s) =>
                norm(s.student_id_number).includes(q) ||
                norm(s.first_name).includes(q) ||
                norm(s.last_name).includes(q)
        );
    }
    return rows;
}

function buildStudentsListResponse(all, params) {
    const filtered = filterStudents(all, params);
    const count = filtered.length;
    const start = (params.page - 1) * PAGE_SIZE;
    const results = filtered.slice(start, start + PAGE_SIZE);
    return new Response(JSON.stringify({ count, results }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
    });
}

function customSortKey(item) {
    if (!item) return [999, ''];
    const m = String(item).match(/\d+/);
    return m ? [parseInt(m[0], 10), item] : [999, item];
}

function buildOfflineFiltersPayload(students) {
    const list = students || [];
    const levels = [
        ...new Set(list.map((s) => s.academic_year).filter(Boolean)),
    ].sort((a, b) => {
        const ka = customSortKey(a);
        const kb = customSortKey(b);
        return ka[0] - kb[0] || String(ka[1]).localeCompare(String(kb[1]));
    });

    const level_class_map = {};
    levels.forEach((level) => {
        const clsSet = new Set();
        list
            .filter((s) => s.academic_year === level)
            .forEach((s) => {
                if (s.class_code) clsSet.add(String(s.class_code).trim());
                else if (s.class_name) clsSet.add(String(s.class_name).trim());
            });
        level_class_map[level] = [...clsSet].sort((a, b) => {
            const ka = customSortKey(a);
            const kb = customSortKey(b);
            return ka[0] - kb[0] || String(ka[1]).localeCompare(String(kb[1]));
        });
    });

    const classes = [
        ...new Set(
            list.flatMap((s) =>
                [s.class_code, s.class_name].filter(Boolean).map((x) => String(x).trim())
            )
        ),
    ].sort((a, b) => {
        const ka = customSortKey(a);
        const kb = customSortKey(b);
        return ka[0] - kb[0] || String(ka[1]).localeCompare(String(kb[1]));
    });

    return { levels, classes, level_class_map };
}

async function tryOfflineStudentsList(urlStr) {
    const params = parseStudentsListUrl(urlStr);
    if (!params) return null;
    const row = await db.cache.get(BOOTSTRAP_KEY);
    if (!row || !row.data || !Array.isArray(row.data.students)) return null;
    return buildStudentsListResponse(row.data.students, params);
}

async function tryOfflineStudentFilters(urlStr) {
    if (!urlStr.includes('/canteen/api/students/filters/')) return null;
    const row = await db.cache.get(BOOTSTRAP_KEY);
    if (!row || !row.data || !Array.isArray(row.data.students)) return null;
    const payload = buildOfflineFiltersPayload(row.data.students);
    return new Response(JSON.stringify(payload), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
    });
}

const OFFLINE_BOOTSTRAP_LOADER_MIN_MS = 480;

async function refreshOfflineBootstrap() {
    if (!bazaNetOk()) return;
    const showLoader = userEligibleForOfflineBootstrapUi();
    const t0 = Date.now();
    let savedStudents = false;
    let savedCount = 0;
    if (showLoader) setOfflineBootstrapLoaderVisible(true);
    try {
        const r = await originalFetch('/canteen/api/offline/bootstrap/?_t=' + Date.now(), {
            credentials: 'same-origin',
        });
        if (!r.ok) {
            console.warn('[OfflineManager] bootstrap HTTP', r.status, r.statusText);
            return;
        }
        const data = await r.json();
        if (Array.isArray(data.students)) {
            await db.cache.put({ key: BOOTSTRAP_KEY, data, timestamp: Date.now() });
            savedStudents = true;
            savedCount = data.students.length;
        } else {
            await db.cache.delete(BOOTSTRAP_KEY);
            if (showLoader) {
                console.warn(
                    '[OfflineManager] لم تُمنح نسخة محلية (فعّل «العمل بالنسخة المحلية» من إدارة المستخدمين مع تسيير/مطعم).'
                );
            }
        }
    } catch (e) {
        console.warn('[OfflineManager] bootstrap failed', e);
    } finally {
        if (showLoader) {
            const wait = Math.max(0, OFFLINE_BOOTSTRAP_LOADER_MIN_MS - (Date.now() - t0));
            setTimeout(() => {
                setOfflineBootstrapLoaderVisible(false);
                if (savedStudents) {
                    showOfflineBootstrapCompleteToast(savedCount);
                }
            }, wait);
        }
    }
}

window.fetch = async (...args) => {
    let [resource, config] = args;
    const url = resource instanceof Request ? resource.url : resource;
    let method = 'GET';
    if (resource instanceof Request) method = resource.method || 'GET';
    else if (config && config.method) method = config.method;
    const isExcluded =
        url.includes('/api/import_historical_expert_data/') ||
        url.includes('/api/import_eleve/') ||
        url.includes('/api/offline/bootstrap/');

    if (
        method === 'GET' &&
        url.includes(API_BASE) &&
        !isExcluded &&
        !bazaNetOk() &&
        userEligibleForOfflineBootstrapUi()
    ) {
        const f1 = await tryOfflineStudentFilters(url);
        if (f1) return f1;
        const s1 = await tryOfflineStudentsList(url);
        if (s1) return s1;
    }

    if (
        ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method) &&
        url.includes(API_BASE) &&
        !isExcluded
    ) {
        if (!bazaNetOk()) {
            if (!userEligibleForOfflineBootstrapUi()) {
                return new Response(
                    JSON.stringify({
                        error: 'لا تتوفر المزامنة المحلية لهذا الحساب. فعّل «العمل بالنسخة المحلية» من إدارة المستخدمين.',
                    }),
                    {
                        status: 503,
                        headers: { 'Content-Type': 'application/json' },
                    }
                );
            }
            return await queueRequest(url, config || {});
        }
    }

    try {
        const res = await originalFetch(...args);
        if (
            userEligibleForOfflineBootstrapUi() &&
            method === 'GET' &&
            url.includes('/canteen/api/students/') &&
            !url.includes('filters') &&
            res.ok
        ) {
            try {
                const clone = res.clone();
                const json = await clone.json();
                const row = await db.cache.get(BOOTSTRAP_KEY);
                if (row && row.data && Array.isArray(row.data.students) && json.results) {
                    const byId = new Map(row.data.students.map((s) => [s.id, s]));
                    json.results.forEach((s) => byId.set(s.id, s));
                    row.data.students = Array.from(byId.values());
                    await db.cache.put({ key: BOOTSTRAP_KEY, data: row.data, timestamp: Date.now() });
                }
            } catch (e) {
                /* ignore */
            }
        }
        return res;
    } catch (error) {
        if (
            ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method) &&
            url.includes(API_BASE) &&
            !isExcluded
        ) {
            if (!userEligibleForOfflineBootstrapUi()) {
                throw error;
            }
            return await queueRequest(url, config || {});
        }
        if (
            method === 'GET' &&
            url.includes(API_BASE) &&
            !isExcluded &&
            userEligibleForOfflineBootstrapUi()
        ) {
            const f1 = await tryOfflineStudentFilters(url);
            if (f1) return f1;
            const s1 = await tryOfflineStudentsList(url);
            if (s1) return s1;
        }
        throw error;
    }
};

async function queueRequest(url, config) {
    try {
        const serializedBody = await serializeBody(config.body);
        const m = (config && config.method && String(config.method)) || 'POST';
        await db.offlineQueue.add({
            url: url,
            method: m.toUpperCase(),
            body: serializedBody,
            timestamp: Date.now(),
        });

        return new Response(JSON.stringify({ message: 'Saved offline (Pending)' }), {
            status: 202,
            statusText: 'Accepted',
            headers: { 'Content-Type': 'application/json' },
        });
    } catch (e) {
        console.error('Offline Save Failed', e);
        throw e;
    }
}

async function processOfflineQueue() {
    const count = await db.offlineQueue.count();
    if (count === 0) return;

    updateStatus('syncing');
    const items = await db.offlineQueue.toArray();

    try {
        const response = await originalFetch('/canteen/api/pending_updates/sync/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('baza_school_csrf_v2'),
            },
            body: JSON.stringify(items),
        });

        if (response.ok) {
            await db.offlineQueue.clear();
            window.dispatchEvent(new CustomEvent('sync-complete'));
            const syncNotif = document.getElementById('syncNotification');
            if (syncNotif) {
                syncNotif.innerHTML = '<i class="fas fa-check"></i> تمت المزامنة';
                setTimeout(() => {
                    updateStatus('online');
                }, 2000);
            }
            refreshOfflineBootstrap();
        } else {
            console.error('Sync Failed', await response.text());
            updateStatus('online');
        }
    } catch (e) {
        console.error('Sync Error', e);
        updateStatus('offline');
    }
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === name + '=') {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

document.addEventListener('DOMContentLoaded', () => {
    if (bazaNetOk()) refreshOfflineBootstrap();
});

window.addEventListener('sync-complete', () => {
    if (bazaNetOk()) refreshOfflineBootstrap();
});

window.OfflineManager = {
    getLocalPending: async () => {
        return await db.offlineQueue.toArray();
    },
    syncNow: () => processOfflineQueue(),
    refreshBootstrap: refreshOfflineBootstrap,
    saveCache: async (key, data) => {
        try {
            await db.cache.put({ key: key, data: data, timestamp: Date.now() });
        } catch (e) {
            console.warn('Cache Save Failed', e);
        }
    },
    getCache: async (key) => {
        try {
            const item = await db.cache.get(key);
            return item ? item.data : null;
        } catch (e) {
            return null;
        }
    },
};
