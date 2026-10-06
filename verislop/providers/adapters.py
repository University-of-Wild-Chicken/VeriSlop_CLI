"""Protocol adapters: build requests and parse text completions for each API family.

Compatible syntax does not imply identical semantics: adapters only use plain text generation
with a separate system instruction, and record requested and returned model identities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .http import ProviderError, request


@dataclass
class Completion:
    text: str
    requested_model: str
    returned_model: str | None
    request_id: str | None
    input_tokens: int | None
    output_tokens: int | None


def _contains_secret(value: Any, secret: str) -> bool:
    if not secret:
        return False
    pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, str) and secret in item:
            return True
        if isinstance(item, dict):
            pending.extend(item.keys())
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    return False


def _inference_request(base: str, path: str, headers: dict[str, str], payload: dict[str, Any],
                       timeout: float, secret: str) -> tuple[dict[str, Any], dict[str, str]]:
    body, hdr = request("POST", base, path, headers, payload, timeout)
    # The secret is still in the adapter's scope here. Reject echoed credentials before
    # response text/metadata can reach a broker transcript or command output.
    if _contains_secret(body, secret) or _contains_secret(hdr, secret):
        raise ProviderError("credential_leak", "provider response contained credential material; response suppressed")
    return body, hdr


def _objects(value: Any, location: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ProviderError("bad_response", f"{location} must be an array of objects")
    return value


def _usage(body: dict[str, Any], field: str = "usage") -> dict[str, Any]:
    value = body.get(field)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ProviderError("bad_response", f"{field} must be an object")
    return value


def _completion(text: Any, model: str, returned_model: Any, request_id: Any,
                input_tokens: Any, output_tokens: Any) -> Completion:
    if not isinstance(text, str) or not text:
        raise ProviderError("bad_response", "provider returned no string completion text")
    for name, value in (("returned model", returned_model), ("request ID", request_id)):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ProviderError("bad_response", f"{name} must be a nonempty string when present")
    try:
        for value in (text, returned_model, request_id):
            if value is not None:
                value.encode("utf-8")
    except UnicodeEncodeError:
        raise ProviderError("bad_response", "completion text or metadata contains invalid Unicode") from None
    for name, value in (("input token usage", input_tokens), ("output token usage", output_tokens)):
        if value is not None and (type(value) is not int or value < 0):
            raise ProviderError("bad_response", f"{name} must be a nonnegative integer when present")
    return Completion(text, model, returned_model, request_id, input_tokens, output_tokens)


def _text_parts(parts: list[dict[str, Any]], text_key: str = "text") -> str:
    values = [part.get(text_key, "") for part in parts]
    if any(not isinstance(value, str) for value in values):
        raise ProviderError("bad_response", "completion text parts must be strings")
    return "".join(values)


def _headers(profile: dict[str, Any], secret: str) -> dict[str, str]:
    scheme = profile["auth_scheme"]
    if scheme == "bearer":
        return {"Authorization": f"Bearer {secret}"}
    if scheme == "x-api-key":
        h = {"x-api-key": secret}
        if profile.get("api_version"):
            h["anthropic-version"] = profile["api_version"]
        return h
    if scheme == "x-goog-api-key":
        return {"x-goog-api-key": secret}
    raise ProviderError("bad_request", f"unsupported auth scheme {scheme}")


def complete(family: str, profile: dict[str, Any], secret: str, model: str, system: str, user: str,
             max_output_tokens: int, timeout: float) -> Completion:
    base = profile["base_url"]
    h = _headers(profile, secret)
    if family == "chat_completions":
        body, hdr = _inference_request(base, "/chat/completions", h, {
            "model": model, "max_tokens": max_output_tokens,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}, timeout, secret)
        try:
            text = body["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise ProviderError("bad_response", "chat completion without choices[0].message.content") from None
        usage = _usage(body)
        return _completion(text, model, body.get("model"), body.get("id") or hdr.get("x-request-id"),
                           usage.get("prompt_tokens"), usage.get("completion_tokens"))
    if family == "responses":
        body, hdr = _inference_request(base, "/responses", h, {
            "model": model, "instructions": system, "input": user, "max_output_tokens": max_output_tokens}, timeout, secret)
        parts = []
        for item in _objects(body.get("output", []) or [], "responses.output"):
            if item.get("type") == "message":
                for c in _objects(item.get("content", []) or [], "responses.output.content"):
                    if c.get("type") in ("output_text", "text"):
                        parts.append(c)
        if not parts and isinstance(body.get("output_text"), str):
            parts.append({"text": body["output_text"]})
        if not parts:
            raise ProviderError("bad_response", "responses API returned no output text")
        usage = _usage(body)
        return _completion(_text_parts(parts), model, body.get("model"), body.get("id") or hdr.get("x-request-id"),
                           usage.get("input_tokens"), usage.get("output_tokens"))
    if family == "anthropic_messages":
        body, hdr = _inference_request(base, "/messages", h, {
            "model": model, "max_tokens": max_output_tokens, "system": system,
            "messages": [{"role": "user", "content": user}]}, timeout, secret)
        parts = [c for c in _objects(body.get("content", []) or [], "messages.content") if c.get("type") == "text"]
        if not parts:
            raise ProviderError("bad_response", "messages API returned no text content")
        usage = _usage(body)
        return _completion(_text_parts(parts), model, body.get("model"), body.get("id") or hdr.get("request-id"),
                           usage.get("input_tokens"), usage.get("output_tokens"))
    if family == "gemini_generate_content":
        if "/" in model or ":" in model:
            raise ProviderError("bad_request", "model identifier must not contain path separators")
        body, hdr = _inference_request(base, f"/models/{model}:generateContent", h, {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"maxOutputTokens": max_output_tokens}}, timeout, secret)
        try:
            parts = _objects(body["candidates"][0]["content"]["parts"], "generateContent.candidate.parts")
        except (KeyError, IndexError, TypeError):
            raise ProviderError("bad_response", "generateContent returned no candidate text") from None
        usage = _usage(body, "usageMetadata")
        return _completion(_text_parts(parts), model, body.get("modelVersion"), body.get("responseId"),
                           usage.get("promptTokenCount"), usage.get("candidatesTokenCount"))
    raise ProviderError("bad_request", f"unsupported API family {family}")


def auth_check(profile: dict[str, Any], secret: str, timeout: float) -> dict[str, Any]:
    """The documented minimal authenticated request: list models (no inference, no model call)."""
    check = profile.get("auth_check")
    if not check:
        return {"ok": None, "performed": False, "may_incur_model_call": True,
                "diagnostic": "no documented non-inference check for this profile; skipped to avoid a model call"}
    method, path = check.split(" ", 1)
    try:
        request(method, profile["base_url"], path, _headers(profile, secret), None, timeout)
    except ProviderError as exc:
        return {"ok": False, "performed": True, "may_incur_model_call": False, "diagnostic": str(exc), "kind": exc.kind}
    return {"ok": True, "performed": True, "may_incur_model_call": False, "diagnostic": "authenticated"}
