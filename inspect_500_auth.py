import requests

session = requests.Session()
response = session.get('http://127.0.0.1:8000/auth/login/')
csrf_token = session.cookies.get('csrftoken')

data = {
    'username': 'director',
    'password': 'password123', # Using default setup password or testadmin
    'csrfmiddlewaretoken': csrf_token,
}
session.post('http://127.0.0.1:8000/auth/login/', data=data, headers={'Referer': 'http://127.0.0.1:8000/auth/login/'})

res = session.get('http://127.0.0.1:8000/canteen/hr/')
print(res.status_code)
if res.status_code == 500:
    print(res.text[:3000])
