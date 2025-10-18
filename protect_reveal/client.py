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
        except requests.RequestException as exc:
            # network-level error, try to return any attached response, else error text
            resp = getattr(exc, 'response', None)
            if resp is None:
                return APIResponse(None, str(exc))

        # At this point we have a Response object (may have non-2xx status)
        status = getattr(resp, 'status_code', None)
        try:
            body = resp.json()
        except Exception:
            body = getattr(resp, 'text', None)

        return APIResponse(status, body)

    # Bulk helpers
    def protect_bulk(self, items: list) -> APIResponse:
        """Send a bulk protect request. Payload: {protection_policy_name, data: [ ... ]}"""
        # include both common and Thales-style keys for compatibility
        payload = {"protection_policy_name": self.policy, "data": items, "data_array": items}
        return self.post_json(self.protect_bulk_url, payload)

    def reveal_bulk(self, protected_items: list, username: Optional[str] = None) -> APIResponse:
        """Send a bulk reveal request.

        protected_items may be a list of strings (tokens) or a list of dicts
        containing at least the key 'protected_data' and optionally keys like
        'external_version'. The payload will include both compatibility keys
        ('protected_data', 'protected_array') and the Thales-style
        'protected_data_array'. If username is provided it will be added to
        the request body.
        """
        # Build protected_data_array preserving any extra fields per-item
        pda = []
        for p in protected_items:
            if isinstance(p, dict):
                # assume it already has 'protected_data' and possibly 'external_version'
                pda.append(p)
            else:
                pda.append({"protected_data": p})

        # include multiple possible keys to match different server implementations
        # protected_data / protected_array keep the old simple list form
        simple_list = [item.get("protected_data") if isinstance(item, dict) else str(item) for item in pda]
        payload: Dict[str, Any] = {
            "protection_policy_name": self.policy,
            "protected_data": simple_list,
            "protected_array": simple_list,
        }
        payload["protected_data_array"] = pda
        if username:
            payload["username"] = username

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
            # Thales style: protected_data_array -> list of {protected_data: value}
            if "protected_data_array" in body and isinstance(body["protected_data_array"], list):
                out = []
                for item in body["protected_data_array"]:
                    if isinstance(item, dict) and "protected_data" in item:
                        out.append(str(item.get("protected_data")))
                return out
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
            # direct list or keyed list
            for key in ("data", "restored", "items"):
                if key in body:
                    val = body[key]
                    if isinstance(val, list):
                        return [str(x) for x in val]
            # results may be list of dicts
            if "results" in body and isinstance(body["results"], list):
                out = []
                for item in body["results"]:
                    if isinstance(item, dict):
                        # try to find common fields
                        for k in ("data", "restored", "value"):
                            if k in item:
                                out.append(str(item.get(k)))
                                break
                return out

            # Thales-style: data_array -> list of {'data': value}
            if 'data_array' in body and isinstance(body['data_array'], list):
                out = []
                for item in body['data_array']:
                    if isinstance(item, dict) and 'data' in item:
                        out.append(str(item.get('data')))
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
