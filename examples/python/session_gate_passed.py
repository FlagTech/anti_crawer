"""Submit the training login form, then parse the protected whole page."""
import requests
from common import BASE_URL, rows_from_html

session = requests.Session()
response = session.post(f"{BASE_URL}/session-gate/login", data={"username": "learner@example.test", "password": "DemoPass!2026"})
print(response.status_code, rows_from_html(response.text))
