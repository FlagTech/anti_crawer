"""Direct page fetch has no session cookie and is denied."""
import requests
from common import BASE_URL

response = requests.get(f"{BASE_URL}/session-gate")
print(response.status_code, response.headers.get("X-Training-Rule"))
