"""Direct page fetch has no login session and is redirected to the login page."""
import requests
from common import BASE_URL

response = requests.get(f"{BASE_URL}/session-gate", allow_redirects=False)
print(response.status_code, response.headers.get("X-Training-Rule"), response.headers.get("Location"))
