"""
Startup script — runs before scheduler.py on Railway.
Decodes base64-encoded credentials from environment variables
and writes them to the credentials/ folder so the rest of
the app can read them normally.

Environment variables to set in Railway dashboard:
  GOOGLE_OAUTH_TOKEN_B64        → base64 of credentials/oauth_token.json
  GOOGLE_SERVICE_ACCOUNT_B64    → base64 of credentials/google_service_account.json

To encode your local credential files, run:
  python encode_credentials.py
"""

import base64
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

CREDENTIALS_DIR = Path("credentials")
CREDENTIALS_DIR.mkdir(exist_ok=True)

VARS = {
    "GOOGLE_OAUTH_TOKEN_B64":     CREDENTIALS_DIR / "oauth_token.json",
    "GOOGLE_SERVICE_ACCOUNT_B64": CREDENTIALS_DIR / "google_service_account.json",
}

missing = []
for env_var, file_path in VARS.items():
    value = os.environ.get(env_var, "").strip()
    if not value:
        if not file_path.exists():
            missing.append(env_var)
        continue
    try:
        decoded = base64.b64decode(value)
        file_path.write_bytes(decoded)
        log.info("Credential written: %s", file_path)
    except Exception as e:
        log.error("Failed to decode %s: %s", env_var, e)
        sys.exit(1)

if missing:
    log.warning("These env vars are not set (credentials may already exist locally): %s", missing)

log.info("Startup complete.")
