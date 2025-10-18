from dataclasses import dataclass
from typing import Optional, Any
import argparse
import json
import logging
import time

from .client import ProtectRevealClient, APIError, APIResponse
from .runner import run_iteration, IterationResult, run_bulk_iteration
from .utils import increment_numeric_string


@dataclass
class Config:
    host: str = "192.168.0.231"
    port: int = 32082
    policy: str = "P03"
    start_data: str = "0123456789123"
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
        parser.add_argument("--host", default=cls.host, help="API host")
        parser.add_argument("--port", default=cls.port, type=int, help="API port")
        parser.add_argument("--policy", default=cls.policy, help="protection_policy_name")
        parser.add_argument("--start-data", default=cls.start_data, help="numeric data to start from")
        parser.add_argument("--iterations", default=cls.iterations, type=int, help="number of iterations")
        parser.add_argument("--timeout", default=cls.timeout, type=int, help="per-request timeout seconds")
        parser.add_argument("--verbose", action="store_true", help="enable debug logging")
        parser.add_argument("--show-bodies", action="store_true", help="print request and response JSON bodies")
        parser.add_argument("--show-progress", action="store_true", dest="show_progress", help="show per-iteration progress output")
        parser.add_argument("--bulk", action="store_true", help="use bulk protect/reveal endpoints")
        parser.add_argument("--batch-size", default=25, type=int, help="batch size for bulk operations (default 25)")
        args = parser.parse_args(argv)
        return cls(**vars(args))


def pretty_json(x: Any) -> str:
    try:
        return json.dumps(x, ensure_ascii=False, indent=2)
    except Exception:
        return str(x)


def main(argv: Optional[list] = None) -> int:
    config = Config.from_args(argv)
    logging.basicConfig(level=logging.DEBUG if config.verbose else logging.INFO, format="%(message)s")
    logger = logging.getLogger("protect_reveal")

    client = ProtectRevealClient(host=config.host, port=config.port, policy=config.policy, timeout=config.timeout)

    if config.bulk:
        # build inputs
        inputs = []
        cur = config.start_data
        for _ in range(config.iterations):
            inputs.append(cur)
            try:
                cur = increment_numeric_string(cur)
            except Exception:
                break

        t0 = time.perf_counter()
        bulk_results = run_bulk_iteration(client, inputs, batch_size=config.batch_size)
        t1 = time.perf_counter()

        # detailed per-batch JSON only when requested
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
                print(json.dumps({"batch": idx, "protect": protect_obj, "reveal": reveal_obj, "time_s": b.time_s}, ensure_ascii=False, indent=2))

        # overall summary aligned with non-bulk output
        total_items = sum(len(b.inputs) for b in bulk_results)
        # Count successful items: prefer exact full-batch success, otherwise fall back to restored count
        successful_items = 0
        matched = 0
        for b in bulk_results:
            # matches per item when restore equals input
            try:
                matched += sum(1 for m in b.matches if m)
            except Exception:
                pass
            if getattr(b.protect_response, 'is_success', False) and getattr(b.reveal_response, 'is_success', False) and len(b.restored_values) == len(b.inputs):
                successful_items += len(b.inputs)
            else:
                successful_items += len(b.restored_values)

        wall_total = t1 - t0
        sum_batch_times = sum(getattr(b, 'time_s', 0.0) for b in bulk_results)

        logger.info("\nSummary:")
        logger.info("Iterations attempted: %d", total_items)
        logger.info("Successful (both 2xx): %d", successful_items)
        logger.info("Revealed matched original data: %d", matched)
        logger.info("Total time: %.4fs", wall_total)
        if total_items:
            avg_per_iter = (sum_batch_times / total_items)
            logger.info("Average per-iteration time: %.4fs", avg_per_iter)
        return 0

    # non-bulk iterative path
    current = config.start_data
    results = []
    t_start = time.perf_counter()

    for i in range(1, config.iterations + 1):
        try:
            result = run_iteration(client, current)
            results.append(result)

            if config.show_progress:
                logger.info("#%03d data=%s time=%.4fs protect_status=%s reveal_status=%s match=%s", i, current, result.time_s, result.protect_response.status_code, result.reveal_response.status_code, result.match)

            # show_bodies: print the same JSON structure as bulk per-batch output
            if config.show_bodies:
                pbody = getattr(result.protect_response, 'body', {}) or {}
                rbody = getattr(result.reveal_response, 'body', {}) or {}
                protect_obj = {
                    "status": pbody.get("status", "Success" if result.protect_response and result.protect_response.is_success else "Error"),
                    "total_count": pbody.get("total_count", 1),
                    "success_count": pbody.get("success_count", 1 if result.protected_token else 0),
                    "error_count": pbody.get("error_count", 0 if result.protected_token else 1),
                    "protected_data_array": ([{"protected_data": result.protected_token}] if result.protected_token else []),
                }
                reveal_obj = {
                    "status": rbody.get("status", "Success" if result.reveal_response and result.reveal_response.is_success else "Error"),
                    "total_count": rbody.get("total_count", 1),
                    "success_count": rbody.get("success_count", 1 if result.restored is not None else 0),
                    "error_count": rbody.get("error_count", 0 if result.restored is not None else 1),
                    "data_array": ([{"data": result.restored}] if result.restored is not None else []),
                }
                print(json.dumps({"batch": i, "protect": protect_obj, "reveal": reveal_obj, "time_s": result.time_s}, ensure_ascii=False, indent=2))

            try:
                current = increment_numeric_string(current)
            except ValueError:
                logger.error("data '%s' is not numeric; stopping iterations", current)
                break

        except APIError as e:
            logger.error("API error: %s (status=%s)", e, e.status_code)
            if config.verbose:
                logger.exception("Full traceback:")
            results.append(IterationResult(data=current, protect_response=e.response or APIResponse(None, None), reveal_response=e.response or APIResponse(None, None), protected_token=None, restored=None, time_s=0.0))
            try:
                current = increment_numeric_string(current)
            except Exception:
                break
        except Exception as e:
            logger.error("Unexpected error: %s", e)
            if config.verbose:
                logger.exception("Full traceback:")
            break

    t_end = time.perf_counter()
    total = t_end - t_start

    successful = sum(1 for r in results if getattr(r, 'success', False))
    matched = sum(1 for r in results if getattr(r, 'match', False))

    logger.info("\nSummary:")
    logger.info("Iterations attempted: %d", len(results))
    logger.info("Successful (both 2xx): %d", successful)
    logger.info("Revealed matched original data: %d", matched)
    logger.info("Total time: %.4fs", total)
    if results:
        avg = sum(getattr(r, 'time_s', 0.0) for r in results) / len(results)
        logger.info("Average per-iteration time: %.4fs", avg)

    return 0
