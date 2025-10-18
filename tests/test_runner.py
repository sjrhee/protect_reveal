from protect_reveal.client import APIResponse, ProtectRevealClient
from protect_reveal.runner import run_bulk_iteration


class DummyResp(APIResponse):
    pass


def test_run_bulk_iteration_happy_path(monkeypatch):
    # Prepare a client whose protect_bulk and reveal_bulk return expected shapes
    client = ProtectRevealClient(host="h", port=1, policy="p")

    def fake_protect_bulk(items):
        # return APIResponse-like object
        # derive token suffix from the numeric value of the input string (001 -> 1)
        return APIResponse(status_code=200, body={
            "protected_data_array": [{"protected_data": f"tok{int(it)}"} for it in items]
        })

    def fake_reveal_bulk(items):
        # items are protected tokens like 'tok1' -> map back to orig1
        def token_to_orig(it):
            if isinstance(it, str) and it.startswith('tok'):
                try:
                    return f"orig{int(it[3:])}"
                except Exception:
                    return f"orig_{it}"
            # fallback: if it's a dict with 'protected_data'
            if isinstance(it, dict) and 'protected_data' in it:
                v = it['protected_data']
                return token_to_orig(v)
            return f"orig_{it}"

        return APIResponse(status_code=200, body={
            "data_array": [{"data": token_to_orig(it)} for it in items]
        })

    monkeypatch.setattr(client, "protect_bulk", fake_protect_bulk)
    monkeypatch.setattr(client, "reveal_bulk", fake_reveal_bulk)

    inputs = ["001", "002", "003", "004"]
    results = run_bulk_iteration(client, inputs, batch_size=2)

    # expect two batches
    assert len(results) == 2
    # check protected tokens and restored values
    assert results[0].protected_tokens == ["tok1", "tok2"]
    assert results[0].restored_values == ["orig1", "orig2"]
    assert results[1].protected_tokens == ["tok3", "tok4"]
    assert results[1].restored_values == ["orig3", "orig4"]
