import requests

try:
    response = requests.get('http://localhost:8000/canteen/hr/')
    print(response.status_code)
    print(response.text[:2000])
except Exception as e:
    print(f"Error: {e}")
