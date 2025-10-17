from dataclasses import dataclass
from typing import Optional, Any
import argparse
import json
import logging
import time

from .client import ProtectRevealClient, APIError
from .runner import run_iteration, IterationResult
from .utils import increment_numeric_string


@dataclass
class Config:
    host: str = "192.168.0.231"
    port: int = 32082
    policy: str = "Pol01"
    start_data: str = "0123456789123456"
    iterations: int = 100
    timeout: int = 10
    verbose: bool = False
    show_bodies: bool = False
    show_progress: bool = False

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

    current = config.start_data
    results = []
    t_start = time.perf_counter()

    for i in range(1, config.iterations + 1):
        try:
            result = run_iteration(client, current)
            results.append(result)

            if config.show_progress:
                logger.info("#%03d data=%s time=%.4fs protect_status=%s reveal_status=%s match=%s", i, current, result.time_s, result.protect_response.status_code, result.reveal_response.status_code, result.match)

                if config.show_bodies:
                    logger.info("  Sent protect payload:\n%s", pretty_json({"protection_policy_name": config.policy, "data": current}))
                    logger.info("  Received protect body:\n%s", pretty_json(result.protect_response.body))
                    logger.info("  Sent reveal payload:\n%s", pretty_json({"protection_policy_name": config.policy, "protected_data": result.protected_token or ""}))
                    logger.info("  Received reveal body:\n%s", pretty_json(result.reveal_response.body))

            try:
                current = increment_numeric_string(current)
            except ValueError:
                logger.error("data '%s' is not numeric; stopping iterations", current)
                break

        except APIError as e:
            logger.error("API error: %s (status=%s)", e, e.status_code)
            if config.verbose:
                logger.exception("Full traceback:")
            results.append(IterationResult(data=current, protect_response=e.response or None, reveal_response=e.response or None, protected_token=None, restored=None, time_s=0.0))
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
