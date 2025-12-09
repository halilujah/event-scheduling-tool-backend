import requests
import json

response = requests.get('http://localhost:10000/events/FPGQK6')
print('Status:', response.status_code)
print('Response:')
print(json.dumps(response.json(), indent=2))
