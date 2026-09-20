"""Fetch the whole page without the headers required by this scenario."""
import requests
from common import BASE_URL

response = requests.get(f"{BASE_URL}/header-policy")
print(response.status_code, response.headers.get("X-Training-Rule"))
