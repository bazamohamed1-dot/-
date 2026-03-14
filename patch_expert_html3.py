with open('students/templates/students/expert_analysis.html', 'r') as f:
    content = f.read()

# Add overlay directly into body
if '<div id="loadingOverlayExpert">' not in content:
    content = content.replace("<body>", """<body>
<div id="loadingOverlayExpert" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 9999; flex-direction: column; align-items: center; justify-content: center; color: white; font-size: 1.5rem;">
    <div class="spinner-border text-light mb-3" role="status" style="width: 3rem; height: 3rem;"></div>
    <div>جاري معالجة البيانات، يرجى الانتظار...</div>
</div>""")
    with open('students/templates/students/expert_analysis.html', 'w') as f:
        f.write(content)
