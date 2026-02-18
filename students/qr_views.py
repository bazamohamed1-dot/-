
import qrcode
from io import BytesIO
import base64
import socket
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import SchoolSettings

def get_local_ip():
    try:
        # Connect to an external server (doesn't send data) to get the interface IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

@login_required
def generate_user_qr(request):
    """
    Generates a QR Code that contains a login URL with pre-filled credentials (username).
    Format: http://<HOST>/canteen/?username=<USERNAME>&install=true
    """
    if not request.user.profile.role == 'director' and not request.user.is_superuser:
        return JsonResponse({'error': 'Unauthorized'}, status=403)

    username = request.GET.get('username')
    if not username:
        return JsonResponse({'error': 'Username required'}, status=400)

    # Prioritize detecting the real LAN IP
    # request.get_host() might return 'localhost' if the director is on the server machine
    local_ip = get_local_ip()
    host = f"{local_ip}:8000"

    # Use HTTP by default for local LAN as configured in recent steps
    protocol = 'http'

    # Construct the URL
    # We point to the landing page which will handle the auto-fill and install prompt
    login_url = f"{protocol}://{host}/canteen/?username={username}&install=true"

    # Generate QR
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(login_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()

    return JsonResponse({'qr_code': f"data:image/png;base64,{img_str}", 'url': login_url})
