"""Crawl all reports, honoring Retry-After when the sixth read is limited."""
import time

import requests
from bs4 import BeautifulSoup
from common import BASE_URL

session = requests.Session()
index = session.get(f"{BASE_URL}/rate-limit")
soup = BeautifulSoup(index.text, "html.parser")

for link in soup.select("#dataset-table a[href*='/reports/']"):
    url = f"{BASE_URL}{link['href']}"
    response = session.get(url)
    if response.status_code == 429:
        wait = int(response.headers["Retry-After"])
        print(f"429 received; waiting {wait}s before retrying {link['href']}")
        time.sleep(wait)
        response = session.get(url)
    report = BeautifulSoup(response.text, "html.parser")
    print(response.status_code, report.select_one("#report-details").get_text(" ", strip=True))
