import os

filepath = "./students/templates/students/settings.html"
with open(filepath, "r") as f:
    content = f.read()

# Add an ID to the form and a loading overlay div
if 'id="importForm"' not in content:
    content = content.replace('<form action="{% url \'import_eleve_view\' %}" method="post" enctype="multipart/form-data" style="padding: 10px 0;">',
                              '<form id="importForm" action="{% url \'import_eleve_view\' %}" method="post" enctype="multipart/form-data" style="padding: 10px 0; position:relative;">')

    # Add loading overlay HTML after the form
    overlay_html = """
    <!-- Loading Overlay -->
    <div id="loadingOverlay" style="display:none; position:absolute; top:0; left:0; width:100%; height:100%; background:rgba(255,255,255,0.8); z-index:1000; justify-content:center; align-items:center; flex-direction:column; border-radius:12px;">
        <i class="fas fa-spinner fa-spin fa-3x" style="color:#2563eb; margin-bottom:15px;"></i>
        <h3 style="color:#1e293b; margin:0;">يرجى الانتظار...</h3>
        <p style="color:#64748b;">يتم الآن استيراد ومعالجة البيانات، قد يستغرق هذا بضع دقائق.</p>
    </div>
    """

    content = content.replace('<p style="margin-top:10px; color:#64748b; font-size:0.9rem;">',
                              overlay_html + '\n        <p style="margin-top:10px; color:#64748b; font-size:0.9rem;">')

    # Add script to show overlay
    script_html = """
<script>
document.addEventListener('DOMContentLoaded', function() {
    const importForm = document.getElementById('importForm');
    const loadingOverlay = document.getElementById('loadingOverlay');
    if(importForm && loadingOverlay) {
        importForm.addEventListener('submit', function(e) {
            loadingOverlay.style.display = 'flex';
        });
    }
});
</script>
    """

    content += script_html

with open(filepath, "w") as f:
    f.write(content)

print("Updated settings.html")
