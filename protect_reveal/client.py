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
    self.protect_bulk_url = urljoin(self.base_url, "/v1/protectbulk")
        self.reveal_url = urljoin(self.base_url, "/v1/reveal")
    self.reveal_bulk_url = urljoin(self.base_url, "/v1/revealbulk")
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

    # Bulk helpers
    def protect_bulk(self, items: list) -> APIResponse:
        """Send a bulk protect request. Payload: {protection_policy_name, data: [ ... ]}"""
        payload = {"protection_policy_name": self.policy, "data": items}
        return self.post_json(self.protect_bulk_url, payload)

    def reveal_bulk(self, protected_items: list) -> APIResponse:
        """Send a bulk reveal request. Payload: {protection_policy_name, protected_data: [ ... ]}"""
        payload = {"protection_policy_name": self.policy, "protected_data": protected_items}
        return self.post_json(self.reveal_bulk_url, payload)

    def extract_protected_list_from_protect_response(self, response: APIResponse) -> list:
        """Extract a list of protected tokens from a bulk protect response.

        Supports multiple response shapes: a dict with keys like 'protected_data' (list),
        a dict with 'results' list of objects containing 'protected_data', or a plain list.
        """
        if response is None or response.body is None:
            return []
        body = response.body
        # If body is a list of tokens
        if isinstance(body, list):
            return [str(x) for x in body]
        # If body is a dict and contains a top-level list
        if isinstance(body, dict):
            if "protected_data" in body and isinstance(body["protected_data"], list):
                return [str(x) for x in body["protected_data"]]
            if "results" in body and isinstance(body["results"], list):
                out = []
                for item in body["results"]:
                    if isinstance(item, dict) and "protected_data" in item:
                        out.append(str(item.get("protected_data")))
                return out
        return []

    def extract_restored_list_from_reveal_response(self, response: APIResponse) -> list:
        """Extract a list of restored values from a bulk reveal response.

        Supports common shapes: list of values, or dict with 'data'/'results'.
        """
        if response is None or response.body is None:
            return []
        body = response.body
        if isinstance(body, list):
            return [str(x) for x in body]
        if isinstance(body, dict):
            # direct list
            for key in ("data", "restored", "results", "items"):
                if key in body:
                    val = body[key]
                    if isinstance(val, list):
                        return [str(x) for x in val]
                    # results may be list of dicts
                    if key == "results" and isinstance(val, list):
                        out = []
                        for item in val:
                            if isinstance(item, dict):
                                # try to find common fields
                                for k in ("data", "restored", "value"):
                                    if k in item:
                                        out.append(str(item.get(k)))
                                        break
                        return out
            # fallback: if dict maps tokens->values
            out = []
            for v in body.values():
                if isinstance(v, (str, int)):
                    out.append(str(v))
            return out
        return []

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
