"""Protocol adapters: build requests and parse text completions for each API family.

Compatible syntax does not imply identical semantics: adapters only use plain text generation
with a separate system instruction, and record requested and returned model identities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .http import ProviderError, request
from .registry import is_ollama_profile


@dataclass
class Completion:
    text: str
    requested_model: str
    returned_model: str | None
    request_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    model_digest_sha256: str | None = None


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
                       timeout: float | None, secret: str) -> tuple[dict[str, Any], dict[str, str]]:
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
    if profile.get("adapter") == "ollama" and not is_ollama_profile(profile):
        raise ProviderError("bad_request", "Ollama requires an explicitly permitted server endpoint")
    scheme = profile["auth_scheme"]
    if scheme == "none" and profile["adapter"] == "ollama":
        return {}
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
             max_output_tokens: int, timeout: float | None) -> Completion:
    base = profile["base_url"]
    h = _headers(profile, secret)
    if family == "ollama_chat":
        body, hdr = _inference_request(base, "/api/chat", h, {
            "model": model, "stream": False, "format": "json", "think": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "options": {"num_predict": max_output_tokens, "temperature": 0}}, timeout, secret)
        if body.get("done") is not True or body.get("error") is not None:
            raise ProviderError("bad_response", "Ollama returned an unfinished or error completion")
        if body.get("done_reason") not in {None, "stop"}:
            raise ProviderError("bad_response", "Ollama completion ended before a normal stop")
        message = body.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant" or message.get("tool_calls"):
            raise ProviderError("bad_response", "Ollama returned no plain assistant completion")
        return _completion(message.get("content"), model, body.get("model"), hdr.get("x-request-id"),
                           body.get("prompt_eval_count"), body.get("eval_count"))
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


def ollama_model_digest(profile: dict[str, Any], model: str, timeout: float | None, secret: str = "") -> str:
    """Record the local catalog identity, never pull a missing model or infer a name.

    Before/after catalog checks detect ordinary replacement; the configured server remains
    trusted to run those weights. A catalog observation is not a weight attestation.
    """
    body, hdr = request("GET", profile["base_url"], "/api/tags", _headers(profile, secret), None, timeout)
    if _contains_secret(body, secret) or _contains_secret(hdr, secret):
        raise ProviderError("credential_leak", "Ollama model catalog contained credential material; response suppressed")
    models = _objects(body.get("models"), "Ollama models")
    names = {model}
    if ":" not in model.rsplit("/", 1)[-1]:
        names.add(model + ":latest")
    matches = [entry for entry in models if entry.get("name") in names or entry.get("model") in names]
    if len(matches) != 1:
        raise ProviderError("not_found", "requested Ollama model must resolve to one installed local catalog entry")
    entry = matches[0]
    if entry.get("remote_host") or entry.get("remote_model"):
        raise ProviderError("bad_request", "remote Ollama models are outside the local adapter")
    digest = entry.get("digest")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ProviderError("bad_response", "Ollama model catalog omitted a canonical SHA-256 digest")
    return digest


def auth_check(profile: dict[str, Any], secret: str, timeout: float | None) -> dict[str, Any]:
    """The documented minimal catalog request (no inference, no model call)."""
    check = "GET /api/tags" if profile["adapter"] == "ollama" else profile.get("auth_check")
    if not check:
        return {"ok": None, "performed": False, "may_incur_model_call": True,
                "diagnostic": "no documented non-inference check for this profile; skipped to avoid a model call"}
    method, path = check.split(" ", 1)
    catalog = None
    try:
        body, hdr = request(method, profile["base_url"], path, _headers(profile, secret), None, timeout)
        if profile["adapter"] == "ollama":
            if _contains_secret(body, secret) or _contains_secret(hdr, secret):
                raise ProviderError("credential_leak", "Ollama model catalog contained credential material; response suppressed")
            catalog = []
            for entry in _objects(body.get("models"), "Ollama models"):
                name, digest = entry.get("name", entry.get("model")), entry.get("digest")
                if not isinstance(name, str) or not name or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                    raise ProviderError("bad_response", "Ollama catalog entry omitted a model name or canonical SHA-256 digest")
                catalog.append({"name": name, "model_digest_sha256": digest,
                                "installed_on_configured_server": not bool(entry.get("remote_host") or entry.get("remote_model"))})
    except ProviderError as exc:
        return {"ok": False, "performed": True, "may_incur_model_call": False, "diagnostic": str(exc), "kind": exc.kind}
    result = {"ok": True, "performed": True, "may_incur_model_call": False,
              "diagnostic": "Ollama model catalog reachable" if profile["adapter"] == "ollama" else "authenticated"}
    if catalog is not None:
        result["available_models"] = catalog
    return result
