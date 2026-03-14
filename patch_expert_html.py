with open('students/templates/students/expert_analysis.html', 'r') as f:
    content = f.read()

# Add a progress/loading overlay logic
loader_div = """
<div id="loadingOverlayExpert" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 9999; flex-direction: column; align-items: center; justify-content: center; color: white; font-size: 1.5rem;">
    <div class="spinner-border text-light mb-3" role="status" style="width: 3rem; height: 3rem;"></div>
    <div id="loadingOverlayText">جاري معالجة البيانات، يرجى الانتظار...</div>
</div>
"""

if 'loadingOverlayExpert' not in content:
    content = content.replace("</head>", loader_div + "</head>")

# Update the modal upload button
content = content.replace("""        const btn = document.getElementById('btnUploadHistoricalModal');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري الرفع والتحليل...';""", """        const btn = document.getElementById('btnUploadHistoricalModal');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري الرفع والتحليل...';

        const overlay = document.getElementById('loadingOverlayExpert');
        if (overlay) {
            overlay.style.display = 'flex';
        }""")

content = content.replace("""            btn.disabled = false;
            btn.innerHTML = originalText;
            if (data.status === 'success') {""", """            btn.disabled = false;
            btn.innerHTML = originalText;
            const overlay = document.getElementById('loadingOverlayExpert');
            if (overlay) overlay.style.display = 'none';
            if (data.status === 'success') {""")

content = content.replace("""        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = originalText;
            alert('حدث خطأ أثناء الاتصال بالخادم.');""", """        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = originalText;
            const overlay = document.getElementById('loadingOverlayExpert');
            if (overlay) overlay.style.display = 'none';
            alert('حدث خطأ أثناء الاتصال بالخادم.');""")


# Update the normal upload button
content = content.replace("""        const btn = document.getElementById('btnUploadHistorical');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري الرفع...';""", """        const btn = document.getElementById('btnUploadHistorical');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> جاري الرفع...';

        const overlay = document.getElementById('loadingOverlayExpert');
        if (overlay) {
            overlay.style.display = 'flex';
        }""")

content = content.replace("""            btn.disabled = false;
            btn.innerHTML = originalText;
            if (data.status === 'success') {""", """            btn.disabled = false;
            btn.innerHTML = originalText;
            const overlay = document.getElementById('loadingOverlayExpert');
            if (overlay) overlay.style.display = 'none';
            if (data.status === 'success') {""")

with open('students/templates/students/expert_analysis.html', 'w') as f:
    f.write(content)
