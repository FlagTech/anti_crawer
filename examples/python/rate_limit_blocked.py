"""Follow report links too quickly and print the expected 429 response."""
import requests
from common import BASE_URL

session = requests.Session()
session.get(f"{BASE_URL}/rate-limit")
for report_id in ("R-101", "R-102", "R-103", "R-104"):
    print(report_id, session.get(f"{BASE_URL}/rate-limit/reports/{report_id}").status_code)
blocked = session.get(f"{BASE_URL}/rate-limit/reports/R-105")
print("sixth read:", blocked.status_code, "Retry-After:", blocked.headers.get("Retry-After"))
