#!/usr/bin/env python3
"""
OAuth Auth Flow — one-time setup to get refresh tokens for connectors.
Run locally, opens browser for authorization, saves tokens.

Usage:
    python3 integrations/auth_flow.py --provider google --client melanin-tech
"""
import os
import sys
import json
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import webbrowser
import httpx

CREDS_DIR = os.path.join(os.path.dirname(__file__), "credentials")
REDIRECT_PORT = 8089
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}/oauth/callback"

GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/webmasters.readonly",
]


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    code = None

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        OAuthCallbackHandler.code = query.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<h1>Authorization successful!</h1><p>You can close this tab.</p>")

    def log_message(self, format, *args):
        pass  # Suppress logs


def google_auth(client_id: str):
    """Run Google OAuth flow."""
    # Load client credentials
    client_creds_path = os.path.join(CREDS_DIR, "google_oauth_client.json")
    if not os.path.exists(client_creds_path):
        print(f"❌ Missing: {client_creds_path}")
        print("   Download from Google Cloud Console → OAuth Client ID → Download JSON")
        sys.exit(1)

    with open(client_creds_path) as f:
        client_data = json.load(f)

    # Handle both formats (web vs installed)
    if "web" in client_data:
        creds = client_data["web"]
    elif "installed" in client_data:
        creds = client_data["installed"]
    else:
        creds = client_data

    oauth_client_id = creds["client_id"]
    oauth_client_secret = creds["client_secret"]
    auth_uri = creds.get("auth_uri", "https://accounts.google.com/o/oauth2/auth")
    token_uri = creds.get("token_uri", "https://oauth2.googleapis.com/token")

    # Build auth URL
    scope_str = " ".join(GOOGLE_SCOPES)
    auth_url = (
        f"{auth_uri}?client_id={oauth_client_id}&redirect_uri={REDIRECT_URI}"
        f"&response_type=code&scope={scope_str}&access_type=offline&prompt=consent"
    )

    print(f"Opening browser for authorization...")
    print(f"If browser doesn't open, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    # Wait for callback
    server = HTTPServer(("localhost", REDIRECT_PORT), OAuthCallbackHandler)
    server.handle_request()
    code = OAuthCallbackHandler.code

    if not code:
        print("❌ No authorization code received")
        sys.exit(1)

    # Exchange code for tokens
    r = httpx.post(token_uri, data={
        "client_id": oauth_client_id,
        "client_secret": oauth_client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    })

    if r.status_code != 200:
        print(f"❌ Token exchange failed: {r.text}")
        sys.exit(1)

    tokens = r.json()
    tokens["client_id"] = oauth_client_id
    tokens["client_secret"] = oauth_client_secret

    import time
    tokens["expires_at"] = time.time() + tokens.get("expires_in", 3600)

    # Save tokens
    client_dir = os.path.join(CREDS_DIR, client_id)
    os.makedirs(client_dir, exist_ok=True)

    # Save for Gmail
    gmail_path = os.path.join(client_dir, "gmail.json")
    with open(gmail_path, "w") as f:
        json.dump(tokens, f, indent=2)
    print(f"✅ Gmail credentials saved: {gmail_path}")

    # Save for Calendar (same tokens, same Google account)
    cal_path = os.path.join(client_dir, "google_calendar.json")
    with open(cal_path, "w") as f:
        json.dump(tokens, f, indent=2)
    print(f"✅ Calendar credentials saved: {cal_path}")


def main():
    parser = argparse.ArgumentParser(description="OAuth auth flow for integrations")
    parser.add_argument("--provider", required=True, choices=["google", "notion"])
    parser.add_argument("--client", required=True, help="Client ID (e.g., melanin-tech)")
    args = parser.parse_args()

    if args.provider == "google":
        google_auth(args.client)
    elif args.provider == "notion":
        print("Notion uses internal integration tokens — no OAuth flow needed.")
        print(f"Save your Notion token to: {CREDS_DIR}/{args.client}/notion.json")
        print('Format: {"access_token": "secret_..."}')


if __name__ == "__main__":
    main()
