"""H01: public errors detach private HTTP exceptions; all transport is simulated."""
import json
import traceback

import httpx
import pytest

from investment_system.llm.openai_client import OpenAIClient
from investment_system.llm.openai_settings import LLMProviderError
from investment_system.llm.schemas import LLMRequest
from test_news_interpretation_runtime import MODEL, NOW, settings


SYNTHETIC_KEY = "synthetic-h01-key-never-a-real-credential"
SYNTHETIC_BODY = "synthetic-h01-private-provider-body"


@pytest.fixture(autouse=True)
def synthetic_credentials(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", SYNTHETIC_KEY)


def invoke(handler):
    request = LLMRequest(
        agent="NewsAgent", task="news_interpretation",
        prompt='Synthetic transport test only\n{"fixture": true}',
        response_schema={"type": "object", "properties": {"ok": {"type": "boolean"}}},
    )
    client = OpenAIClient(settings().adapter, enabled=True, transport=httpx.MockTransport(handler))
    return client.complete(request, MODEL)


def assert_safe_error(error, code, retryable):
    assert type(error) is LLMProviderError
    assert error.args == (code,) and str(error) == error.code == code
    assert error.retryable is retryable and error.response is None
    assert error.__context__ is None and error.__cause__ is None
    assert not any(isinstance(value, (BaseException, httpx.Request, httpx.Response,
                                     httpx.Headers, httpx.BaseTransport))
                   for value in vars(error).values())
    public = repr(vars(error)) + repr(error.args) + "".join(traceback.format_exception(error))
    assert SYNTHETIC_KEY not in public and SYNTHETIC_BODY not in public


@pytest.mark.parametrize("error_type,code", [
    (httpx.ReadTimeout, "timeout"),
    (httpx.ConnectTimeout, "timeout"),
    (httpx.ConnectError, "disconnect"),
    (httpx.ReadError, "disconnect"),
])
def test_transport_exception_detached_without_mutating_private_error(error_type, code, caplog, capsys):
    private_errors = []

    def fail(request):
        assert request.headers["Authorization"] == "Bearer " + SYNTHETIC_KEY
        error = error_type(SYNTHETIC_BODY, request=request)
        private_errors.append(error)
        raise error

    with pytest.raises(LLMProviderError) as caught:
        invoke(fail)
    assert_safe_error(caught.value, code, True)
    assert len(private_errors) == 1  # The client still performs no automatic retries.
    assert str(private_errors[0]) == SYNTHETIC_BODY
    assert private_errors[0].request.headers["Authorization"] == "Bearer " + SYNTHETIC_KEY
    assert not caplog.text
    assert capsys.readouterr() == ("", "")


def test_invalid_json_body_is_not_retained_in_public_exception(caplog, capsys):
    responses = []

    def invalid(request):
        response = httpx.Response(200, text=SYNTHETIC_KEY + SYNTHETIC_BODY, request=request)
        responses.append(response)
        return response

    with pytest.raises(LLMProviderError) as caught:
        invoke(invalid)
    assert_safe_error(caught.value, "invalid_provider_envelope", True)
    # Private transport objects are not redacted or otherwise mutated by the fix.
    assert responses[0].text == SYNTHETIC_KEY + SYNTHETIC_BODY
    assert not caplog.text
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("body", [
    {"private": SYNTHETIC_BODY},  # Missing mandatory model key.
    {"model": MODEL, "created_at": SYNTHETIC_BODY},  # Type error while decoding.
])
def test_invalid_envelope_preserves_public_error_contract(body):
    with pytest.raises(LLMProviderError) as caught:
        invoke(lambda request: httpx.Response(200, json=body, request=request))
    assert_safe_error(caught.value, "invalid_provider_envelope", True)


@pytest.mark.parametrize("status,code,retryable", [
    (401, "authentication", False), (403, "authorization", False),
    (400, "permanent_http_error", False), (302, "permanent_http_error", False),
    (429, "rate_limit", True), (503, "server_error", True),
])
def test_http_error_contract_remains_sanitized(status, code, retryable):
    with pytest.raises(LLMProviderError) as caught:
        invoke(lambda request: httpx.Response(status, text=SYNTHETIC_BODY, request=request))
    assert_safe_error(caught.value, code, retryable)


def test_valid_provider_response_preserves_content_usage_and_wire():
    calls = []
    content = '{"ok": true}'

    def valid(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={
            "model": MODEL, "created_at": NOW.timestamp(), "status": "completed",
            "output": [{"type": "message", "content": [{"type": "output_text", "text": content}]}],
            "usage": {"input_tokens": 100, "output_tokens": 20,
                      "input_tokens_details": {"cached_tokens": 10, "cache_write_tokens": 5}},
        }, request=request)

    response = invoke(valid)
    assert response.model == MODEL and response.content == content and response.generated_at == NOW
    assert (response.input_tokens, response.cached_input_tokens, response.output_tokens) == (100, 10, 20)
    assert response.raw["cache_write_tokens"] == 5 and response.raw["usage_reported"] is True
    assert len(calls) == 1
    assert calls[0]["tools"] == [] and calls[0]["store"] is False
    assert calls[0]["background"] is False and calls[0]["text"]["format"]["strict"] is True
