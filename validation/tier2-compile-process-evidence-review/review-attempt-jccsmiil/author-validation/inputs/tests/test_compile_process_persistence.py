"""Durability at actual authoring/CLI consumers, with generic preview fixtures."""
from pathlib import Path
from types import SimpleNamespace
import json
import tempfile
import unittest
from unittest.mock import patch

from verislop import agents, canonical, cli
from verislop.bridges import vscore3_checker as checker
from verislop.events import EventSink
from verislop.package import Package
from verislop.targets import vscore3_source as source, vscore3_target as target


class CompileProcessPersistenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="verislop-process-consumers-")
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.pkg = Package(self.root / "run")
        self.pkg.ensure("generic-process-consumers")
        self.source = source.compile_surface(
            'program "vscore/0.3" profile "data-pipeline/0.3"; entry echo(x:Bool)->Bool{x}')
        self.relation = {"schema_version": "0.3", "format": target.RELATION_FORMAT,
                         "template": target.TEMPLATE, "source_slot": "vscore-source",
                         "proof_slot": "vscore-proof", "bindings": [{"symbol": "echo", "entry": "echo"}]}
        self.spec = SimpleNamespace(text="generic fixture goal", refinement_symbols={"echo"})
        self.inventory = {"Generic.Process": {"availability": "available", "record": {
            "format": "verislop.lean-compile-process/1", "stdout": {"content_b64": "Zml4dHVyZQ=="}}}}
        self.info = {"proposition_hash": "sha256:" + "a" * 64, "model": b"{}", "profile": b"{}",
                     "compile_process_evidence": self.inventory, "proof_checked": False, "edge_axioms": []}

    def test_agent_check_artifact_retains_exact_preview_inventory(self):
        params = {"tier": 2, "target": "vscore", "endpoint": "restricted_source",
                  "backend": "verislop.backend.vscore/0.3", "backend_version": "0.3"}
        fixed = {"parameters": params, "accepted_reference": {}, "accepted_packages": {},
                 "accepted_profile": {}, "lean_toolchain": "synthetic-pin"}
        proposal = json.dumps({"program": canonical.loads(self.source), "relation": self.relation,
                               "proof_source": "generic fixture proof"})
        events = EventSink(self.pkg.run_id, quiet=True)
        self.addCleanup(events.close)
        with patch.object(agents, "_vscore_context", return_value=fixed), \
             patch.object(agents, "_role", return_value="fixture-role"), \
             patch.object(agents, "recorded_call", return_value=SimpleNamespace(text=proposal)), \
             patch.object(checker, "preview", return_value=(self.spec, None, self.info)):
            agents._vscore_implementation(None, {"roles": {}}, self.pkg, events, {"parameters": params}, 1, 0)
        checks = self.pkg.root / "agents/vscore-attempts/source-1/checks"
        for label in ("source", "initial-proof"):
            record = canonical.load_file(checks / (label + ".json"))
            self.assertEqual(record["compile_process_evidence"], self.inventory)
            self.assertTrue(record["passed"])
            self.assertEqual(record["source_hash"], canonical.digest(self.source))

    def test_cli_retains_bytes_and_returns_advisory_digest_reference(self):
        src = self.root / "program.json"
        rel = self.root / "relation.json"
        src.write_bytes(self.source)
        rel.write_bytes(canonical.dumps(self.relation))
        out = self.root / "goal"
        args = SimpleNamespace(source=str(src), vscore_action="goal", package=str(self.pkg.root),
                               relation=str(rel), proof=None, bridge_id=None, obligation=[], out=str(out))
        with patch.object(checker, "preview", return_value=(self.spec, None, self.info)):
            result = cli.cmd_vscore(args)
        self.assertEqual(result.status, "PASS")
        data = (out / "compile-process-evidence.json").read_bytes()
        self.assertEqual(canonical.loads(data), self.inventory)
        self.assertEqual(result.summary["compile_process_evidence"], {
            "path": str(out / "compile-process-evidence.json"), "sha256": canonical.digest(data),
            "authoritative": False})
        self.assertNotIn("content_b64", json.dumps(result.to_json()))


if __name__ == "__main__":
    unittest.main()
