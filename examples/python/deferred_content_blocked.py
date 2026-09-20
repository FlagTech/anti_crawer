"""requests downloads only the initial HTML; it does not execute page JavaScript."""
import requests
from common import BASE_URL, rows_from_html

response = requests.get(f"{BASE_URL}/deferred-content")
print(response.status_code, rows_from_html(response.text))
