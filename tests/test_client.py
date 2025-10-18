from protect_reveal.client import APIResponse, ProtectRevealClient


def test_extract_protected_list_from_protect_response_simple():
    # protect response returns protected_data_array shape
    resp = APIResponse(status_code=200, body={
        "protected_data_array": [{"protected_data": "tok1"}, {"protected_data": "tok2"}]
    })
    client = ProtectRevealClient(host="h", port=1, policy="p")
    out = client.extract_protected_list_from_protect_response(resp)
    assert out == ["tok1", "tok2"]


def test_extract_restored_list_from_reveal_response_fallback():
    # reveal response returns data_array shape
    resp = APIResponse(status_code=200, body={
        "data_array": [{"data": "orig1"}, {"data": "orig2"}]
    })
    client = ProtectRevealClient(host="h", port=1, policy="p")
    out = client.extract_restored_list_from_reveal_response(resp)
    assert out == ["orig1", "orig2"]
