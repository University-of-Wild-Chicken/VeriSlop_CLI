"""Adapter and endpoint-profile registry (docs/provider-sources.md).

Provider family, region, base URL, protocol, auth scheme and capabilities are distinct fields.
A profile whose base URL depends on the user's account/region/workspace ships without a base
URL and must be completed by an explicit user-defined profile; VeriSlop never guesses one.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

UNTESTED = "implemented; live-service conformance not tested in this release"

ADAPTERS: dict[str, dict[str, Any]] = {
    "openai": {"protocol": ["responses", "chat_completions"], "auth": "bearer", "status": UNTESTED},
    "anthropic": {"protocol": ["anthropic_messages"], "auth": "x-api-key", "status": UNTESTED},
    "google_gemini": {"protocol": ["gemini_generate_content"], "auth": "x-goog-api-key", "status": UNTESTED},
    "google_vertex": {"protocol": ["vertex_generate_content"], "auth": "google-cloud-oauth",
                      "status": "unsupported in v0.1: Vertex AI needs Google Cloud OAuth credentials, a separate auth profile"},
    "deepseek": {"protocol": ["chat_completions"], "auth": "bearer", "status": UNTESTED},
    "alibaba_model_studio": {"protocol": ["chat_completions"], "auth": "bearer", "status": UNTESTED},
    "zai": {"protocol": ["chat_completions"], "auth": "bearer", "status": UNTESTED},
    "zhipu": {"protocol": ["chat_completions"], "auth": "bearer", "status": UNTESTED},
    "moonshot": {"protocol": ["chat_completions"], "auth": "bearer", "status": UNTESTED},
    "xai": {"protocol": ["responses", "chat_completions"], "auth": "bearer", "status": UNTESTED},
    "meta": {"protocol": ["responses", "chat_completions", "anthropic_messages"], "auth": "bearer", "status": UNTESTED},
    "openai_compatible": {"protocol": ["chat_completions", "responses"], "auth": "bearer", "status": UNTESTED},
    "ollama": {"protocol": ["ollama_chat"], "auth": "none or configured bearer",
               "status": "implemented; bounded local Ollama inference tested; general agent tasks not certified"},
    "custom": {"protocol": [], "auth": "custom", "status": "unsupported in v0.1: custom adapters require a registered plugin"},
}

# Capabilities VeriSlop roles need: plain text generation with a separate system instruction.
# Structured output is requested as JSON text and validated by VeriSlop, never trusted.
ROLE_CAPABILITIES = {"text_generation", "system_instruction"}
FAMILY_CAPABILITIES = {
    "responses": {"text_generation", "system_instruction"},
    "chat_completions": {"text_generation", "system_instruction"},
    "ollama_chat": {"text_generation", "system_instruction", "json_output"},
    "anthropic_messages": {"text_generation", "system_instruction"},
    "gemini_generate_content": {"text_generation", "system_instruction"},
    "vertex_generate_content": set(),
    "custom": set(),
}

BUILTIN_PROFILES: dict[str, dict[str, Any]] = {
    "ollama-local": {"adapter": "ollama", "base_url": "http://localhost:11434", "auth_scheme": "none",
                     "families": ["ollama_chat"], "region": "local", "auth_check": "GET /api/tags",
                     "allow_insecure_loopback": True},
    "openai-direct": {"adapter": "openai", "base_url": "https://api.openai.com/v1", "auth_scheme": "bearer",
                      "families": ["responses", "chat_completions"], "region": "global", "auth_check": "GET /models"},
    "anthropic-direct": {"adapter": "anthropic", "base_url": "https://api.anthropic.com/v1", "auth_scheme": "x-api-key",
                         "api_version": "2023-06-01", "families": ["anthropic_messages"], "region": "global",
                         "auth_check": "GET /models"},
    "gemini-developer": {"adapter": "google_gemini", "base_url": "https://generativelanguage.googleapis.com/v1beta",
                         "auth_scheme": "x-goog-api-key", "families": ["gemini_generate_content"], "region": "global",
                         "auth_check": "GET /models"},
    "deepseek-direct": {"adapter": "deepseek", "base_url": "https://api.deepseek.com", "auth_scheme": "bearer",
                        "families": ["chat_completions"], "region": "global", "auth_check": "GET /models"},
    "zai-general": {"adapter": "zai", "base_url": "https://api.z.ai/api/paas/v4", "auth_scheme": "bearer",
                    "families": ["chat_completions"], "region": "global", "auth_check": None},
    "moonshot-direct": {"adapter": "moonshot", "base_url": "https://api.moonshot.ai/v1", "auth_scheme": "bearer",
                        "families": ["chat_completions"], "region": "global", "auth_check": "GET /models"},
    "xai-inference": {"adapter": "xai", "base_url": "https://api.x.ai/v1", "auth_scheme": "bearer",
                      "families": ["responses", "chat_completions"], "region": "global", "auth_check": "GET /models"},
    "meta-model-api": {"adapter": "meta", "base_url": None, "auth_scheme": "bearer",
                       "families": ["responses", "chat_completions", "anthropic_messages"], "region": None,
                       "auth_check": None,
                       "unresolved": "the Meta Model API base URL is not shipped; define it in a user endpoint profile"},
    "user-selected-dashscope-region-workspace": {
        "adapter": "alibaba_model_studio", "base_url": None, "auth_scheme": "bearer", "families": ["chat_completions"],
        "region": None, "auth_check": "GET /models",
        "unresolved": "DashScope region/workspace cannot be inferred from a key; define the base URL for your region",
    },
}


def resolve_profile(pid: str, user_profiles: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    """User-defined profiles override built-ins of the same ID (explicit configuration)."""
    if pid in user_profiles:
        return {**user_profiles[pid], "source": "user"}
    if pid in BUILTIN_PROFILES:
        return {**BUILTIN_PROFILES[pid], "source": "builtin"}
    return None


def is_ollama_profile(profile: dict[str, Any]) -> bool:
    """User-selected server origins/prefixes; HTTP needs an explicit profile opt-in."""
    try:
        url = urlsplit(profile.get("base_url") or "")
        loopback = url.hostname in {"localhost", "127.0.0.1", "::1"}
        permitted_http = (loopback and profile.get("allow_insecure_loopback") is True) or profile.get("allow_insecure_http") is True
        return (profile.get("adapter") == "ollama" and profile.get("auth_scheme") in {"none", "bearer"}
                and url.scheme in {"http", "https"} and bool(url.hostname)
                and url.username is None and url.password is None and not url.query and not url.fragment
                and (url.port is None or 1 <= url.port <= 65535)
                and not any(c.isspace() for c in profile["base_url"])
                and (url.scheme != "http" or permitted_http))
    except ValueError:
        return False
