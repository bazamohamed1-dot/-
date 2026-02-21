/* Dashboard JS Logic */

// Global Variables
let currentStudents = [];
let currentPage = 1;
const itemsPerPage = 20;

async function initDashboard() {
    console.log("Initializing Dashboard...");
    await loadStudents();
}

// 1. Fetch Students
async function loadStudents() {
    const tableBody = document.querySelector('#std-table tbody');
    tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center;">جاري التحميل...</td></tr>';

    try {
        const snapshot = await db.collection('students').orderBy('last_name').get();
        currentStudents = [];
        snapshot.forEach(doc => {
            currentStudents.push({ id: doc.id, ...doc.data() });
        });
        renderStudentTable();
    } catch (e) {
        console.error("Error loading students:", e);
        tableBody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:red;">خطأ في تحميل البيانات</td></tr>';
    }
}

// 2. Render Table with Pagination & Filtering
function renderStudentTable() {
    const search = document.getElementById('std-search').value.toLowerCase();

    // Filter
    let filtered = currentStudents.filter(s => {
        const name = (s.first_name + ' ' + s.last_name).toLowerCase();
        return name.includes(search) || s.student_id_number.includes(search);
    });

    const tbody = document.querySelector('#std-table tbody');
    tbody.innerHTML = '';

    if (filtered.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;">لا توجد نتائج</td></tr>';
        return;
    }

    // Pagination (Simple client-side for now)
    // For large datasets, server-side pagination (limit/startAfter) is better,
    // but client-side is faster for < 2000 students.

    filtered.slice(0, 50).forEach(s => { // Limit render for performance
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="western-nums">${s.student_id_number}</td>
            <td>${s.last_name}</td>
            <td>${s.first_name}</td>
            <td>${s.class_name}</td>
            <td>
                <div style="display:flex; gap:5px; justify-content:center;">
                    ${renderActionButtons(s)}
                </div>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function renderActionButtons(student) {
    let btns = '';
    // Check permissions from currentUserProfile (global from employee.html)
    const p = currentUserProfile.permissions || [];
    const isDir = currentUserProfile.role === 'director';

    // Attendance Button
    if (isDir || p.includes('student_edit') || p.includes('access_management')) {
        btns += `<button onclick="reportAbsence('${student.id}')" class="btn btn-danger btn-sm" title="تسجيل غياب"><i class="fas fa-user-times"></i></button>`;
    }

    // Photo Button
    if (isDir || p.includes('student_edit')) {
        btns += `<button onclick="triggerPhotoUpload('${student.id}')" class="btn btn-primary btn-sm" title="تحديث الصورة"><i class="fas fa-camera"></i></button>`;
    }

    return btns;
}

// Search Listener
document.getElementById('std-search').addEventListener('keyup', renderStudentTable);

// --- Actions ---

async function reportAbsence(id) {
    // Show Modal instead of simple prompt
    const reason = prompt("سبب الغياب (اختياري):");
    if (reason === null) return;

    try {
        await db.collection('pending_updates').add({
            type: 'ATTENDANCE',
            student_ref: id,
            details: { status: 'ABSENT', reason: reason },
            submitted_by: currentUserProfile.username,
            submitted_at: firebase.firestore.FieldValue.serverTimestamp(),
            status: 'pending',
            date: new Date().toISOString().split('T')[0]
        });
        alert("تم إرسال تسجيل الغياب للموافقة.");
    } catch(e) {
        alert("خطأ: " + e.message);
    }
}

// Global scope binding
window.initDashboard = initDashboard;
