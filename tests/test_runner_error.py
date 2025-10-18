from protect_reveal.client import APIResponse, ProtectRevealClient
from protect_reveal.runner import run_bulk_iteration


def test_run_bulk_iteration_partial_failure(monkeypatch):
    client = ProtectRevealClient(host="h", port=1, policy="p")

    def fake_protect_bulk(items):
        # first batch returns success, second batch returns an error response
        if items[0] == "001":
            return APIResponse(
                status_code=200,
                body={
                    "protected_data_array": [
                        {"protected_data": "tok1"},
                        {"protected_data": "tok2"},
                    ]
                },
            )
        return APIResponse(status_code=500, body={"error": "server error"})

    def fake_reveal_bulk(items):
        return APIResponse(status_code=200, body={"data_array": [{"data": "orig1"}, {"data": "orig2"}]})

    monkeypatch.setattr(client, "protect_bulk", fake_protect_bulk)
    monkeypatch.setattr(client, "reveal_bulk", fake_reveal_bulk)

    inputs = ["001", "002", "003", "004"]
    results = run_bulk_iteration(client, inputs, batch_size=2)

    # two batches
    assert len(results) == 2
    # first batch succeeded
    assert results[0].protect_response.status_code == 200
    # second batch returned an error status code (500)
    assert results[1].protect_response.status_code == 500
