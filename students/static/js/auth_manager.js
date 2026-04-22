function bazaNetOk() {
    return typeof bazaNetworkOkForSameOrigin === 'function'
        ? bazaNetworkOkForSameOrigin()
        : navigator.onLine;
}

const OFFLINE_SESSION_KEYS = {
    token: 'offline_session_token',
    role: 'offline_user_role',
    username: 'offline_username',
    perms: 'offline_user_permissions',
};

function mirrorSessionToOfflineStorage(data) {
    if (!data || !data.token) return;
    try {
        localStorage.setItem(OFFLINE_SESSION_KEYS.token, data.token);
        if (data.role) localStorage.setItem(OFFLINE_SESSION_KEYS.role, data.role);
        if (data.username) localStorage.setItem(OFFLINE_SESSION_KEYS.username, data.username);
        if (data.permissions) {
            localStorage.setItem(OFFLINE_SESSION_KEYS.perms, JSON.stringify(data.permissions));
        } else {
            localStorage.removeItem(OFFLINE_SESSION_KEYS.perms);
        }
    } catch (e) {
        console.warn('mirrorSessionToOfflineStorage', e);
    }
}

function clearOfflineSessionMirror() {
    try {
        Object.values(OFFLINE_SESSION_KEYS).forEach((k) => localStorage.removeItem(k));
    } catch (e) { /* ignore */ }
}

function restoreSessionFromOfflineMirror() {
    if (navigator.onLine) return;
    if (sessionStorage.getItem('session_token')) return;
    const t = localStorage.getItem(OFFLINE_SESSION_KEYS.token);
    if (!t) return;
    sessionStorage.setItem('session_token', t);
    const r = localStorage.getItem(OFFLINE_SESSION_KEYS.role);
    if (r) sessionStorage.setItem('user_role', r);
    const u = localStorage.getItem(OFFLINE_SESSION_KEYS.username);
    if (u) sessionStorage.setItem('username', u);
    const p = localStorage.getItem(OFFLINE_SESSION_KEYS.perms);
    if (p) sessionStorage.setItem('user_permissions', p);
}

