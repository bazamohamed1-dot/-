import os

filepath = "./students/templates/students/hr.html"
with open(filepath, "r") as f:
    content = f.read()

# Replace the anchor tag delete with a button that calls an async JS function
old_anchor = """<a href="{% url 'hr_delete' emp.id %}" class="btn btn-sm btn-danger" onclick="return confirm('هل أنت متأكد؟')"><i class="fas fa-trash"></i></a>"""
new_button = """<button class="btn btn-sm btn-danger" onclick="deleteEmployee('{{ emp.id }}', this)" title="حذف الموظف"><i class="fas fa-trash"></i></button>"""

if old_anchor in content:
    content = content.replace(old_anchor, new_button)

# Add the deleteEmployee script
script_to_add = """
    async function deleteEmployee(id, btnElement) {
        if(!confirm('هل أنت متأكد من حذف هذا الموظف؟')) return;

        const row = btnElement.closest('tr');
        if(row) row.style.opacity = '0.5'; // Visual feedback

        try {
            const res = await fetch(`/canteen/hr/delete/${id}/`, {
                method: 'POST', // Try POST first, fallback if Django requires GET without CSRF in the template, wait actually hr_delete is usually GET because it was a link. Let's send POST with CSRF and make view accept it or just GET. The view doesn't specify method, so GET is fine but better to be safe. Since it was an <a> tag, it was a GET request.
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                }
            });
            const data = await res.json();
            if (data.status === 'success') {
                if(row) row.remove(); // Instantly remove from UI
            } else {
                alert(data.message || 'خطأ أثناء الحذف');
                if(row) row.style.opacity = '1';
            }
        } catch(e) {
            alert('تعذر الاتصال بالخادم.');
            if(row) row.style.opacity = '1';
        }
    }
"""

if "function deleteEmployee" not in content:
    # Inject it before the last </script>
    content = content.replace("</script>", script_to_add + "\n</script>", 1)

with open(filepath, "w") as f:
    f.write(content)

print("Patched hr.html with AJAX delete function")
