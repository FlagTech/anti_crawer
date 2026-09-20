"""requests has a different TLS ClientHello and is expected to receive 403."""
from pathlib import Path
import subprocess

import requests

from common import BASE_URL

ca_root = Path(subprocess.check_output(["mkcert", "-CAROOT"], text=True).strip()) / "rootCA.pem"
response = requests.get(f"{BASE_URL}/tls-fingerprint", verify=ca_root)
print(response.status_code, response.headers.get("X-Training-Rule"))
