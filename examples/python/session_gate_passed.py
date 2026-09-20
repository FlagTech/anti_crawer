"""Create the site's demonstration session, then parse the whole page."""
import requests
from common import BASE_URL, rows_from_html

session = requests.Session()
response = session.get(f"{BASE_URL}/session-gate/start")
print(response.status_code, rows_from_html(response.text))
