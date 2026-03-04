import re

file_path = './students/templates/students/analytics.html'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the single import button with two buttons
old_btn = """<button class="btn" style="background: #38bdf8; color: #0f172a; font-weight: bold; white-space: nowrap;" onclick="document.getElementById('importGradesModal').style.display='flex'">
                    <i class="fas fa-cloud-upload-alt"></i> استيراد العلامات
                </button>"""

new_btns = """
                <button class="btn btn-outline-primary fw-bold shadow-sm" style="white-space: nowrap; border-width: 2px;" onclick="document.getElementById('importMode').value='local'; document.getElementById('aiImportNotice').style.display='none'; document.getElementById('importGradesModal').style.display='flex'; document.getElementById('modalTitleText').innerText='استيراد محلي ذكي';">
                    <i class="fas fa-file-excel"></i> استيراد محلي
                </button>
                <button class="btn fw-bold shadow-sm" style="background-color: #a855f7; color: white; white-space: nowrap; border: 2px solid #9333ea;" onclick="document.getElementById('importMode').value='ai'; document.getElementById('aiImportNotice').style.display='block'; document.getElementById('importGradesModal').style.display='flex'; document.getElementById('modalTitleText').innerText='استيراد بالذكاء الاصطناعي';">
                    <i class="fas fa-magic"></i> استيراد AI
                </button>
"""

content = content.replace(old_btn, new_btns)

# Update the modal to include a hidden input for import mode and an AI notice
modal_title_replace = r'<h3 style="margin-top:0; color:#0f172a; border-bottom:1px solid #e2e8f0; padding-bottom:10px;">استيراد العلامات <small style="font-size:0.5em; color:#64748b;">\(ملف واحد أو عدة ملفات\)</small></h3>'
new_modal_header = """<h3 style="margin-top:0; color:#0f172a; border-bottom:1px solid #e2e8f0; padding-bottom:10px;"><span id="modalTitleText">استيراد العلامات</span> <small style="font-size:0.5em; color:#64748b;">(ملف واحد أو عدة ملفات)</small></h3>
        <div id="aiImportNotice" class="alert alert-warning" style="display:none; font-size:0.9rem;">
            <i class="fas fa-exclamation-triangle"></i> سيتم إرسال الملفات إلى خادم الذكاء الاصطناعي لتحليلها واستخراج العلامات. قد تستغرق العملية وقتاً أطول وتستهلك من رصيد الكلمات.
        </div>"""

content = re.sub(modal_title_replace, new_modal_header, content)

# Add hidden input to the form
csrf_token = "{% csrf_token %}"
content = content.replace(csrf_token, csrf_token + '\n            <input type="hidden" id="importMode" name="import_mode" value="local">')

# Pass import_mode in JS payload
js_payload_replace = "formData.append('term', term);"
new_js_payload = "formData.append('term', term);\n            formData.append('import_mode', document.getElementById('importMode').value);"
content = content.replace(js_payload_replace, new_js_payload)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated import UI in analytics.html")
