// camera_helper.js

function checkCameraSupport() {
    // Check if secure context
    if (!window.isSecureContext) {
        showSecurityWarning();
        return false;
    }
    return true;
}

function showSecurityWarning() {
    const origin = window.location.origin; // e.g. http://192.168.1.100:8000

    const banner = document.createElement('div');
    banner.id = 'camera-warning-banner';
    banner.innerHTML = `
        <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.9); z-index: 99999; display: flex; align-items: center; justify-content: center; padding: 20px;">
            <div style="background: white; padding: 25px; border-radius: 12px; max-width: 500px; text-align: center; position: relative;">
                <button onclick="document.getElementById('camera-warning-banner').remove()" style="position: absolute; top: 10px; left: 10px; background: none; border: none; font-size: 1.5rem; cursor: pointer;">&times;</button>

                <i class="fas fa-video-slash fa-3x" style="color: #ef4444; margin-bottom: 15px;"></i>
                <h3 style="margin: 0 0 10px 0; color: #1e293b;">تفعيل الكاميرا</h3>

                <p style="color: #64748b; font-size: 0.95rem; line-height: 1.6; margin-bottom: 20px;">
                    للسماح بالكاميرا على هذا الرابط، يجب اتباع الخطوات بدقة:
                </p>

                <div style="text-align: right; background: #f8fafc; padding: 15px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #e2e8f0;">
                    <div style="margin-bottom: 10px;">
                        <span style="font-weight: bold; color: var(--primary);">1. انسخ هذا الرابط:</span>
                        <div style="direction: ltr; font-family: monospace; background: #e2e8f0; padding: 5px; margin-top: 5px; border-radius: 4px; overflow-x: auto; white-space: nowrap;">
                            chrome://flags/#unsafely-treat-insecure-origin-as-secure
                        </div>
                    </div>

                    <div style="margin-bottom: 10px;">
                        <span style="font-weight: bold; color: var(--primary);">2. الصقه في شريط العنوان واضغط Enter.</span>
                    </div>

                    <div style="margin-bottom: 10px;">
                        <span style="font-weight: bold; color: var(--primary);">3. قم بتفعيل الخيار (Enable).</span>
                    </div>

                    <div style="margin-bottom: 10px;">
                        <span style="font-weight: bold; color: var(--primary);">4. في الخانة أسفله، اكتب الرابط التالي (بالضبط):</span>
                        <div style="display: flex; gap: 5px; margin-top: 5px;">
                            <input type="text" value="${origin}" readonly style="width: 100%; padding: 5px; border: 1px solid #ccc; border-radius: 4px; direction: ltr; text-align: center;" id="originUrlInput">
                            <button onclick="copyOrigin()" style="background: #3b82f6; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer;">نسخ</button>
                        </div>
                    </div>

                    <div>
                        <span style="font-weight: bold; color: var(--primary);">5. اضغط Relaunch أسفل الشاشة.</span>
                    </div>
                </div>

                <div style="background: #fff7ed; color: #9a3412; padding: 10px; border-radius: 6px; font-size: 0.9rem; margin-bottom: 20px;">
                    <i class="fas fa-info-circle"></i> يمكنك استخدام <strong>الإدخال اليدوي</strong> كبديل إذا لم تنجح هذه الطريقة.
                </div>

                <button onclick="document.getElementById('camera-warning-banner').remove()" style="background: #64748b; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: bold; width: 100%;">إغلاق</button>
            </div>
        </div>
    `;
    document.body.appendChild(banner);
}

function copyOrigin() {
    const copyText = document.getElementById("originUrlInput");
    copyText.select();
    copyText.setSelectionRange(0, 99999);
    navigator.clipboard.writeText(copyText.value);
    alert("تم نسخ الرابط: " + copyText.value);
}
