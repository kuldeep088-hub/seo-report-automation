"""
One-time OAuth2 setup for Google Docs export.

Steps:
  1. Go to Google Cloud Console -> APIs & Services -> Credentials
  2. Click "Create Credentials" -> "OAuth 2.0 Client ID"
  3. Application type: Desktop app
  4. Download the JSON and save it as: credentials/oauth_client.json
  5. Run: python setup_oauth.py
  6. A browser window will open — sign in with your Google account and grant access.
  7. credentials/oauth_token.json will be saved for future runs.
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

CLIENT_FILE = "credentials/oauth_client.json"
TOKEN_FILE = "credentials/oauth_token.json"

if not os.path.exists(CLIENT_FILE):
    print(f"ERROR: {CLIENT_FILE} not found.")
    print("Download your OAuth 2.0 Client ID JSON from Google Cloud Console and save it as:")
    print(f"  {CLIENT_FILE}")
    exit(1)

flow = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES)
creds = flow.run_local_server(port=0)

with open(TOKEN_FILE, "w") as fh:
    fh.write(creds.to_json())

print(f"\nSuccess! OAuth token saved to: {TOKEN_FILE}")
print("You can now run main.py normally.")
