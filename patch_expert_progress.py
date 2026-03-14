with open('students/templates/students/expert_analysis.html', 'r') as f:
    content = f.read()

# Replace the current simple loading overlay with a progress bar overlay
new_overlay = """<div id="loadingOverlayExpert" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 9999; flex-direction: column; align-items: center; justify-content: center; color: white; font-family: 'Cairo', sans-serif;">
    <div style="text-align: center; max-width: 500px; width: 80%;">
        <div class="spinner-border text-primary mb-3" role="status" style="width: 3rem; height: 3rem;"></div>
        <h3 id="loadingOverlayText" class="mb-4">جاري معالجة البيانات، يرجى الانتظار...</h3>

        <div class="progress" style="height: 25px; border-radius: 15px; background-color: #333; overflow: hidden; box-shadow: inset 0 1px 3px rgba(0,0,0,0.5);">
            <div id="expertProgressBar" class="progress-bar progress-bar-striped progress-bar-animated bg-success" role="progressbar" style="width: 0%; font-size: 1.1rem; font-weight: bold; line-height: 25px; transition: width 0.4s ease;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">0%</div>
        </div>
        <p id="expertProgressSubtext" class="mt-3 text-muted" style="font-size: 0.9rem;">تتم الآن قراءة وتحليل الملفات المرفقة...</p>
    </div>
</div>"""

import re
content = re.sub(r'<div id="loadingOverlayExpert".*?</div>\s*</div>', new_overlay, content, flags=re.DOTALL)

# Add logic to simulate progress since it's a long synchronous request
progress_js = """
let progressInterval;
function startExpertProgress(text) {
    const overlay = document.getElementById('loadingOverlayExpert');
    const title = document.getElementById('loadingOverlayText');
    const bar = document.getElementById('expertProgressBar');
    const subtext = document.getElementById('expertProgressSubtext');

    if(overlay) overlay.style.display = 'flex';
    if(title) title.innerText = text || 'جاري معالجة البيانات، يرجى الانتظار...';
    if(bar) {
        bar.style.width = '0%';
        bar.innerText = '0%';
        bar.setAttribute('aria-valuenow', 0);
    }

    let currentProgress = 0;
    // Slow down progress as it reaches 90%
    progressInterval = setInterval(() => {
        if (currentProgress < 50) currentProgress += 5;
        else if (currentProgress < 80) currentProgress += 2;
        else if (currentProgress < 95) currentProgress += 0.5;

        if(bar) {
            bar.style.width = currentProgress + '%';
            bar.innerText = Math.round(currentProgress) + '%';
            bar.setAttribute('aria-valuenow', Math.round(currentProgress));
        }

        if(subtext) {
            if(currentProgress > 80) subtext.innerText = "جاري حفظ التغييرات في قاعدة البيانات...";
            else if(currentProgress > 50) subtext.innerText = "جاري استخراج وتحليل النتائج...";
            else subtext.innerText = "تتم الآن قراءة الملفات المرفقة...";
        }
    }, 500);
}

function stopExpertProgress() {
    clearInterval(progressInterval);
    const overlay = document.getElementById('loadingOverlayExpert');
    const bar = document.getElementById('expertProgressBar');

    if(bar) {
        bar.style.width = '100%';
        bar.innerText = '100%';
        bar.setAttribute('aria-valuenow', 100);
    }

    setTimeout(() => {
        if(overlay) overlay.style.display = 'none';
    }, 500); // Wait half a second before hiding to show 100%
}
"""

content = content.replace("function uploadHistoricalDataModal() {", progress_js + "\n    function uploadHistoricalDataModal() {")

# Update usages
content = content.replace("if (overlay) {\n            overlay.style.display = 'flex';\n        }", "startExpertProgress('جاري استيراد وتحليل ملفات السنوات السابقة...');")
content = content.replace("if (overlay) overlay.style.display = 'none';", "stopExpertProgress();")

with open('students/templates/students/expert_analysis.html', 'w') as f:
    f.write(content)