document.addEventListener('DOMContentLoaded', async () => {
    restoreSessionFromOfflineMirror();
    const token = sessionStorage.getItem('session_token');
    const role = sessionStorage.getItem('user_role');

    // Ensure Device ID exists
    let deviceId = localStorage.getItem('device_id');
    if (!deviceId) {
        // Generate a random UUID-like string
        deviceId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
        localStorage.setItem('device_id', deviceId);
        console.log("New Device ID generated:", deviceId);
    }

    // Auth Check
    if (!token) {
        // Redirect to landing if not there
        // If we are on a protected page but have no token, we MUST logout from backend to clear cookies
        // Otherwise, backend sees us as logged in and redirects back -> Infinite Loop
        if (window.location.pathname !== '/' && window.location.pathname !== '/canteen/') {
            if (!bazaNetOk()) {
                window.location.replace('/canteen/');
            } else {
                fetch('/canteen/auth/logout/', {
                    method: 'POST',
                    headers: {'X-CSRFToken': getCookie('baza_school_csrf_v2')}
                }).finally(() => {
                    window.location.href = '/canteen/';
                });
            }
        }
    } else {
        // If we have a token, just check role redirection first to avoid UI flash
        // Verification happens in background
        const perms = (function(){
            try {
                const p = sessionStorage.getItem('user_permissions');
                return p ? JSON.parse(p) : [];
            } catch(e){ return []; }
        })();
        checkRoleRedirect(role, perms);

        // Verify online if possible (Background Check)
        if (bazaNetOk()) {
            const deviceId = localStorage.getItem('device_id');
            const headers = {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('baza_school_csrf_v2')
            };
            if(deviceId) headers['X-Device-ID'] = deviceId;

            fetch('/canteen/auth/verify/', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({ token: token })
            })
            .then(res => {
                if (res.status === 401) {
                    logout();
                } else if (res.ok) {
                    return res.json();
                }
            })
            .then(async (data) => {
                if (data) {
                    if (data.clear_offline_storage && typeof window.clearSchoolAppOfflineCaches === 'function') {
                        try {
                            await window.clearSchoolAppOfflineCaches();
                        } catch (e) { console.warn(e); }
                        window.location.reload();
                        return;
                    }
                    if (data.role && data.role !== role) {
                        sessionStorage.setItem('user_role', data.role);
                    }
                    if (data.permissions) {
                        sessionStorage.setItem('user_permissions', JSON.stringify(data.permissions));
                    }
                    mirrorSessionToOfflineStorage({
                        token: sessionStorage.getItem('session_token'),
                        role: data.role || sessionStorage.getItem('user_role'),
                        username: sessionStorage.getItem('username'),
                        permissions: data.permissions,
                    });
                    checkRoleRedirect(data.role || role, data.permissions);
                }
            })
            .catch(e => console.log("Auth background check failed", e));
        }
    }

    // Login Form Handler
    document.getElementById('loginForm')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        const errorDiv = document.getElementById('loginError');

        try {
            const deviceId = localStorage.getItem('device_id');
            const headers = { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('baza_school_csrf_v2') };
            if(deviceId) headers['X-Device-ID'] = deviceId;

            const response = await fetch('/canteen/auth/login/', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({ username, password })
            });

            const text = await response.text();
            let data;
            try {
                data = JSON.parse(text);
            } catch (e) {
                console.error("Server Error (Non-JSON):", text);
                errorDiv.textContent = 'خطأ في الخادم (500). يرجى المحاولة لاحقاً.';
                errorDiv.style.display = 'block';
                return;
            }

            if (response.ok) {
                try {
                    if (typeof window.clearSchoolAppOfflineCaches === 'function') {
                        const prevUser = localStorage.getItem('offline_last_user');
                        if (data.clear_offline_storage || (prevUser && prevUser !== data.username)) {
                            await window.clearSchoolAppOfflineCaches();
                        }
                    }
                } catch (e) { console.warn('clearSchoolAppOfflineCaches', e); }
                localStorage.setItem('offline_last_user', data.username);
                sessionStorage.setItem('session_token', data.token);
                sessionStorage.setItem('user_role', data.role);
                sessionStorage.setItem('username', data.username);
                if (data.permissions) {
                    sessionStorage.setItem('user_permissions', JSON.stringify(data.permissions));
                } else {
                    sessionStorage.removeItem('user_permissions');
                }
                mirrorSessionToOfflineStorage({
                    token: data.token,
                    role: data.role,
                    username: data.username,
                    permissions: data.permissions,
                });
                if (data.device_id) {
                    localStorage.setItem('device_id', data.device_id);
                }
                location.reload();
            } else {
                // Handle Lockout
                if (data.code === 'LOCKED') {
                    // Disable all inputs and button
                    const inputs = document.querySelectorAll('#loginForm input, #loginForm button');
                    inputs.forEach(el => el.disabled = true);

                    errorDiv.innerHTML = '<i class="fas fa-lock"></i> ' + (data.error || 'تم قفل الحساب. اتصل بالمدير.');
                    errorDiv.style.display = 'block';
                    errorDiv.style.backgroundColor = '#fee2e2';
                    errorDiv.style.color = '#991b1b';
                    errorDiv.style.fontWeight = 'bold';
                } else {
                    errorDiv.textContent = data.error || 'فشل تسجيل الدخول';
                    errorDiv.style.display = 'block';
                }
            }
        } catch (e) {
            errorDiv.textContent = 'خطأ في الاتصال';
            errorDiv.style.display = 'block';
        }
    });

    document.getElementById('logoutBtn')?.addEventListener('click', (e) => {
        e.preventDefault();
        logout();
    });

    // Sync Logout across tabs
    // Note: sessionStorage is not shared across tabs/windows in the same way localStorage is for storage events.
    // However, we keep this listener if the app uses localStorage for other syncs, or if we decide to revert.
    // For now, removing the listener for session_token on storage as sessionStorage doesn't trigger it across tabs.
});

function showLogin() {
    window.location.href = '/canteen/';
}

async function logout() {
    if (!bazaNetOk()) {
        const ok = confirm(
            'أنت غير متصل بالخادم: بعد تسجيل الخروج لن تتمكن من تسجيل الدخول مجدداً حتى يعود الاتصال.\n\n' +
            'للعمل دون إنترنت، يُفضّل عدم الخروج أثناء الانقطاع.\n\n' +
            'هل تريد المتابعة؟'
        );
        if (!ok) return;
    }
    // 1. Clear session (لا نُفرّغ cache/SW هنا — يبقى للعمل دون اتصال حتى تبديل مستخدم أو إجراء المدير)
    sessionStorage.clear();
    localStorage.removeItem('session_token');
    localStorage.removeItem('user_role');
    clearOfflineSessionMirror();

    // 2. Backend Logout
    const csrftoken = getCookie('baza_school_csrf_v2');
    try {
        await fetch('/canteen/auth/logout/', {
            method: 'POST',
            headers: {'X-CSRFToken': csrftoken}
        });
    } catch (e) { console.error("Backend logout failed", e); }

    try {
        const authChannel = new BroadcastChannel('auth_channel');
        authChannel.postMessage('logout');
    } catch (e) { /* ignore */ }

    // 3. Hard Redirect
    window.location.replace('/canteen/');
}

