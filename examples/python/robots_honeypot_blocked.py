"""Access the crawler-only honeypot directly and observe the denial."""
import requests
from common import BASE_URL

response = requests.get(f"{BASE_URL}/training-honeypot")
print(response.status_code, response.headers.get("X-Training-Rule"))
