from protect_reveal.runner import run_iteration, IterationResult
from protect_reveal.client import APIResponse


class FakeClient:
    def __init__(self):
        self.policy = "PTEST"
        self.protect_url = "http://example/protect"
        self.reveal_url = "http://example/reveal"
        self._protected = None
        self._map = {}

    def post_json(self, url, payload):
        # return fake protect/reveal bodies depending on url
        if url.endswith('/protect') or 'protect' in url:
            # create a fake token and remember mapping to original data
            token = f"tok-{payload.get('data','')}-id"
            self._protected = token
            self._map[token] = payload.get('data', '')
            return APIResponse(status_code=200, body={"protected_data": token})
        if url.endswith('/reveal') or 'reveal' in url:
            protected = payload.get('protected_data', '')
            return APIResponse(status_code=200, body={"data": self._map.get(protected, '')})
        return APIResponse(status_code=404, body={})

    def extract_protected_from_protect_response(self, response):
        return response.body.get('protected_data')

    def extract_restored_from_reveal_response(self, response):
        return response.body.get('data')


def test_run_iteration_success():
    client = FakeClient()
    res = run_iteration(client, '001')
    assert isinstance(res, IterationResult)
    assert res.protected_token == client._protected
    assert res.restored == '001'
    assert res.match is True
    assert res.success is True
