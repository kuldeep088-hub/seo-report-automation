"""
Helper: prints base64-encoded versions of your credential files.
Copy the output and paste into Railway environment variables.

Run: python encode_credentials.py
"""

import base64
from pathlib import Path

files = {
    "GOOGLE_OAUTH_TOKEN_B64":     Path("credentials/oauth_token.json"),
    "GOOGLE_SERVICE_ACCOUNT_B64": Path("credentials/google_service_account.json"),
}

print("=" * 60)
print("Copy these into Railway → Variables tab")
print("=" * 60)

for var_name, path in files.items():
    if not path.exists():
        print(f"\n{var_name}:  FILE NOT FOUND ({path})")
        continue
    encoded = base64.b64encode(path.read_bytes()).decode()
    print(f"\n{var_name}:\n{encoded[:80]}...  ({len(encoded)} chars total)")
    # Write full value to a temp file for easy copy
    out = Path(f"{var_name}.txt")
    out.write_text(encoded, encoding="utf-8")
    print(f"  Full value saved to: {out}")

print()
print("=" * 60)
print("Also set these from your .env:")
env_keys = [
    "ANTHROPIC_API_KEY",
    "AHREFS_API_KEY",
    "PAGESPEED_API_KEY",
    "GDOCS_FOLDER_ID",
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM",
]
for k in env_keys:
    print(f"  {k}")
print("=" * 60)
