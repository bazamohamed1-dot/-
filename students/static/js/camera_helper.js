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
    const banner = document.createElement('div');
    banner.id = 'camera-warning-banner';
    banner.innerHTML = `
        <div style="position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.8); z-index: 99999; display: flex; align-items: center; justify-content: center; padding: 20px;">
            <div style="background: white; padding: 25px; border-radius: 12px; max-width: 500px; text-align: center;">
                <i class="fas fa-exclamation-triangle fa-3x" style="color: #f59e0b; margin-bottom: 15px;"></i>
                <h3 style="margin: 0 0 10px 0; color: #1e293b;">تنبيه هام حول الكاميرا</h3>
                <p style="color: #64748b; line-height: 1.6; margin-bottom: 20px;">
                    المتصفح يمنع استخدام الكاميرا لأن الاتصال "غير آمن" (HTTP). لتشغيل الكاميرا في هذا الوضع (Offline)، يجب تفعيل الخيار التالي في هاتفك:
                </p>
                <div style="background: #f1f5f9; padding: 15px; border-radius: 8px; text-align: left; direction: ltr; font-family: monospace; font-size: 0.9rem; margin-bottom: 20px; word-break: break-all;">
                    <strong>chrome://flags/#unsafely-treat-insecure-origin-as-secure</strong>
                </div>
                <ol style="text-align: right; margin-bottom: 20px; font-size: 0.9rem; color: #475569; padding-right: 20px;">
                    <li>انسخ الرابط أعلاه وضعه في شريط العنوان في Chrome.</li>
                    <li>فعّل الخيار (Enable).</li>
                    <li>أضف عنوان السيرفر: <strong dir="ltr">${window.location.origin}</strong> في الخانة المخصصة.</li>
                    <li>أعد تشغيل المتصفح.</li>
                </ol>
                <button onclick="document.getElementById('camera-warning-banner').remove()" style="background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 8px; font-weight: bold; width: 100%;">فهمت، سأقوم بذلك</button>
            </div>
        </div>
    `;
    document.body.appendChild(banner);
}

// Hook into existing scanner starts
const originalHtml5Qrcode = window.Html5Qrcode;
if (originalHtml5Qrcode) {
    // We can't easily override the class constructor but we can check before instantiating in the app code
    // Ideally, we just call checkCameraSupport() when the scanner modal opens.
}
