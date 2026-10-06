"""Minimal HTTPS JSON transport for provider adapters.

* Redirects are refused: a credential is never forwarded to another origin.
* The request URL must stay under the configured profile's base URL (no model-chosen URLs).
* TLS certificate verification uses the platform defaults; plain HTTP is allowed only for
  explicitly configured loopback profiles (local test servers).
* Failures are mapped to distinct diagnostics: invalid credentials, rate limit, quota,
  model/endpoint not found, provider error, network error, timeout.
"""

from __future__ import annotations

import http.client
import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise urllib.error.HTTPError(req.full_url, code, "provider redirect refused (credentials are never forwarded)", headers, fp)


_OPENER = urllib.request.build_opener(_NoRedirect)
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_ERROR_BYTES = 16 * 1024


@dataclass
class ProviderError(Exception):
    kind: str          # auth_invalid | rate_limited | quota_exhausted | not_found | provider_error | network | timeout | bad_response
    message: str
    status: int | None = None
    retryable: bool = False
    retry_after: float | None = None

    def __str__(self) -> str:
        return f"{self.kind}: {self.message}"


def _classify(code: int, body: str) -> ProviderError:
    low = body.lower()
    if code in (401, 403):
        return ProviderError("auth_invalid", "credential rejected by the provider", code)
    if code == 404:
        return ProviderError("not_found", "model or endpoint not found", code)
    if code == 429:
        if "quota" in low or "insufficient" in low or "billing" in low or "credit" in low:
            return ProviderError("quota_exhausted", "quota or credit exhausted", code)
        return ProviderError("rate_limited", "rate limited", code, retryable=True)
    if 500 <= code < 600 or code == 529:
        return ProviderError("provider_error", f"provider returned HTTP {code}", code, retryable=True)
    # Provider-controlled error bodies can echo authorization headers. Preserve a stable
    # status/category, never their raw text, in user output or broker transcripts.
    return ProviderError("bad_request", f"provider returned HTTP {code}; response body suppressed", code)


def request(method: str, base_url: str, path: str, headers: dict[str, str], payload: dict[str, Any] | None,
            timeout: float) -> tuple[dict[str, Any], dict[str, str]]:
    url = base_url.rstrip("/") + path
    if not url.startswith(base_url.rstrip("/") + "/"):
        raise ProviderError("bad_request", "request URL escapes the configured endpoint profile")
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={**headers, "Content-Type": "application/json",
                                                                          "Accept": "application/json",
                                                                          "User-Agent": "verislop/0.1"})
    try:
        with _OPENER.open(req, timeout=timeout) as resp:
            raw_body = resp.read(MAX_RESPONSE_BYTES + 1)
            if len(raw_body) > MAX_RESPONSE_BYTES:
                raise ProviderError("bad_response", "provider response exceeded the transport size limit")
            try:
                body = raw_body.decode("utf-8")
            except UnicodeDecodeError:
                raise ProviderError("bad_response", "provider response is not valid UTF-8") from None
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read(MAX_ERROR_BYTES).decode("utf-8", "replace") if exc.fp else ""
        except Exception:  # noqa: BLE001
            pass
        finally:
            exc.close()
        if 300 <= exc.code < 400:
            raise ProviderError("bad_request", "provider redirect or non-success 3xx response refused", exc.code) from None
        err = _classify(exc.code, body)
        ra = exc.headers.get("retry-after") if exc.headers else None
        if ra:
            try:
                err.retry_after = float(ra)
            except ValueError:
                pass
        raise err from None
    except (socket.timeout, TimeoutError):
        raise ProviderError("timeout", f"no response within {timeout}s", retryable=True) from None
    except urllib.error.URLError:
        raise ProviderError("network", "provider network request failed", retryable=True) from None
    except (OSError, http.client.HTTPException):
        raise ProviderError("network", "provider connection failed; transport details suppressed", retryable=True) from None
    except (ValueError, UnicodeError):
        raise ProviderError("bad_request", "provider URL or authentication header is invalid; values suppressed") from None
    try:
        parsed = json.loads(body)
    except (ValueError, RecursionError):
        raise ProviderError("bad_response", "provider response is not JSON") from None
    if not isinstance(parsed, dict):
        raise ProviderError("bad_response", "provider response must be a JSON object")
    return parsed, hdrs
