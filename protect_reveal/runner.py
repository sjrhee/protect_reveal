"""작업 단일 반복을 수행하는 실행기.

run_iteration은 제공된 `ProtectRevealClient`를 사용해 protect -> reveal 순서로
요청을 보내고, 소요 시간과 응답을 담은 `IterationResult`를 반환합니다.
"""

from dataclasses import dataclass
from typing import Optional
import time

from .client import APIResponse, ProtectRevealClient


@dataclass
class IterationResult:
    data: str
    protect_response: APIResponse
    reveal_response: APIResponse
    protected_token: Optional[str]
    restored: Optional[str]
    time_s: float

    @property
    def match(self) -> bool:
        return self.restored == self.data if self.restored is not None else False

    @property
    def success(self) -> bool:
        return self.protect_response.is_success and self.reveal_response.is_success


def run_iteration(client: ProtectRevealClient, data: str) -> IterationResult:
    t0 = time.perf_counter()

    protect_payload = {"protection_policy_name": client.policy, "data": data}
    protect_response = client.post_json(client.protect_url, protect_payload)

    protected_token = client.extract_protected_from_protect_response(protect_response)

    reveal_payload = {"protection_policy_name": client.policy, "protected_data": protected_token or ""}
    reveal_response = client.post_json(client.reveal_url, reveal_payload)

    restored = client.extract_restored_from_reveal_response(reveal_response)
    t1 = time.perf_counter()

    return IterationResult(
        data=data,
        protect_response=protect_response,
        reveal_response=reveal_response,
        protected_token=protected_token,
        restored=restored,
        time_s=t1 - t0,
    )
