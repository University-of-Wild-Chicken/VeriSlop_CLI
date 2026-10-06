"""`verislop providers check`: configuration, capability and (optionally) live auth checks.

Without `--live` this makes no network request at all. With `--live` it performs only the
documented minimal authenticated request per used provider (listing models) and reports
whether a check could incur a model call; it never sends an inference request.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..auth import resolve
from ..errors import Diagnostic
from ..stage import StageResult, status_from
from . import config as cfg
from .adapters import auth_check
from .registry import ADAPTERS, resolve_profile


def live_auth_check(profile_id: str, credential_ref: str, profiles_path: Path | None) -> dict[str, Any]:
    prof = resolve_profile(profile_id, cfg.load_user_profiles(profiles_path))
    if prof is None or not prof.get("base_url"):
        return {"ok": False, "performed": False, "may_incur_model_call": False, "diagnostic": f"profile {profile_id} unresolved"}
    try:
        secret = resolve(credential_ref)
    except LookupError as exc:
        return {"ok": False, "performed": False, "may_incur_model_call": False, "diagnostic": str(exc)}
    try:
        return auth_check(prof, secret, 30)
    finally:
        del secret


def run(config_path: Path, live: bool = False, profiles: Path | None = None) -> StageResult:
    res = StageResult("providers", "PASS", "configuration resolves and every used provider has a supported capability set")
    conf = cfg.load(config_path)
    r = cfg.resolve(conf, cfg.load_user_profiles(profiles))
    res.diagnostics.extend(r.diagnostics)
    providers: dict[str, Any] = {}
    for name, prov in conf["providers"].items():
        used = name in r.used_providers
        prof = r.profiles.get(name)
        entry: dict[str, Any] = {"used": used, "adapter": prov["adapter"], "adapter_status": ADAPTERS[prov["adapter"]]["status"],
                                 "api_family": prov["api_family"], "endpoint_profile": prov["endpoint_profile"],
                                 "base_url": prof.get("base_url") if prof else None, "credential_ref": prov["credential_ref"]}
        if used:
            try:
                resolve(prov["credential_ref"])
                entry["credential"] = "resolves"
            except LookupError as exc:
                entry["credential"] = f"unavailable: {exc}"
                res.diagnostics.append(Diagnostic("CONFIGURATION_INVALID", f"provider {name}: credential {prov['credential_ref']} unavailable ({exc})"))
            if live and prof and prof.get("base_url") and entry["credential"] == "resolves":
                entry["live_check"] = live_auth_check(prov["endpoint_profile"], prov["credential_ref"], profiles)
                if entry["live_check"]["ok"] is False:
                    res.diagnostics.append(Diagnostic("PROVIDER_FAILURE", f"provider {name}: {entry['live_check']['diagnostic']}"))
        else:
            entry["credential"] = "not required (provider unused by any role, review slot or fallback)"
        providers[name] = entry
    tiers = [{"id": t["id"], "reviewers": sum(g["count"] for g in t["reviewers"]), "consensus": t["consensus"]["mode"]}
             for t in conf["review"]["review_tiers"]]
    res.summary = {"bridge_tier": conf["bridge_tier"], "endpoint": conf["endpoint"], "roles": conf["roles"],
                   "review_checkpoints": conf["review"]["checkpoints"], "review_tiers": tiers, "providers": providers,
                   "network_requests_made": live}
    res.lines = ["review tiers: " + " -> ".join(f"{t['id']}({t['reviewers']} {t['consensus']})" for t in tiers)]
    res.lines += [f"{n}: {'USED' if e['used'] else 'unused'} {e['adapter']}/{e['api_family']} via {e['endpoint_profile']} — credential {e['credential']}"
                  for n, e in providers.items()]
    res.status = status_from(res.diagnostics)
    return res
