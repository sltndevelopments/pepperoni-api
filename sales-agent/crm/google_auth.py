"""
OAuth2 JWT для Google Sheets / Drive API.

Использует тот же service account, что и pepperoni SEO (GSC), либо отдельный JSON.
Ключ формата AQ.* — не подходит для Sheets; нужен service account.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = ROOT / "secrets"
DEFAULT_KEY_PATH = SECRETS_DIR / "google-service-account.json"

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
DEFAULT_SCOPES = f"{SHEETS_SCOPE} {DRIVE_SCOPE}"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def load_service_account_info() -> dict:
    """Загрузить JSON service account из env или файла."""
    path = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "").strip()
    if path and Path(path).is_file():
        return json.loads(Path(path).read_text(encoding="utf-8"))

    if DEFAULT_KEY_PATH.is_file():
        return json.loads(DEFAULT_KEY_PATH.read_text(encoding="utf-8"))

    raw = os.environ.get("GSC_SERVICE_ACCOUNT_KEY", "").strip()
    if raw:
        return json.loads(raw)

    b64 = os.environ.get("GSC_SERVICE_ACCOUNT_KEY_B64", "").strip()
    if b64:
        return json.loads(base64.b64decode(b64).decode("utf-8"))

    raise RuntimeError(
        "Нет credentials для Google Sheets. Положите JSON в "
        f"{DEFAULT_KEY_PATH} или задайте GOOGLE_SHEETS_CREDENTIALS / GSC_SERVICE_ACCOUNT_KEY"
    )


def jwt_token(sa_info: dict, *, scope: str = DEFAULT_SCOPES) -> str:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {
        "iss": sa_info["client_email"],
        "scope": scope,
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }
    hdr_b64 = _b64url(json.dumps(header).encode())
    pay_b64 = _b64url(json.dumps(payload).encode())
    signing_input = f"{hdr_b64}.{pay_b64}".encode()
    private_key = serialization.load_pem_private_key(
        sa_info["private_key"].encode(), password=None
    )
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{hdr_b64}.{pay_b64}.{_b64url(signature)}"


def get_access_token(*, scope: str = DEFAULT_SCOPES) -> tuple[str, dict]:
    sa_info = load_service_account_info()
    jwt = jwt_token(sa_info, scope=scope)
    data = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt,
    }).encode()
    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            token = json.loads(resp.read())["access_token"]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Google token error {e.code}: {body}") from e
    return token, sa_info


def service_account_email() -> str:
    return load_service_account_info()["client_email"]
