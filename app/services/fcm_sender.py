"""Real FCM HTTP v1 sender.

Sends push notifications via the Firebase Cloud Messaging HTTP v1 API.
Requires a Firebase service-account JSON (Project Settings -> Service Accounts
-> Generate new private key). Point FCM_SERVICE_ACCOUNT_FILE at it.

The google-services.json shipped with the app is CLIENT config only and cannot
authenticate sends.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


class FcmError(RuntimeError):
    pass


def _service_account_path() -> str:
    path = os.getenv("FCM_SERVICE_ACCOUNT_FILE", "")
    if not path or not os.path.exists(path):
        raise FcmError(
            "No FCM service account configured. Set FCM_SERVICE_ACCOUNT_FILE to a "
            "Firebase service-account JSON (Project Settings > Service Accounts > "
            "Generate new private key). The google-services.json is client config "
            "only and cannot authorize sends."
        )
    return path


def _access_token(sa_path: str) -> tuple[str, str]:
    """Mint an OAuth2 access token from the service account. Returns (token, project_id)."""
    from google.auth.transport.requests import Request  # type: ignore
    from google.oauth2 import service_account  # type: ignore

    creds = service_account.Credentials.from_service_account_file(sa_path, scopes=[FCM_SCOPE])
    creds.refresh(Request())
    project_id = json.loads(open(sa_path).read())["project_id"]
    return creds.token, project_id


def send_to_token(token: str, title: str, body: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send a notification to a single device token via FCM HTTP v1."""
    sa_path = _service_account_path()
    access_token, project_id = _access_token(sa_path)
    url = f"https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
    message: dict[str, Any] = {
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
        }
    }
    if data:
        message["message"]["data"] = {k: str(v) for k, v in data.items()}
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json=message,
        timeout=20,
    )
    if resp.status_code >= 400:
        raise FcmError(f"FCM send failed ({resp.status_code}): {resp.text}")
    return resp.json()
