import requests

s = requests.Session()
# Go to login page explicitly using canteen prefix
res = s.get('http://127.0.0.1:8000/canteen/auth/login/')
s.post('http://127.0.0.1:8000/canteen/auth/login/', data={
    'username': 'director',
    'password': 'password123',
    'csrfmiddlewaretoken': s.cookies.get('csrftoken', '')
})
res = s.get('http://127.0.0.1:8000/canteen/hr/')
print(res.status_code)
if res.status_code == 500:
    print(res.text[:1000])
