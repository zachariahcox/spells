import requests # python -m pip install requests.
import json

token = '3a5f50e43ec0886fb38ffe950fd3add479567863'
repo = 'test_book'
description = 'A test repo'
url= "https://www.google.com"
payload = {
    'name': repo,
    'description': description
    }

headers = {
    'Authorization': f'token {token}'
    }

response = requests.get(
    url,
    # headers=headers,
    # data=json.dumps(payload)
    )

print(response.status_code)
print(response)

data = response.json()
print(data)
