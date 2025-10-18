#!/usr/bin/env python3
"""protect_reveal.py

Utilities to call a protect endpoint then a reveal endpoint repeatedly.

This module provides a clean and type-safe interface for interacting with 
protect/reveal API endpoints.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
import argparse
import json
import logging
import sys
import time
from urllib.parse import urljoin

import requests


# Defaults
DEFAULT_HOST = "192.168.0.231"
DEFAULT_PORT = 32082
DEFAULT_POLICY = "P03"
DEFAULT_START_DATA = "0123456789123"


class ProtectRevealError(Exception):
    """Base exception class for protect/reveal operations."""
    pass


class APIError(ProtectRevealError):
    """Exception raised for API related errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


@dataclass
class APIResponse:
    """Structure holding the API response data."""
    status_code: Optional[int]
    body: Any
    
    @property
    def is_success(self) -> bool:
        """Check if the response indicates success."""
        return bool(self.status_code and str(self.status_code).startswith('2'))


@dataclass
class Config:
    """Configuration for protect/reveal operations."""
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    policy: str = DEFAULT_POLICY
    start_data: str = DEFAULT_START_DATA
    iterations: int = 100
    timeout: int = 10
    verbose: bool = False
    show_bodies: bool = False
    show_progress: bool = False
    bulk: bool = False
    batch_size: int = 25
    
    @classmethod
    def from_args(cls, argv: Optional[list] = None) -> 'Config':
        """Create Config from command line arguments."""
        parser = argparse.ArgumentParser(
            description="Loop protect/reveal calls and measure time"
        )
        parser.add_argument("--host", default=DEFAULT_HOST, help="API host")
        parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="API port")
        parser.add_argument("--policy", default=DEFAULT_POLICY, 
                           help="protection_policy_name")
        parser.add_argument("--start-data", default=DEFAULT_START_DATA, 
                           help="numeric data to start from")
        parser.add_argument("--iterations", default=100, type=int, 
                           help="number of iterations")
        parser.add_argument("--timeout", default=10, type=int, 
                           help="per-request timeout seconds")
        parser.add_argument("--verbose", action="store_true", 
                           help="enable debug logging")
        parser.add_argument("--show-bodies", action="store_true", 
                   help="print request and response JSON bodies")
        parser.add_argument("--show-progress", action="store_true", 
                   dest="show_progress", 
                   help="show per-iteration progress output")
        parser.add_argument("--bulk", action="store_true", help="use bulk protect/reveal endpoints")
        parser.add_argument("--batch-size", default=25, type=int, help="batch size for bulk operations (default 25)")

        args = parser.parse_args(argv)
        return cls(**vars(args))


class ProtectRevealClient:
    """Client for interacting with protect/reveal API endpoints."""
    
    def __init__(self, host: str, port: int, policy: str, timeout: int = 10):
        """Initialize the client with API configuration."""
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
        """POST JSON to url and return APIResponse.

        Do not raise on HTTP error statuses; instead return an APIResponse with
        status_code and body when available so callers can inspect 4xx/5xx bodies.
        """
        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as exc:
            resp = getattr(exc, 'response', None)
            if resp is None:
                return APIResponse(None, str(exc))

        status = getattr(resp, 'status_code', None)
        try:
            body = resp.json()
        except Exception:
            body = getattr(resp, 'text', None)

        return APIResponse(status, body)

    # Bulk helpers (mirror package client)
    def protect_bulk(self, items: list) -> APIResponse:
        payload = {"protection_policy_name": self.policy, "data": items, "data_array": items}
        return self.post_json(self.protect_bulk_url, payload)

    def reveal_bulk(self, protected_items: list) -> APIResponse:
        payload = {"protection_policy_name": self.policy, "protected_data": protected_items, "protected_array": protected_items}
        payload['protected_data_array'] = [{"protected_data": p} for p in protected_items]
        return self.post_json(self.reveal_bulk_url, payload)

    def extract_protected_list_from_protect_response(self, response: APIResponse) -> list:
        if response is None or response.body is None:
            return []
        body = response.body
        # If body is a plain list of tokens
        if isinstance(body, list):
            return [str(x) for x in body]
        # If body is a dict, check several possible shapes
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
        if response is None or response.body is None:
            return []
        body = response.body
        if isinstance(body, list):
            return [str(x) for x in body]
        if isinstance(body, dict):
            # direct list or keyed list
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
        """Extract the protected token from a protect response."""
        if not isinstance(response.body, dict):
            return None
        return (response.body.get("protected_data") or 
                response.body.get("protected") or 
                response.body.get("token"))

    def extract_restored_from_reveal_response(self, response: APIResponse) -> Optional[str]:
        """Extract the restored data from a reveal response."""
        if not isinstance(response.body, dict):
            return None
        candidates = ("data", "original", "plain", "revealed", 
                     "unprotected_data", "unprotected", "decrypted")
        for key in candidates:
            if key in response.body:
                return response.body.get(key)
        return None


