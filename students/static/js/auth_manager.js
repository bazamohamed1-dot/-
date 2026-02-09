document.addEventListener('DOMContentLoaded', async () => {
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
             fetch('/canteen/auth/logout/', {
                 method: 'POST',
                 headers: {'X-CSRFToken': getCookie('csrftoken')}
             }).finally(() => {
                 window.location.href = '/canteen/';
             });
        }
    } else {
        // If we have a token, just check role redirection first to avoid UI flash
        // Verification happens in background
        checkRoleRedirect(role);

        // Verify online if possible (Background Check)
        if (navigator.onLine) {
            const deviceId = localStorage.getItem('device_id');
            const headers = {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken')
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
            .then(data => {
                if(data && data.role && data.role !== role) {
                     sessionStorage.setItem('user_role', data.role);
                     checkRoleRedirect(data.role);
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
            const headers = { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') };
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
                sessionStorage.setItem('session_token', data.token);
                sessionStorage.setItem('user_role', data.role);
                sessionStorage.setItem('username', data.username);
                if (data.device_id) {
                    localStorage.setItem('device_id', data.device_id);
                }
                location.reload();
            } else {
                errorDiv.textContent = data.error || 'فشل تسجيل الدخول';
                errorDiv.style.display = 'block';
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
    sessionStorage.clear();
    const csrftoken = getCookie('csrftoken');
    try {
        await fetch('/canteen/auth/logout/', {
            method: 'POST',
            headers: {'X-CSRFToken': csrftoken}
        });
    } catch (e) { console.error(e); }
    location.href = '/canteen/';
}

function checkRoleRedirect(role) {
    const path = window.location.pathname;

    // Hide Sidebar Links Logic
    const sidebar = document.querySelector('.sidebar .nav-links');
    if (sidebar) {
        const links = sidebar.querySelectorAll('.nav-link');
        links.forEach(link => {
            const href = link.getAttribute('href');
            let show = false;

            if (role === 'director') show = true;
            else if (role === 'storekeeper') {
                if (href.includes('ui') || href.includes('canteen_home')) show = true;
                // Storekeeper sees Canteen only.
            } else if (role === 'librarian') {
                if (href.includes('library')) show = true;
            } else if (role === 'secretariat') {
                if (href.includes('management') || href.includes('list')) show = true;
            } else if (role === 'archivist') {
                if (href.includes('archive')) show = true;
            }

            if (!show) {
                link.parentElement.style.display = 'none';
            } else {
                 link.parentElement.style.display = 'block';
            }
        });
    }

    // Director sees everything, no redirect needed usually, unless specific landing
    if (role === 'director') return;

    // Force Redirect
    if (role === 'storekeeper') {
        if (!path.includes('canteen/ui') && !path.includes('canteen_stats')) {
            window.location.href = '/canteen/ui/';
        }
    } else if (role === 'librarian') {
        if (!path.includes('library')) {
            window.location.href = '/canteen/library/';
        }
    } else if (role === 'secretariat') {
         if (!path.includes('management') && !path.includes('student_list')) {
            window.location.href = '/canteen/management/';
        }
    } else if (role === 'archivist') {
         if (!path.includes('archive')) {
            window.location.href = '/canteen/archive/';
        }
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
window.getCookie = getCookie;
window.logout = logout;
