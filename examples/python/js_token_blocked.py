"""A plain HTTP fetch cannot execute the page's token workflow."""
import requests
from common import BASE_URL, rows_from_html

print(rows_from_html(requests.get(f"{BASE_URL}/js-token").text))
