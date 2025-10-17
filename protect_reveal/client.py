from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import requests


class ProtectRevealError(Exception):
    pass


class APIError(ProtectRevealError):
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


@dataclass
class APIResponse:
    status_code: Optional[int]
    body: Any

    @property
    def is_success(self) -> bool:
        return bool(self.status_code and str(self.status_code).startswith("2"))


class ProtectRevealClient:
    def __init__(self, host: str, port: int, policy: str, timeout: int = 10):
        self.base_url = f"http://{host}:{port}"
        self.protect_url = urljoin(self.base_url, "/v1/protect")
        self.reveal_url = urljoin(self.base_url, "/v1/reveal")
        self.policy = policy
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

    def post_json(self, url: str, payload: Dict[str, Any]) -> APIResponse:
        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            status = getattr(exc.response, "status_code", None)
            raise APIError(str(exc), status_code=status, response=getattr(exc, "response", None))

        try:
            body = resp.json()
        except ValueError:
            body = resp.text

        return APIResponse(resp.status_code, body)

    def extract_protected_from_protect_response(self, response: APIResponse) -> Optional[str]:
        if not isinstance(response.body, dict):
            return None
        return response.body.get("protected_data") or response.body.get("protected") or response.body.get("token")

    def extract_restored_from_reveal_response(self, response: APIResponse) -> Optional[str]:
        if not isinstance(response.body, dict):
            return None
        candidates = ("data", "original", "plain", "revealed", "unprotected_data", "unprotected", "decrypted")
        for key in candidates:
            if key in response.body:
                return response.body.get(key)
        return None
