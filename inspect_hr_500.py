import requests

session = requests.Session()
# Get CSRF token
res = session.get('http://127.0.0.1:8000/auth/login/')
csrf_token = session.cookies.get('csrftoken')

# Login as admin
data = {
    'username': 'director',
    'password': 'password123',
    'csrfmiddlewaretoken': csrf_token,
}
session.post('http://127.0.0.1:8000/auth/login/', data=data, headers={'Referer': 'http://127.0.0.1:8000/auth/login/'})

# Request HR page
res = session.get('http://127.0.0.1:8000/canteen/hr/')
print(res.status_code)
if res.status_code == 500:
    import bs4
    soup = bs4.BeautifulSoup(res.text, 'html.parser')
    err = soup.find('div', id='summary')
    if err:
        print(err.text.strip())
    else:
        print(res.text[:2000])