function countNavSurfaces(perms) {
    const keys = [
        'access_canteen', 'access_library', 'access_management', 'access_archive',
        'access_guidance', 'access_hr', 'access_parents',
    ];
    let n = keys.filter(k => perms.indexOf(k) >= 0).length;
    if (perms.indexOf('access_analytics') >= 0 || perms.indexOf('access_advanced_analytics') >= 0) n += 1;
    return n;
}

function checkRoleRedirect(role, permissions) {
    const path = window.location.pathname;
    const perms = Array.isArray(permissions) ? permissions : [];
    const hasPerm = function(p) { return perms.indexOf(p) >= 0; };

    const sidebar = document.querySelector('.sidebar .nav-links');
    if (sidebar) {
        const links = sidebar.querySelectorAll('.nav-link');
        links.forEach(link => {
            const href = link.getAttribute('href') || '';
            let show = false;

            if (role === 'director') {
                show = true;
            } else if (perms.length > 0) {
                if (href.includes('analytics')) show = hasPerm('access_analytics') || hasPerm('access_advanced_analytics');
                else if (href.includes('management') || href.includes('list')) show = hasPerm('access_management');
                else if (href.includes('ui') || href.includes('canteen')) show = hasPerm('access_canteen');
                else if (href.includes('library')) show = hasPerm('access_library');
                else if (href.includes('archive')) show = hasPerm('access_archive');
                else if (href.includes('hr')) show = hasPerm('access_hr');
                else if (href.includes('parents')) show = hasPerm('access_parents');
                else if (href.includes('guidance')) show = hasPerm('access_guidance');
                else if (href.includes('tasks')) show = hasPerm('access_tasks');
                else if (href.includes('settings')) show = hasPerm('manage_settings');
                else show = true;
            } else {
                if (role === 'storekeeper') show = href.includes('ui') || href.includes('canteen');
                else if (role === 'librarian') show = href.includes('library');
                else if (role === 'archivist') show = href.includes('archive');
                else if (role === 'secretariat') show = href.includes('management') || href.includes('list');
                else show = true;
            }

            link.parentElement.style.display = show ? 'block' : 'none';
        });
    }

    if (role === 'director') return;

    function soleHomeUrl() {
        const p = perms;
        if (p.length > 0) {
            if (countNavSurfaces(p) !== 1) return null;
            if (p.indexOf('access_canteen') >= 0) return '/canteen/ui/';
            if (p.indexOf('access_library') >= 0) return '/canteen/library/';
            if (p.indexOf('access_management') >= 0) return '/canteen/management/';
            if (p.indexOf('access_archive') >= 0) return '/canteen/archive/';
            if (p.indexOf('access_guidance') >= 0) return '/canteen/guidance/';
            if (p.indexOf('access_hr') >= 0) return '/canteen/hr/';
            if (p.indexOf('access_parents') >= 0) return '/canteen/parents/';
            if (p.indexOf('access_analytics') >= 0 || p.indexOf('access_advanced_analytics') >= 0) return '/canteen/analytics/';
            return null;
        }
        if (role === 'storekeeper') return '/canteen/ui/';
        if (role === 'librarian') return '/canteen/library/';
        if (role === 'archivist') return '/canteen/archive/';
        if (role === 'secretariat') return '/canteen/management/';
        return null;
    }

    function alreadyOnModule(home) {
        if (home === '/canteen/ui/') return path.includes('/canteen/ui') || path.includes('/canteen_stats');
        if (home === '/canteen/library/') return path.includes('/library');
        if (home === '/canteen/management/') return path.includes('/management') || path.includes('/list');
        if (home === '/canteen/archive/') return path.includes('/archive');
        if (home === '/canteen/guidance/') return path.includes('/guidance');
        if (home === '/canteen/hr/') return path.includes('/hr');
        if (home === '/canteen/parents/') return path.includes('/parents');
        if (home === '/canteen/analytics/') return path.includes('/analytics');
        return false;
    }

    const home = soleHomeUrl();
    if (home && !alreadyOnModule(home)) window.location.href = home;
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
window.getCookie = getCookie;
window.logout = logout;
