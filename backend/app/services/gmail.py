from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from ..config import SECRETS_DIR, get_settings

log = logging.getLogger(__name__)

# Gmail READ-ONLY. The app can never send, delete or modify mail with this scope.
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN_FILE = SECRETS_DIR / "gmail_token.enc"
_FLOWS: dict[str, object] = {}
_flows_lock = threading.Lock()

# Local development redirect is http://localhost; allow it (production should use https).
if get_settings().google_redirect_uri.startswith("http://localhost") or get_settings().google_redirect_uri.startswith("http://127.0.0.1"):
    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")


class GmailError(Exception):
    def __init__(self, message: str, code: str = "gmail_error", status: int = 400):
        super().__init__(message)
        self.code, self.status = code, status


class AccountMismatch(GmailError):
    def __init__(self, got: str, expected: str):
        super().__init__(f"Authenticated Gmail account ({got}) does not match the configured target inbox ({expected}). "
                         "No mail was read and no token was stored.", "account_mismatch", 403)


def _fernet() -> Fernet:
    key = get_settings().token_encryption_key.strip()
    if not key:
        kf = SECRETS_DIR / "fernet.key"
        SECRETS_DIR.mkdir(parents=True, exist_ok=True)
        if not kf.exists():
            kf.write_bytes(Fernet.generate_key())
            kf.chmod(0o600)
        key = kf.read_text().strip()
    return Fernet(key.encode())


def _save_token(creds) -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_bytes(_fernet().encrypt(creds.to_json().encode()))
    TOKEN_FILE.chmod(0o600)


def load_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not TOKEN_FILE.exists():
        return None
    try:
        info = json.loads(_fernet().decrypt(TOKEN_FILE.read_bytes()))
    except (InvalidToken, ValueError):
        log.error("Stored Gmail token could not be decrypted; reconnect Gmail")
        return None
    creds = Credentials.from_authorized_user_info(info, SCOPES)
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
    return creds if creds.valid else None


def disconnect() -> None:
    TOKEN_FILE.unlink(missing_ok=True)


def is_configured() -> tuple[bool, str | None]:
    s = get_settings()
    if not s.target_configured:
        return False, "TARGET_GMAIL_ADDRESS is not set in .env"
    if not s.has_oauth_client:
        return False, f"Google OAuth credentials not configured (set GOOGLE_CLIENT_ID & GOOGLE_CLIENT_SECRET in .env or place client_secret.json at {s.client_secrets_path})"
    return True, None


def _build_flow():
    from google_auth_oauthlib.flow import Flow

    s = get_settings()
    if s.google_client_id.strip() and s.google_client_secret.strip():
        client_config = {
            "web": {
                "client_id": s.google_client_id.strip(),
                "client_secret": s.google_client_secret.strip(),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [s.google_redirect_uri],
            }
        }
        return Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=s.google_redirect_uri)
    return Flow.from_client_secrets_file(str(s.client_secrets_path), scopes=SCOPES, redirect_uri=s.google_redirect_uri)


def start_auth() -> str:
    ok, why = is_configured()
    if not ok:
        raise GmailError(why or "Gmail not configured", "not_configured", 400)
    s = get_settings()
    flow = _build_flow()
    url, state = flow.authorization_url(access_type="offline", prompt="consent", login_hint=s.target_gmail_address,
                                        include_granted_scopes="false")
    with _flows_lock:
        _FLOWS[state] = flow
    return url


def finish_auth(state: str, code: str) -> str:
    """Exchange the code, verify the account equals TARGET_GMAIL_ADDRESS, and only then store the token."""
    with _flows_lock:
        flow = _FLOWS.pop(state, None)
    if flow is None:
        raise GmailError("OAuth state is unknown or expired. Click Connect Gmail again.", "bad_state", 400)
    flow.fetch_token(code=code)
    creds = flow.credentials
    account = profile(build_service(creds))["emailAddress"].lower()
    target = get_settings().target_gmail_address.strip().lower()
    if account != target:
        try:  # best-effort revoke of the wrong account's grant
            import requests
            requests.post("https://oauth2.googleapis.com/revoke", params={"token": creds.token}, timeout=5)
        except Exception:  # pragma: no cover
            pass
        raise AccountMismatch(account, target)
    _save_token(creds)
    return account


def build_service(creds):
    from googleapiclient.discovery import build

    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def profile(service) -> dict:
    return service.users().getProfile(userId="me").execute()


def get_verified_service():
    """Return (service, profile) for the authorised, target-matching mailbox or raise."""
    ok, why = is_configured()
    if not ok:
        raise GmailError(why or "Gmail not configured", "not_configured", 400)
    creds = load_credentials()
    if creds is None:
        raise GmailError("Gmail is not connected. Click Connect Gmail.", "not_connected", 401)
    svc = build_service(creds)
    prof = profile(svc)
    target = get_settings().target_gmail_address.strip().lower()
    if prof["emailAddress"].lower() != target:
        disconnect()
        raise AccountMismatch(prof["emailAddress"].lower(), target)
    return svc, prof


def list_inbox_ids(svc, max_messages: int) -> list[str]:
    ids: list[str] = []
    token = None
    while len(ids) < max_messages:
        r = svc.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=min(100, max_messages - len(ids)), pageToken=token).execute()
        ids += [m["id"] for m in r.get("messages", [])]
        token = r.get("nextPageToken")
        if not token:
            break
    return ids


def list_new_ids(svc, start_history_id: str) -> list[str] | None:
    """Incremental listing via the History API. Returns None when the history id expired (caller does a full sync)."""
    from googleapiclient.errors import HttpError

    ids: list[str] = []
    token = None
    try:
        while True:
            r = svc.users().history().list(userId="me", startHistoryId=start_history_id, historyTypes=["messageAdded"],
                                           labelId="INBOX", pageToken=token).execute()
            for h in r.get("history", []):
                ids += [m["message"]["id"] for m in h.get("messagesAdded", [])]
            token = r.get("nextPageToken")
            if not token:
                break
    except HttpError as e:
        if getattr(e.resp, "status", None) == 404:
            return None
        raise
    return list(dict.fromkeys(ids))


def get_message(svc, msg_id: str) -> dict:
    return svc.users().messages().get(userId="me", id=msg_id, format="full").execute()
