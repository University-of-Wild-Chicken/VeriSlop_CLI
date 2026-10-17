"""Release display projection checks; no model calls or generated success trials."""
from copy import deepcopy
import unittest

from verislop import canonical, review_prompt


class LegacyReviewPromptTests(unittest.TestCase):
    def packet(self):
        backend = {"target": "vscore", "backend_version": "0.3",
                   "id": "verislop.backend.vscore/0.3", "endpoint": "restricted_source"}
        claim = {"claim_id": "END_TO_END_VERIFIED:O1", "required": True,
                 "premises": ["LINKED:O1"], "outcome": "PASS"}
        outputs = {"module_parts": {"Example": {"ast": "exact" * 300}},
                   "literal": {"execution_inventory": "must remain in full packet"}}
        return {
            "checkpoint": "release", "request": "Unicode scalar é e\u0301 🙂\x00\n",
            "scope": ["O1", "CLOSURE:determinism"], "obligations": {"O1": claim},
            "lean_accepted_source": "theorem accepted : True := by trivial\n",
            "implementation": {"program.vscore.json": '{"source":"exact"}',
                               "Proof.lean": "-- delivered proof\n"},
            "vscore": {"selection": {"backend": backend}, "source": "exact source",
                       "goal": "exact goal", "certificate": {"bound": "exact certificate"}},
            "mechanical_snapshot": {
                "backend": deepcopy(backend), "mechanical_status": "BLOCKED",
                "claims": [claim], "provenance": [{"claim_id": claim["claim_id"]}],
                "diagnostics": [{"message": "retained failure"}],
                "execution_inventory": [{"path": f"evidence/{i}", "sha256": "sha256:" + "1" * 64}
                                        for i in range(30)],
                "builds": [{"build": "A", "ok": True, "errors": [], "outputs": outputs},
                           {"build": "B", "ok": False, "errors": ["concrete failure"],
                            "outputs": deepcopy(outputs)}],
                "determinism": {"mismatches": ["module_parts"]},
            },
            "counterexample_policy": {"supported": ["mechanical_replay"],
                                      "scope": ["O1", "CLOSURE:determinism"]},
            "required_mechanical_claims": [deepcopy(claim)],
            "checked_link_inventory": {"bindings": ["exact binding"]},
            "excluded_surfaces": ["host execution"],
        }

    def references(self, view):
        snapshot = view["packet"]["mechanical_snapshot"]
        return [snapshot["execution_inventory"], *(build["outputs"] for build in snapshot["builds"])]

    def test_roundtrip_is_exact_detached_and_does_not_mutate_packet(self):
        packet = self.packet()
        before = canonical.dumps(packet)
        view = review_prompt._project_legacy(packet)
        restored = review_prompt.restore_packet(view, packet)
        self.assertEqual(before, canonical.dumps(packet))
        self.assertEqual(before, canonical.dumps(restored))
        self.assertEqual(canonical.digest(before), view["packet_sha256"])
        self.assertEqual(len(before), view["packet_utf8_bytes"])
        self.assertLess(len(canonical.dumps(view)), len(before))
        restored["scope"].append("unrelated restored mutation")
        view["packet"]["counterexample_policy"]["scope"].clear()
        self.assertEqual(before, canonical.dumps(packet))

    def test_every_replaced_path_has_exact_closed_reference_and_all_else_is_unchanged(self):
        packet = self.packet()
        view = review_prompt._project_legacy(packet)
        reconstructed = deepcopy(view["packet"])
        for index, ref in enumerate(self.references(view)):
            if index == 0:
                pointer = "/mechanical_snapshot/execution_inventory"
                value = packet["mechanical_snapshot"]["execution_inventory"]
                reconstructed["mechanical_snapshot"]["execution_inventory"] = value
            else:
                pointer = f"/mechanical_snapshot/builds/{index - 1}/outputs"
                value = packet["mechanical_snapshot"]["builds"][index - 1]["outputs"]
                reconstructed["mechanical_snapshot"]["builds"][index - 1]["outputs"] = value
            self.assertEqual({"format": review_prompt.REFERENCE_FORMAT, "packet_ref": "packet.json",
                              "pointer": pointer, "sha256": canonical.digest_json(value),
                              "utf8_bytes": len(canonical.dumps(value))}, ref)
        self.assertEqual(canonical.dumps(packet), canonical.dumps(reconstructed))
        self.assertEqual(packet["scope"], view["packet"]["scope"])
        self.assertEqual(packet["counterexample_policy"], view["packet"]["counterexample_policy"])
        self.assertFalse(view["packet"]["mechanical_snapshot"]["builds"][1]["ok"])
        self.assertEqual(["concrete failure"], view["packet"]["mechanical_snapshot"]["builds"][1]["errors"])

    def test_literal_references_and_similarly_named_keys_are_not_interpreted(self):
        packet = self.packet()
        literal = {"format": review_prompt.REFERENCE_FORMAT, "packet_ref": "/other/path",
                   "pointer": "/mechanical_snapshot/builds/0/outputs", "sha256": "literal", "utf8_bytes": 0}
        packet["outputs"] = literal
        packet["execution_inventory"] = [literal]
        packet["vscore"]["outputs"] = {"mechanical_snapshot": {"execution_inventory": literal}}
        packet["mechanical_snapshot"]["builds"][0]["nested"] = {"outputs": literal}
        view = review_prompt._project_legacy(packet)
        for key in ("outputs", "execution_inventory", "vscore"):
            self.assertEqual(packet[key], view["packet"][key])
        self.assertEqual(packet, review_prompt.restore_packet(view, packet))

    def test_view_envelope_missing_unknown_or_mutated_fields_are_rejected(self):
        packet = self.packet()
        view = review_prompt._project_legacy(packet)
        for key in view:
            missing = deepcopy(view); missing.pop(key)
            changed = deepcopy(view); changed[key] = "changed"
            for invalid in (missing, changed):
                with self.subTest(key=key, value=invalid.get(key)), self.assertRaises(ValueError):
                    review_prompt.restore_packet(invalid, packet)
        with self.assertRaises(ValueError):
            review_prompt.restore_packet({**view, "extra": "unknown"}, packet)

    def test_all_reference_fields_and_all_omitted_paths_are_bound(self):
        packet = self.packet()
        original = review_prompt._project_legacy(packet)
        for index, ref in enumerate(self.references(original)):
            for key in ref:
                for mutation in ("missing", "changed"):
                    view = deepcopy(original)
                    changed = self.references(view)[index]
                    if mutation == "missing":
                        changed.pop(key)
                    else:
                        changed[key] = "changed"
                    with self.subTest(index=index, key=key, mutation=mutation), self.assertRaises(ValueError):
                        review_prompt.restore_packet(view, packet)
            view = deepcopy(original)
            self.references(view)[index]["extra"] = True
            with self.subTest(index=index, mutation="extra"), self.assertRaises(ValueError):
                review_prompt.restore_packet(view, packet)

    def test_unknown_missing_mutated_and_type_changed_visible_packet_fields_fail(self):
        packet = self.packet()
        changes = [lambda p: p.update(extra=True), lambda p: p.pop("scope"),
                   lambda p: p["scope"].clear(), lambda p: p["vscore"].update(source="changed"),
                   lambda p: p["counterexample_policy"].update(scope=[]),
                   lambda p: p["mechanical_snapshot"]["builds"].pop(),
                   lambda p: p["mechanical_snapshot"]["builds"][0].update(ok=1),
                   lambda p: p["mechanical_snapshot"]["builds"][1].update(errors=[])]
        for mutate in changes:
            view = review_prompt._project_legacy(packet)
            mutate(view["packet"])
            with self.assertRaises(ValueError):
                review_prompt.restore_packet(view, packet)

    def test_changed_full_packet_is_rejected_even_with_refreshed_outer_digest(self):
        original = self.packet()
        mutations = [lambda p: p.update(request="changed"),
                     lambda p: p["mechanical_snapshot"]["execution_inventory"].clear(),
                     lambda p: p["mechanical_snapshot"]["builds"][0].update(outputs={}),
                     lambda p: p["mechanical_snapshot"]["builds"][1].update(outputs={})]
        for mutate in mutations:
            packet = deepcopy(original)
            mutate(packet)
            view = review_prompt._project_legacy(original)
            with self.assertRaises(ValueError):
                review_prompt.restore_packet(view, packet)
            view["packet_sha256"] = canonical.digest_json(packet)
            view["packet_utf8_bytes"] = len(canonical.dumps(packet))
            with self.assertRaises(ValueError):
                review_prompt.restore_packet(view, packet)

    def test_projection_is_deterministic_and_keeps_array_order(self):
        packet = self.packet()
        reordered = {key: packet[key] for key in reversed(packet)}
        first = review_prompt._project_legacy(packet)
        self.assertEqual(canonical.dumps(first), canonical.dumps(review_prompt._project_legacy(reordered)))
        self.assertEqual(["A", "B"], [b["build"] for b in first["packet"]["mechanical_snapshot"]["builds"]])

    def test_no_builds_is_displayed_without_inventing_success_or_references(self):
        packet = self.packet()
        packet["mechanical_snapshot"]["builds"] = []
        view = review_prompt._project_legacy(packet)
        self.assertEqual(1, len(self.references(view)))
        self.assertEqual("BLOCKED", view["packet"]["mechanical_snapshot"]["mechanical_status"])
        self.assertEqual(packet, review_prompt.restore_packet(view, packet))

    def test_earlier_checkpoints_and_other_backend_bindings_are_rejected(self):
        for checkpoint in ("interpretation", "formal_contract", "implementation", None):
            packet = self.packet(); packet["checkpoint"] = checkpoint
            with self.subTest(checkpoint=checkpoint), self.assertRaises(ValueError):
                review_prompt._project_legacy(packet)
        for path in ("selection", "snapshot"):
            for key, value in (("backend_version", "0.1"), ("backend_version", "0.2"),
                               ("backend_version", None), ("target", "python"),
                               ("id", "verislop.backend.vscore/0.1"), ("id", None)):
                packet = self.packet()
                backend = (packet["vscore"]["selection"]["backend"] if path == "selection"
                           else packet["mechanical_snapshot"]["backend"])
                backend[key] = value
                with self.subTest(path=path, key=key, value=value), self.assertRaises(ValueError):
                    review_prompt._project_legacy(packet)

    def test_malformed_mechanical_containers_and_double_projection_are_rejected(self):
        changes = [lambda p: p.pop("vscore"), lambda p: p.update(vscore=[]),
                   lambda p: p["vscore"].update(selection=[]),
                   lambda p: p.pop("mechanical_snapshot"),
                   lambda p: p["mechanical_snapshot"].pop("execution_inventory"),
                   lambda p: p["mechanical_snapshot"].update(execution_inventory={}),
                   lambda p: p["mechanical_snapshot"].update(builds={}),
                   lambda p: p["mechanical_snapshot"]["builds"].append(None),
                   lambda p: p["mechanical_snapshot"]["builds"][0].pop("outputs")]
        for mutate in changes:
            packet = self.packet(); mutate(packet)
            with self.assertRaises(ValueError):
                review_prompt._project_legacy(packet)
        view = review_prompt._project_legacy(self.packet())
        with self.assertRaises(ValueError):
            review_prompt._project_legacy(view["packet"])

    def test_view_explicitly_disclaims_authority_and_inspection_of_omitted_details(self):
        view = review_prompt._project_legacy(self.packet())
        self.assertIn("no proof, acceptance, milestone or release authority", view["authority"])
        self.assertIn("must not claim to have inspected referenced detail", view["omitted_detail"])
        self.assertIn("independently replayed probes", view["omitted_detail"])


if __name__ == "__main__":
    unittest.main()