def increment_numeric_string(s: str) -> str:
    """Increment a numeric string while preserving width (zero padding)."""
    if not s.isdigit():
        raise ValueError("data must be a numeric string")
    width = len(s)
    n = int(s) + 1
    return f"{n:0{width}d}"


@dataclass
class IterationResult:
    """Result of a single protect->reveal iteration."""
    data: str
    protect_response: APIResponse
    reveal_response: APIResponse
    protected_token: Optional[str]
    restored: Optional[str]
    time_s: float
    
    @property
    def match(self) -> bool:
        """Check if the revealed data matches the original."""
        return self.restored == self.data if self.restored is not None else False
    
    @property
    def success(self) -> bool:
        """Check if both API calls were successful."""
        return self.protect_response.is_success and self.reveal_response.is_success


def run_iteration(client: ProtectRevealClient, data: str) -> IterationResult:
    """Run a single protect->reveal sequence and return a result."""
    t0 = time.perf_counter()

    protect_payload = {"protection_policy_name": client.policy, "data": data}
    protect_response = client.post_json(client.protect_url, protect_payload)

    protected_token = client.extract_protected_from_protect_response(protect_response)

    reveal_payload = {
        "protection_policy_name": client.policy,
        "protected_data": protected_token or ""
    }
    reveal_response = client.post_json(client.reveal_url, reveal_payload)

    restored = client.extract_restored_from_reveal_response(reveal_response)
    t1 = time.perf_counter()

    return IterationResult(
        data=data,
        protect_response=protect_response,
        reveal_response=reveal_response,
        protected_token=protected_token,
        restored=restored,
        time_s=t1 - t0
    )


