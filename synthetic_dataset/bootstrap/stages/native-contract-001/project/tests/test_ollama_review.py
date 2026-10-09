"""Local tag replacement must invalidate a frozen review identity."""
from types import SimpleNamespace
import unittest

from verislop.errors import UsageError
from verislop.review import _model_matches, model_resolution_manifest


class OllamaReviewIdentityTests(unittest.TestCase):
    def inputs(self, digest=None, fixed=False, local=True):
        identity = {"resolved_model": "qwen:27b"}
        if digest is not None:
            identity["model_digest_sha256"] = digest
        conf = {"agents": {"r": {"provider": "local", "model_identity": identity}},
                "review": {"require_fixed_model_snapshot": fixed}}
        resolved = SimpleNamespace(profiles={"local": {"adapter": "ollama" if local else "openai"}})
        return conf, resolved, {"r": "qwen:27b"}

    def test_same_tag_different_digest_is_rejected(self):
        manifest = model_resolution_manifest(*self.inputs("a" * 64, fixed=True))
        self.assertTrue(_model_matches(manifest, "r", "qwen:27b", "qwen:27b", "a" * 64))
        self.assertFalse(_model_matches(manifest, "r", "qwen:27b", "qwen:27b", "b" * 64))
        self.assertFalse(_model_matches(manifest, "r", "qwen:27b", "qwen:27b"))

    def test_fixed_local_snapshot_requires_digest(self):
        with self.assertRaises(UsageError):
            model_resolution_manifest(*self.inputs(fixed=True))

    def test_cloud_name_pins_keep_existing_behavior(self):
        manifest = model_resolution_manifest(*self.inputs(fixed=True, local=False))
        self.assertNotIn("expected_digest", manifest["models"][0])
        self.assertTrue(_model_matches(manifest, "r", "qwen:27b", "qwen:27b"))
        self.assertFalse(_model_matches(manifest, "r", "qwen:27b", "different"))


if __name__ == "__main__":
    unittest.main()
