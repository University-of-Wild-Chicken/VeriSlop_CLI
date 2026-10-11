"""Pure candidate profile/inventory metadata derivation from authenticated bytes."""
import copy


def build_profile(helper, legacy_source, legacy_profile, references, source_bytes, code,
                  reconstruction_source, *, marker_pattern, expected_markers):
    """No generator import or precomputed message is an input/output."""
    helper.require(type(marker_pattern) is str and type(expected_markers) is list and
                   len(expected_markers) == 4 and all(type(v) is str for v in expected_markers),
                   "FRESH_MARKER_REGISTRATION_REQUIRED")
    profile = copy.deepcopy(legacy_profile)
    profile["author_protocol"]["reconstruction_source"] = dict(reconstruction_source)
    profile["marker_pattern"] = marker_pattern
    profile["expected_markers"] = list(expected_markers)
    profile["compact_protocol"] = {"format": helper.COMPACT_SCHEMA,
        "sources": copy.deepcopy(references), "code": dict(code),
        "source_schema": helper.PureTemplateAST(source_bytes["generator"]).schema()}
    helper.validate_literals(legacy_source, profile, source_bytes)
    return profile


def inventory_registration(base, descriptor, registration_path, integration_path):
    """Static independent exact path list; no producer inventory call."""
    result = copy.deepcopy(base)
    paths = list(base["transport_files"])
    paths += [registration_path, integration_path]
    paths += [ref["path"] for ref in descriptor["source_files"].values()]
    result["transport_files"] = sorted(set(paths))
    result["runtime_dependency_registration"] = {
        "format": descriptor["format"], "api_revision": descriptor["api_revision"],
        "registration_path": registration_path, "embedded_launcher": descriptor["launcher"],
        "external_interpreters": copy.deepcopy(descriptor["interpreters"]),
        "session_files_in_source_inventory": False}
    result["mode"] = "CANDIDATE_SOURCE_PREPARATION_ONLY"
    result["qualification_source_root"] = None
    return result