def main(argv: Optional[list] = None) -> int:
    """Main entry point."""
    config = Config.from_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if config.verbose else logging.INFO,
        format="%(message)s"
    )
    logger = logging.getLogger("protect_reveal")

    client = ProtectRevealClient(
        host=config.host,
        port=config.port,
        policy=config.policy,
        timeout=config.timeout
    )

    # If bulk mode is enabled, use the bulk runner
    if config.bulk:
        from protect_reveal.runner import run_bulk_iteration

        # build list of inputs from start_data and iterations
        inputs = []
        cur = config.start_data
        for _ in range(config.iterations):
            inputs.append(cur)
            try:
                cur = increment_numeric_string(cur)
            except Exception:
                break

        bulk_results = run_bulk_iteration(client, inputs, batch_size=config.batch_size)
        bulk_results = run_bulk_iteration(client, inputs, batch_size=config.batch_size)

        # If requested, print per-batch details (bodies). Otherwise suppress.
        for idx, b in enumerate(bulk_results, start=1):
            if config.show_bodies:
                pbody = getattr(b.protect_response, 'body', {}) or {}
                rbody = getattr(b.reveal_response, 'body', {}) or {}

                protect_obj = {
                    "status": pbody.get("status", "Success" if b.protect_response and b.protect_response.is_success else "Error"),
                    "total_count": pbody.get("total_count", len(b.inputs)),
                    "success_count": pbody.get("success_count", len(b.protected_tokens)),
                    "error_count": pbody.get("error_count", max(0, len(b.inputs) - len(b.protected_tokens))),
                    "protected_data_array": [{"protected_data": tok} for tok in b.protected_tokens],
                }

                reveal_obj = {
                    "status": rbody.get("status", "Success" if b.reveal_response and b.reveal_response.is_success else "Error"),
                    "total_count": rbody.get("total_count", len(b.inputs)),
                    "success_count": rbody.get("success_count", len(b.restored_values)),
                    "error_count": rbody.get("error_count", max(0, len(b.inputs) - len(b.restored_values))),
                    "data_array": [{"data": v} for v in b.restored_values],
                }

                out = {"batch": idx, "protect": protect_obj, "reveal": reveal_obj, "time_s": b.time_s}
                print(json.dumps(out, ensure_ascii=False, indent=2))

        # Print overall bulk summary so user sees timing and counts even when
        # per-batch output is suppressed.
        total_batches = len(bulk_results)
        total_items = sum(len(b.inputs) for b in bulk_results)
        total_time = sum(b.time_s for b in bulk_results)
        avg_batch_time = (total_time / total_batches) if total_batches else 0.0

        logger.info("Bulk run summary:")
        logger.info("  Batches processed: %d", total_batches)
        logger.info("  Items processed: %d", total_items)
        logger.info("  Total bulk time (sum of batch times): %.4fs", total_time)
        logger.info("  Average batch time: %.4fs", avg_batch_time)

        return 0

    current = config.start_data
    results: list[IterationResult] = []
    t_start = time.perf_counter()

    for i in range(1, config.iterations + 1):
        try:
            result = run_iteration(client, current)
            results.append(result)
            
            if config.show_progress:
                logger.info(
                    "#%03d data=%s time=%.4fs protect_status=%s reveal_status=%s match=%s",
                    i,
                    current,
                    result.time_s,
                    result.protect_response.status_code,
                    result.reveal_response.status_code,
                    result.match,
                )

            # show_bodies should be independent of show_progress
            if config.show_bodies:
                def pretty(x: Any) -> str:
                    try:
                        return json.dumps(x, ensure_ascii=False, indent=2)
                    except Exception:
                        return str(x)

                protect_payload = {
                    "protection_policy_name": config.policy,
                    "data": current
                }
                reveal_payload = {
                    "protection_policy_name": config.policy,
                    "protected_data": result.protected_token or ""
                }

                if not config.show_progress:
                    logger.info("#%03d data=%s", i, current)

                logger.info("  Sent protect payload:\n%s", pretty(protect_payload))
                logger.info("  Received protect body:\n%s", pretty(result.protect_response.body))
                logger.info("  Sent reveal payload:\n%s", pretty(reveal_payload))
                logger.info("  Received reveal body:\n%s", pretty(result.reveal_response.body))

            try:
                current = increment_numeric_string(current)
            except ValueError:
                logger.error("data '%s' is not numeric; stopping iterations", current)
                break
            except Exception as e:
                logger.error("Unexpected error: %s", str(e))
                break

        except Exception as e:
            logger.error("Error in iteration %d: %s", i, str(e))
            if config.verbose:
                logger.exception("Full traceback:")
            continue

    t_end = time.perf_counter()
    total = t_end - t_start

    successful = sum(1 for r in results if r.success)
    matched = sum(1 for r in results if r.match)

    logger.info("\nSummary:")
    logger.info("Iterations attempted: %d", len(results))
    logger.info("Successful (both 2xx): %d", successful)
    logger.info("Revealed matched original data: %d", matched)
    logger.info("Total time: %.4fs", total)
    if results:
        avg = sum(r.time_s for r in results) / len(results)
        logger.info("Average per-iteration time: %.4fs", avg)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        raise SystemExit(1)
    except Exception as e:
        print(f"Fatal error: {e}", file=sys.stderr)
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            import traceback
            traceback.print_exc()
        raise SystemExit(1)
