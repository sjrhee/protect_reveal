
#!/usr/bin/env python3
"""protect_reveal.py - thin CLI wrapper around protect_reveal package

Provides a small CLI that delegates to the package implementation. Keeps
backwards-compatible CLI flags. Default batch size is 25.
"""
from dataclasses import dataclass
from typing import Any, Optional
import argparse
import json
import logging
import sys
import time

from protect_reveal.client import ProtectRevealClient, APIResponse
from protect_reveal.runner import run_bulk_iteration


# Defaults
DEFAULT_HOST = "192.168.0.231"
DEFAULT_PORT = 32082
DEFAULT_POLICY = "P03"
DEFAULT_START_DATA = "0123456789123"


@dataclass
class Config:
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
        parser = argparse.ArgumentParser(description="Loop protect/reveal calls and measure time")
        parser.add_argument("--host", default=DEFAULT_HOST, help="API host")
        parser.add_argument("--port", default=DEFAULT_PORT, type=int, help="API port")
        parser.add_argument("--policy", default=DEFAULT_POLICY, help="protection_policy_name")
        parser.add_argument("--start-data", default=DEFAULT_START_DATA, help="numeric data to start from")
        parser.add_argument("--iterations", default=100, type=int, help="number of iterations")
        parser.add_argument("--timeout", default=10, type=int, help="per-request timeout seconds")
        parser.add_argument("--verbose", action="store_true", help="enable debug logging")
        parser.add_argument("--show-bodies", action="store_true", help="print request and response JSON bodies")
        parser.add_argument("--show-progress", action="store_true", dest="show_progress", help="show per-iteration progress output")
        parser.add_argument("--bulk", action="store_true", help="use bulk protect/reveal endpoints")
        parser.add_argument("--batch-size", default=25, type=int, help="batch size for bulk operations (default 25)")
        args = parser.parse_args(argv)
        return cls(**vars(args))


def increment_numeric_string(s: str) -> str:
    if not s.isdigit():
        raise ValueError("data must be a numeric string")
    width = len(s)
    n = int(s) + 1
    return f"{n:0{width}d}"


def run_iteration(client: ProtectRevealClient, data: str):
    t0 = time.perf_counter()
    protect_payload = {"protection_policy_name": client.policy, "data": data}
    protect_response = client.post_json(client.protect_url, protect_payload)

    protected_token = None
    if isinstance(protect_response, APIResponse):
        if isinstance(protect_response.body, dict):
            protected_token = (protect_response.body.get("protected_data") or
                               protect_response.body.get("protected") or
                               protect_response.body.get("token"))

    reveal_payload = {"protection_policy_name": client.policy, "protected_data": protected_token or ""}
    reveal_response = client.post_json(client.reveal_url, reveal_payload)

    restored = None
    if isinstance(reveal_response, APIResponse) and isinstance(reveal_response.body, dict):
        for k in ("data", "original", "plain", "revealed", "unprotected_data"):
            if k in reveal_response.body:
                restored = reveal_response.body.get(k)
                break

    t1 = time.perf_counter()
    from dataclasses import dataclass as _d

    @_d
    class _R:
        data: str
        protect_response: APIResponse
        reveal_response: APIResponse
        protected_token: Optional[str]
        restored: Optional[str]
        time_s: float

    return _R(data=data, protect_response=protect_response, reveal_response=reveal_response, protected_token=protected_token, restored=restored, time_s=t1 - t0)


def main(argv: Optional[list] = None) -> int:
    config = Config.from_args(argv)
    logging.basicConfig(level=logging.DEBUG if config.verbose else logging.INFO, format="%(message)s")
    logger = logging.getLogger("protect_reveal")

    client = ProtectRevealClient(host=config.host, port=config.port, policy=config.policy, timeout=config.timeout)

    if config.bulk:
        inputs = []
        cur = config.start_data
        for _ in range(config.iterations):
            inputs.append(cur)
            try:
                cur = increment_numeric_string(cur)
            except Exception:
                break

        bulk_results = run_bulk_iteration(client, inputs, batch_size=config.batch_size)

        for idx, b in enumerate(bulk_results, start=1):
            if config.show_bodies:
                pbody = getattr(b.protect_response, 'body', {}) or {}
                rbody = getattr(b.reveal_response, 'body', {}) or {}
                protect_obj = {
                    "status": pbody.get("status", "Success" if getattr(b.protect_response, 'status_code', None) and str(getattr(b.protect_response, 'status_code', '')).startswith('2') else "Error"),
                    "total_count": pbody.get("total_count", len(b.inputs)),
                    "success_count": pbody.get("success_count", len(b.protected_tokens)),
                    "error_count": pbody.get("error_count", max(0, len(b.inputs) - len(b.protected_tokens))),
                    "protected_data_array": [{"protected_data": tok} for tok in b.protected_tokens],
                }
                reveal_obj = {
                    "status": rbody.get("status", "Success" if getattr(b.reveal_response, 'status_code', None) and str(getattr(b.reveal_response, 'status_code', '')).startswith('2') else "Error"),
                    "total_count": rbody.get("total_count", len(b.inputs)),
                    "success_count": rbody.get("success_count", len(b.restored_values)),
                    "error_count": rbody.get("error_count", max(0, len(b.inputs) - len(b.restored_values))),
                    "data_array": [{"data": v} for v in b.restored_values],
                }
                out = {"batch": idx, "protect": protect_obj, "reveal": reveal_obj, "time_s": b.time_s}
                print(json.dumps(out, ensure_ascii=False, indent=2))

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

    # non-bulk iterative mode
    current = config.start_data
    results = []
    t_start = time.perf_counter()
    for i in range(1, config.iterations + 1):
        try:
            r = run_iteration(client, current)
            results.append(r)
            if config.show_progress:
                logger.info("#%03d data=%s time=%.4fs protect_status=%s reveal_status=%s match=%s", i, current, r.time_s, getattr(r.protect_response, 'status_code', 'N/A'), getattr(r.reveal_response, 'status_code', 'N/A'), r.restored == current)
            if config.show_bodies:
                def pretty(x: Any) -> str:
                    try:
                        return json.dumps(x, ensure_ascii=False, indent=2)
                    except Exception:
                        return str(x)
                protect_payload = {"protection_policy_name": config.policy, "data": current}
                reveal_payload = {"protection_policy_name": config.policy, "protected_data": r.protected_token or ""}
                if not config.show_progress:
                    logger.info("#%03d data=%s", i, current)
                logger.info("  Sent protect payload:\n%s", pretty(protect_payload))
                logger.info("  Received protect body:\n%s", pretty(r.protect_response.body))
                logger.info("  Sent reveal payload:\n%s", pretty(reveal_payload))
                logger.info("  Received reveal body:\n%s", pretty(r.reveal_response.body))
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
    successful = sum(1 for r in results if getattr(r.protect_response, 'status_code', 0) and str(getattr(r.protect_response, 'status_code')).startswith('2') and getattr(r.reveal_response, 'status_code', 0) and str(getattr(r.reveal_response, 'status_code')).startswith('2'))
    matched = sum(1 for r in results if r.restored == r.data)
    logger.info("\nSummary:")
    logger.info("Iterations attempted: %d", len(results))
    logger.info("Successful (both 2xx): %d", successful)
    logger.info("Revealed matched original data: %d", matched)
    logger.info("Total time: %.4fs", total)
    if results:
        avg = sum(getattr(r, 'time_s', 0) for r in results) / len(results)
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

