const API_URL = "http://127.0.0.1";

// 1. وظيفة الحفظ (زر حفظ)
async function saveStudentData() {
    const studentData = {
        student_id_number: document.getElementById('studentID').value,
        last_name: document.getElementById('lastName').value,
        first_name: document.getElementById('firstName').value,
        gender: document.getElementById('gender').value,
        date_of_birth: document.getElementById('dateOfBirth').value,
        place_of_birth: document.getElementById('placeOfBirth').value,
        academic_year: document.getElementById('academicYear').value,
        class_name: document.getElementById('className').value,
        attendance_system: document.getElementById('attendanceSystem').value,
        enrollment_number: document.getElementById('enrollmentNumber').value,
        enrollment_date: document.getElementById('enrollmentDate').value,
        exit_date: document.getElementById('exitDate').value || null,
        guardian_name: document.getElementById('guardianName').value,
        mother_name: document.getElementById('motherName').value,
        address: document.getElementById('address').value,
        guardian_phone: document.getElementById('guardianPhone').value,
    };

    // التحقق من طول رقم التعريف (الصرامة التي اتفقنا عليها)
    if (studentData.student_id_number.length !== 16) {
        alert("خطأ: رقم التعريف يجب أن يتكون من 16 رقماً بالضبط.");
        return;
    }

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(studentData)
        });

        if (response.ok) {
            alert("✅ تم حفظ بيانات التلميذ بنجاح في متوسطة بوشنافة عمر");
            clearForm(); // تفريغ الحقول بعد النجاح
        } else {
            const error = await response.json();
            alert("❌ فشل الحفظ: " + JSON.stringify(error));
        }
    } catch (err) {
        alert("⚠️ خطأ في الاتصال بالسيرفر. سيتم الحفظ محلياً (Offline Mode) قريباً.");
    }
}

// 2. وظيفة تفريغ الحقول (زر جديد)
function clearForm() {
    const inputs = document.querySelectorAll('input, select');
    inputs.forEach(input => input.value = "");
    document.getElementById('studentPhoto').style.display = 'none';
    document.getElementById('userIcon').style.display = 'block';
}

// 3. وظيفة البحث (عند الضغط على بحث)
async function searchStudents() {
    const name = document.getElementById('searchInput').value;
    const response = await fetch(`${API_URL}search_by_name/?name=${name}`);
    const results = await response.json();
    
    // سيتم لاحقاً برمجة عرض النتائج في الجدول السفلي
    console.log("نتائج البحث:", results);
}

// ربط الأزرار بالوظائف
document.querySelector('.btn-save').addEventListener('click', saveStudentData);
document.querySelector('.btn-new').addEventListener('click', clearForm);

// تعريف الوظائف المفقودة لمنع الأخطاء
function uploadPhoto() {
    console.log("تم الضغط على تحميل الصورة");
    alert("هذه الميزة قيد البرمجة حالياً");
}

function editData() {
    alert("وظيفة التعديل سيتم برمجتها بعد استقرار الحفظ");
}

function deleteData() {
    alert("وظيفة الحذف سيتم برمجتها لاحقاً");
}

function importExcel() {
    alert("جاري العمل على كود استيراد ملفات الإكسل");
}

function exitApp() {
    if(confirm("هل تريد الخروج من البرنامج؟")) {
        window.close();
    }
}
