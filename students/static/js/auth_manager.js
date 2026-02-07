document.addEventListener('DOMContentLoaded', async () => {
    const token = localStorage.getItem('session_token');
    const role = localStorage.getItem('user_role');
    const loginModal = document.getElementById('loginModal');

    // Auth Check
    if (!token) {
        showLogin();
    } else {
        // Verify online if possible
        if (navigator.onLine) {
            try {
                const response = await fetch('/canteen/auth/verify/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken')
                    },
                    body: JSON.stringify({ token: token })
                });

                if (response.status === 401) {
                    logout(); // Invalid session
                } else if (response.ok) {
                    const data = await response.json();
                    localStorage.setItem('user_role', data.role); // Update role
                    checkRoleRedirect(data.role);
                }
            } catch (e) {
                console.log("Auth verify failed (offline?)", e);
            }
        }
        // If offline, trust the token for now (PWA mode)
        checkRoleRedirect(role);
    }

    // Login Form Handler
    document.getElementById('loginForm')?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        const errorDiv = document.getElementById('loginError');

        try {
            const response = await fetch('/canteen/auth/login/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json();

            if (response.ok) {
                localStorage.setItem('session_token', data.token);
                localStorage.setItem('user_role', data.role);
                localStorage.setItem('username', data.username);
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
    window.addEventListener('storage', (e) => {
        if (e.key === 'session_token' && !e.newValue) {
            // Token removed -> logout
            window.location.href = '/canteen/';
        }
    });
});

function showLogin() {
    const modal = document.getElementById('loginModal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

async function logout() {
    localStorage.removeItem('session_token');
    localStorage.removeItem('user_role');
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
