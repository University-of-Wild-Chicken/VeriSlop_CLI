"""Actual kernel-normalized inhabitation witnesses for the new typed data domain."""
import tempfile
import unittest
from pathlib import Path

from verislop import accept, canonical, contract, dsl, leanbridge, policy, reify
from verislop.exprjson import parse_name


SOURCE = '''import Std
namespace DataWitness
structure Input where
  values : List Int
  minimum : Int
  text : String
theorem inhabited : ∃ i : Input, i.minimum < 0 :=
  ⟨{values := [-1, 2, -1], minimum := -2, text := "é🙂"}, by decide⟩
theorem large_signed : ∃ x : Int, x < 0 :=
  ⟨-340282366920938463463374607431768211456, by decide⟩
theorem unicode : ∃ text : String, text = "é🙂" := ⟨"é🙂", rfl⟩
end DataWitness
'''


class DataWitnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.toolchain = leanbridge.resolve_toolchain()
        compiled = leanbridge.compile_module(cls.toolchain, SOURCE.encode(), Path(cls.directory.name) / "witness")
        if not compiled.ok:
            raise AssertionError(compiled.errors)
        names = ["DataWitness." + name for name in ("inhabited", "large_signed", "unicode")]
        exported = leanbridge.run_kernel_tool(cls.toolchain, compiled.olean,
                                              {"export": True, "axioms": True, "witnesses": [parse_name(n) for n in names]})
        env = contract.Env.from_export(exported, policy.get("strict"), "witness regression")
        if env.diagnostics:
            raise AssertionError(env.diagnostics)
        raw, _ = reify.derive_profile("witness-data.v0_2", env.decls, env.hashes, set(names))
        cls.profile = dsl.Profile.from_json(raw)
        cls.values = {}
        witnesses = {".".join(row["theorem"]): row for row in exported["witnesses"]}
        for name in names:
            formula, why, _ = reify.reify_formula(env.decls[name]["type"], cls.profile, env.decls)
            if formula is None:
                raise AssertionError(why)
            result = witnesses[name]
            if not result["ok"]:
                raise AssertionError(result)
            cls.values[name] = accept.match_witnesses(formula, result["shape"], cls.profile)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_nested_record_and_ordered_signed_list_witness_are_decoded(self):
        self.assertEqual(self.values["DataWitness.inhabited"], [[dsl.record_v("Input", [(-1, 2, -1), -2, "é🙂"])]])

    def test_unicode_witness_retains_scalar_text_without_normalization(self):
        self.assertEqual(self.values["DataWitness.unicode"], [["é🙂"]])

    def test_large_signed_witness_receipt_is_canonical_without_unsafe_json_integer(self):
        value = self.values["DataWitness.large_signed"][0][0]
        self.assertEqual(value, -(2**128))
        self.assertEqual(canonical.loads(canonical.dumps(accept._jsonable(value, numeric_strings=True))), {"int": str(-(2**128))})


if __name__ == "__main__":
    unittest.main()
