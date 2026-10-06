"""Provider/agent/review configuration (schemas/review-config.schema.json) and its semantic checks.

Parsing makes no network requests. Only providers actually used by a role, a review slot or a
declared fallback need credentials; unused registry entries never force the user to obtain a
token. Unsupported required capabilities are configuration diagnostics, never fabricated calls.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import canonical, schemas
from ..errors import Diagnostic, UsageError
from .registry import ADAPTERS, FAMILY_CAPABILITIES, ROLE_CAPABILITIES, resolve_profile

DEFAULT_PROFILES_PATH = "endpoint-profiles.json"


def config_home() -> Path:
    return Path(os.environ.get("VERISLOP_CONFIG_HOME", Path.home() / ".config" / "verislop"))


def load(path: Path) -> dict[str, Any]:
    try:
        conf = canonical.load_file(path)
    except (OSError, canonical.CanonicalJSONError) as exc:
        raise UsageError(f"cannot read configuration {path}: {exc}") from None
    issues = schemas.validate("review-config", conf)
    if issues:
        raise UsageError(f"configuration {path} is invalid", [Diagnostic("CONFIGURATION_INVALID", str(i)) for i in issues[:20]])
    return conf


def load_user_profiles(path: Path | None) -> dict[str, dict[str, Any]]:
    candidates = [path] if path else [config_home() / DEFAULT_PROFILES_PATH]
    for p in candidates:
        if p and p.is_file():
            data = canonical.load_file(p)
            issues = schemas.validate("endpoint-profiles", data)
            if issues:
                raise UsageError(f"endpoint profiles {p} are invalid",
                                 [Diagnostic("CONFIGURATION_INVALID", str(i)) for i in issues[:20]])
            for pid, prof in data["profiles"].items():
                if prof["base_url"].startswith("http://") and not prof.get("allow_insecure_loopback"):
                    raise UsageError(f"profile {pid}: plain-HTTP loopback endpoints require allow_insecure_loopback=true")
            return data["profiles"]
    return {}


@dataclass
class Resolved:
    conf: dict[str, Any]
    profiles: dict[str, dict[str, Any]]           # provider name -> resolved endpoint profile
    used_providers: set[str]
    used_agents: set[str]
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def agent(self, name: str) -> dict[str, Any]:
        return self.conf["agents"][name]

    def provider(self, name: str) -> dict[str, Any]:
        return self.conf["providers"][name]


def resolve(conf: dict[str, Any], user_profiles: dict[str, dict[str, Any]]) -> Resolved:
    diags: list[Diagnostic] = []
    agents = conf["agents"]
    providers = conf["providers"]
    used_agents: set[str] = set()
    for role, agent in conf["roles"].items():
        if agent not in agents:
            diags.append(Diagnostic("CONFIGURATION_INVALID", f"role {role} references unknown agent {agent}"))
        used_agents.add(agent)
    tier_ids: set[str] = set()
    for tier in conf["review"]["review_tiers"]:
        if tier["id"] in tier_ids:
            diags.append(Diagnostic("CONFIGURATION_INVALID", f"duplicate review tier ID {tier['id']}"))
        tier_ids.add(tier["id"])
        total = sum(g["count"] for g in tier["reviewers"])
        for g in tier["reviewers"]:
            if g["agent"] not in agents:
                diags.append(Diagnostic("CONFIGURATION_INVALID", f"review tier {tier['id']} references unknown agent {g['agent']}"))
            elif agents[g["agent"]]["tool_profile"] != "review_readonly":
                diags.append(Diagnostic("CONFIGURATION_INVALID", f"reviewer agent {g['agent']} must use tool_profile review_readonly"))
            used_agents.add(g["agent"])
        cons = tier["consensus"]
        if cons["mode"] == "quorum" and cons["min_accepts"] > total:
            diags.append(Diagnostic("CONFIGURATION_INVALID", f"tier {tier['id']}: min_accepts {cons['min_accepts']} exceeds the {total} configured reviewers"))
    used_providers: set[str] = set()
    for a in sorted(used_agents):
        if a not in agents:
            continue
        p = agents[a]["provider"]
        if p not in providers:
            diags.append(Diagnostic("CONFIGURATION_INVALID", f"agent {a} references unknown provider {p}"))
            continue
        used_providers.add(p)
    resolved: dict[str, dict[str, Any]] = {}
    for name, prov in providers.items():
        prof = resolve_profile(prov["endpoint_profile"], user_profiles)
        used = name in used_providers
        sev = "blocking" if used else "warning"
        if prof is None:
            diags.append(Diagnostic("CONFIGURATION_INVALID", f"provider {name}: endpoint profile {prov['endpoint_profile']!r} does not resolve", severity=sev))
            continue
        if prof.get("base_url") is None:
            diags.append(Diagnostic("CONFIGURATION_INVALID", f"provider {name}: {prof.get('unresolved', 'profile has no base URL')}", severity=sev))
        if prof["adapter"] != prov["adapter"]:
            diags.append(Diagnostic("CONFIGURATION_INVALID", f"provider {name}: adapter {prov['adapter']} does not match profile adapter {prof['adapter']}", severity=sev))
        adapter = ADAPTERS[prov["adapter"]]
        if adapter["status"].startswith("unsupported"):
            diags.append(Diagnostic("CONFIGURATION_INVALID", f"provider {name}: adapter {prov['adapter']} is {adapter['status']}", severity=sev))
        if prov["api_family"] not in adapter["protocol"] or prov["api_family"] not in prof["families"]:
            diags.append(Diagnostic("CONFIGURATION_INVALID", f"provider {name}: API family {prov['api_family']} is not supported by adapter/profile", severity=sev))
        missing = ROLE_CAPABILITIES - FAMILY_CAPABILITIES.get(prov["api_family"], set())
        if missing:
            diags.append(Diagnostic("CONFIGURATION_INVALID", f"provider {name}: missing required capabilities {sorted(missing)}", severity=sev))
        resolved[name] = prof
    return Resolved(conf, resolved, used_providers, used_agents, diags)


def redacted(conf: dict[str, Any]) -> dict[str, Any]:
    """Configuration for hashing into review targets: credential references removed."""
    out = canonical.loads(canonical.dumps(conf))
    for prov in out.get("providers", {}).values():
        prov.pop("credential_ref", None)
    return out
