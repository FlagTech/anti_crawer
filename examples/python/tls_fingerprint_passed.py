"""curl-cffi impersonates Chrome's TLS ClientHello for this local lab."""
from pathlib import Path
import subprocess

from bs4 import BeautifulSoup
from curl_cffi import requests

from common import BASE_URL

ca_root = Path(subprocess.check_output(["mkcert", "-CAROOT"], text=True).strip()) / "rootCA.pem"
response = requests.get(f"{BASE_URL}/tls-fingerprint", impersonate="chrome", verify=str(ca_root))
soup = BeautifulSoup(response.text, "html.parser")
rows = [row.get_text(" ", strip=True) for row in soup.select("#dataset-table tbody tr")]
print(response.status_code, rows)
