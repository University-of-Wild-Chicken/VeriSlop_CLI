"""Independent generic source/ownership checks; no retained model candidates."""
from __future__ import annotations

import copy
import unittest

from verislop import canonical, dsl, native_contract, native_source, python_boundary as pb


ENTRY = {"file": "solution.py", "name": "solve", "arity": 1}


class PythonBoundaryTests(unittest.TestCase):
    def check(self, source, **kwargs):
        return pb.check_sources({"solution.py": source.encode()}, expected_entry=ENTRY, **kwargs)

    def accepted(self, source, **kwargs):
        result = self.check(source, **kwargs)
        self.assertTrue(result["accepted"], result["diagnostics"])
        self.assertFalse(result["facts"]["totality_claimed"])
        return result

    def rejected(self, source, code=None, **kwargs):
        result = self.check(source, **kwargs)
        self.assertFalse(result["accepted"], result)
        self.assertFalse(result["facts"]["input_frame_preserved"])
        if code:
            self.assertEqual(code, result["diagnostics"][0]["code"], result)
        return result

    def test_audited_borrowed_writes_are_concrete_ast_diagnostics(self):
        examples = [
            'def solve(data):\n data["x"] = 1\n return 0\n',
            'def solve(data):\n xs=data["events"]\n xs.append(0)\n return 0\n',
            'def solve(data):\n xs=data["events"]\n xs += [0]\n return 0\n',
            'def solve(data):\n xs=list(data["events"])\n xs[0]["value"] = 7\n return 0\n',
            'def solve(data):\n xs=list(data["events"])\n xs[0] += [0]\n return 0\n',
        ]
        for source in examples:
            with self.subTest(source=source):
                result = self.rejected(source, "BORROWED_WRITE")
                diagnostic = result["diagnostics"][0]
                self.assertEqual("solution.py", diagnostic["file"])
                self.assertTrue(diagnostic["ast_path"].startswith("/body/0/body/"))
                self.assertIsInstance(diagnostic["line"], int)

    def test_duplicate_global_and_python_normalized_alias_are_rejected(self):
        self.rejected('def solve(data): return 0\ndef solve(data): return 1\n', "DUPLICATE_GLOBAL")
        self.rejected('def K(data): return 0\ndef K(data): return 1\ndef solve(data): return 0\n', "DUPLICATE_GLOBAL")

    def test_entry_layout_name_arity_and_extra_policy_fields_are_closed(self):
        for entry in ({"file": "other.py", "name": "solve", "arity": 1},
                      {"file": "solution.py", "name": "other", "arity": 1},
                      {"file": "solution.py", "name": "solve", "arity": 2}):
            result = pb.check_sources({"solution.py": b"def solve(data): return 0\n"}, expected_entry=entry)
            self.assertFalse(result["accepted"])
            self.assertEqual("ENTRY_MISMATCH", result["diagnostics"][0]["code"])
        for entry in ({**ENTRY, "accepted": True}, {**ENTRY, "file": "../solution.py"},
                      {**ENTRY, "arity": True}, {**ENTRY, "name": "K"}):
            result = pb.check_sources({"solution.py": b"def solve(data): return 0\n"}, expected_entry=entry)
            self.assertFalse(result["accepted"])
            self.assertEqual("ENTRY_REQUIREMENT", result["diagnostics"][0]["code"])

    def test_imports_module_effects_and_function_metadata_are_rejected(self):
        for source in ('import os\ndef solve(data): return 0\n',
                       'print("x")\ndef solve(data): return 0\n',
                       'state=[]\ndef solve(data): return state\n',
                       'class Thing: pass\ndef solve(data): return 0\n'):
            self.rejected(source, "MODULE_STATEMENT")
        for source in ('def solve(data=0): return 0\n', 'def solve(data: int): return 0\n',
                       'def solve(data)->int: return 0\n', '@other\ndef solve(data): return 0\n',
                       'def solve(*data): return 0\n', 'def solve(data, *, other): return 0\n'):
            self.rejected(source, "FUNCTION_METADATA")

    def test_closed_calls_and_shadowed_lexical_calls(self):
        for source in ('def solve(data): return print(data)\n',
                       'def solve(data): return open("x")\n',
                       'def solve(data): return sorted(data)\n'):
            self.rejected(source, "UNCLOSED_CALL")
        self.rejected('def solve(data):\n len=data\n return len(data)\n', "SHADOWED_CALL")
        self.rejected('def step(data): return data\ndef solve(data):\n step=data\n return step(data)\n', "SHADOWED_CALL")
        self.rejected('def solve(data):\n x=len(data)\n len=0\n return x\n', "SHADOWED_CALL")
        self.rejected('def len(data): return 0\ndef solve(data): return 0\n', "RESERVED_GLOBAL")
        self.rejected('def solve(data): return data["f"](data)\n', "DYNAMIC_CALL")
        self.rejected('def solve(data): return list(items=data)\n', "DYNAMIC_CALL")

    def test_recursive_and_mutually_recursive_helpers_are_rejected(self):
        self.rejected('def solve(data): return solve(data)\n', "CYCLIC_CALLS")
        self.rejected('def a(data): return b(data)\ndef b(data): return a(data)\ndef solve(data): return a(data)\n', "CYCLIC_CALLS")

    def test_helper_mediated_input_mutation_is_rejected(self):
        self.rejected('def change(xs):\n xs.append(0)\n return 0\ndef solve(data): return change(data)\n', "BORROWED_WRITE")
        self.rejected('def identity(xs): return xs\ndef solve(data):\n xs=identity(data)\n xs.append(0)\n return 0\n', "BORROWED_WRITE")

    def test_external_helper_signature_cannot_hide_mutating_internal_calls(self):
        source = 'def change(n):\n n += [0]\n return n\ndef solve(data): return change(data["xs"])\n'
        self.rejected(source, "BORROWED_WRITE", typed_args={"solution.py:change": ["Int"]})

    def test_branch_alias_and_loop_carry_aliases_remain_borrowed(self):
        self.rejected('def solve(data):\n xs=[]\n if data["flag"]:\n  xs=data["xs"]\n xs.append(0)\n return 0\n', "BORROWED_WRITE")
        self.rejected('def solve(data):\n xs=[]\n for x in data["xs"]:\n  xs=x\n xs.append(0)\n return 0\n', "BORROWED_WRITE")
        self.rejected('def solve(data):\n xs=[]\n for x in data["xs"]:\n  xs.append(0)\n  xs=x\n return 0\n', "BORROWED_WRITE")

    def test_active_iterable_alias_mutations_are_rejected(self):
        for body in ('xs.append(0)', 'alias.append(0)', 'xs[0]=0', 'xs += [0]'):
            source = 'def solve(data):\n xs=[0]\n alias=xs\n for x in xs:\n  ' + body + '\n return 0\n'
            self.rejected(source, "ACTIVE_ITERABLE_WRITE")
        self.rejected('def solve(data):\n xs=[0]\n out=[xs.append(1) for x in xs]\n return 0\n', "ACTIVE_ITERABLE_WRITE")

    def test_shallow_copy_owns_only_root_and_fresh_children_can_be_written(self):
        self.accepted('def solve(data):\n xs=list(data["xs"])\n xs.append(0)\n xs[0]=1\n return xs\n')
        self.accepted('def solve(data):\n child={"value":0}\n xs=[child]\n xs[0]["value"]=1\n return xs\n')
        self.rejected('def solve(data):\n xs=[data["child"]]\n xs[0]["value"]=1\n return 0\n', "BORROWED_WRITE")

    def test_fresh_local_alias_writes_dicts_and_augmented_lists_are_admitted(self):
        self.accepted('def solve(data):\n xs=[]\n alias=xs\n alias.append(1)\n xs += [2]\n out={"xs":xs}\n out["n"]=len(xs)\n return out\n')

    def test_generic_data_composition_helpers_and_comprehensions(self):
        source = '''def increments(xs):
 return [x+1 for x in xs]
def records(xs):
 out=[]
 for x in xs:
  row={"value":x}
  row["extra"]=1
  out.append(row)
 return out
def solve(data):
 xs=increments(data["values"])
 xs.append(0)
 rows=records(xs)
 out=[]
 for row in rows:
  out.append({"value":row["value"]+1})
 return out
'''
        result = self.accepted(source)
        self.assertEqual(["solution.py:increments", "solution.py:records"], result["call_graph"]["solution.py:solve"])

    def test_fresh_helper_return_does_not_clean_borrowed_descendants(self):
        self.rejected('def wrap(xs): return [xs]\ndef solve(data):\n out=wrap(data["xs"])\n out[0][0]=0\n return 0\n', "BORROWED_WRITE")
        self.accepted('def make(xs): return {"items":[]}\ndef solve(data):\n out=make(data)\n out["items"].append(0)\n return out\n')

    def test_typed_records_allow_safe_scalar_augmented_assignment(self):
        profile = {"records": {"Input": {"fields": [{"name": "n", "sort": "Int"}, {"name": "xs", "sort": {"list": "Int"}}]}}}
        source = 'def solve(data):\n n=data["n"]\n n += 1\n out=list(data["xs"])\n out.append(n)\n return out\n'
        self.accepted(source, typed_args={"solution.py:solve": [{"record": "Input"}]}, profile=profile)
        self.rejected(source, "BORROWED_WRITE")

    def test_local_tuples_preserve_element_ownership_when_unpacked(self):
        self.accepted('def pair(data): return ([], 0)\ndef solve(data):\n xs,n=pair(data)\n xs.append(n)\n return xs\n')
        self.rejected('def pair(data): return (data, 0)\ndef solve(data):\n xs,n=pair(data)\n xs.append(n)\n return xs\n', "BORROWED_WRITE")

    def test_non_json_literals_reflection_and_identity_are_rejected(self):
        for expression in ('b"x"', '1j', '1e309'):
            self.rejected('def solve(data): return ' + expression + '\n', "NON_JSON_LITERAL")
        self.rejected('def solve(data): return data.__class__\n', "UNSUPPORTED_EXPRESSION")
        self.rejected('def solve(data): return __builtins__\n', "REFLECTION_NAME")
        self.rejected('def solve(data): return data["a"] is data["b"]\n', "IDENTITY_OBSERVATION")
        self.accepted('def solve(data): return data["a"] is not None\n')

    def test_uncertain_branch_bindings_and_unsupported_loops_are_explicit(self):
        self.rejected('def solve(data):\n if data["flag"]:\n  xs=[]\n xs.append(0)\n return xs\n', "UNCLOSED_NAME")
        self.rejected('def solve(data):\n while data:\n  pass\n return 0\n', "UNSUPPORTED_STATEMENT")
        self.rejected('def solve(data):\n def inner(): return 0\n return 0\n', "UNSUPPORTED_STATEMENT")

    def test_pure_raise_and_assert_do_not_claim_totality(self):
        self.accepted('def solve(data):\n assert data is not None\n if data==0:\n  raise ValueError("zero")\n return 0\n')

    def test_explicit_work_bounds_block_without_claiming_semantic_failure(self):
        self.rejected('def solve(data): return 0\n', "SYNTAX_LIMIT", limits={"nodes": 2})
        self.rejected('def solve(data): return 0\n', "ANALYSIS_LIMIT", limits={"analysis_steps": 1})
        self.rejected('def solve(data):\n out=[]\n for x in data:\n  out.append(x)\n return out\n', "OWNERSHIP_FIXPOINT", limits={"loop_iterations": 1})
        self.rejected('def solve(data): return 0\n', "INVALID_POLICY", limits={"nodes": pb.DEFAULT_LIMITS["nodes"]+1})

    def test_receipt_hash_inventory_and_policy_are_reproducible_and_source_bound(self):
        source = 'def solve(data): return 0\n'
        result = self.accepted(source)
        self.assertEqual(result, self.check(source))
        self.assertEqual(canonical.digest(source.encode()), result["source_inventory"]["solution.py"])
        payload = copy.deepcopy(result); digest = payload.pop("receipt_hash")
        self.assertEqual(digest, canonical.digest_json(payload))
        self.assertNotEqual(result["receipt_hash"], self.accepted('def solve(data): return 1\n')["receipt_hash"])
        self.assertNotEqual(result["receipt_hash"], self.accepted(source, limits={"analysis_steps": 10000})["receipt_hash"])

    def test_safe_source_paths_and_exact_bytes(self):
        for sources in ({"../solution.py": b"def solve(data): return 0\n"},
                        {"solution.py": "def solve(data): return 0\n"},
                        {"a//solution.py": b"def solve(data): return 0\n"},
                        {}):
            result = pb.check_sources(sources, expected_entry=ENTRY)
            self.assertFalse(result["accepted"])

    def test_invalid_noncanonical_metadata_is_a_computed_blocked_receipt(self):
        for kwargs in ({"typed_args": {"solve": [b"not-a-sort"]}},
                       {"profile": {"records": {"bad": float("nan")}}},
                       {"expected_entry": {**ENTRY, "arity": 10**100}}):
            result = pb.check_sources({"solution.py": b"def solve(data): return 0\n"}, **kwargs)
            self.assertFalse(result["accepted"])
            self.assertEqual("TYPE_SHAPE", result["diagnostics"][0]["code"])

    def test_determinism_scope_does_not_claim_raw_dictionary_key_order_invariance(self):
        source = 'def solve(data):\n out=[]\n for key in data:\n  out.append(key)\n return out\n'
        result = self.accepted(source)
        namespace = {}; exec(compile(source, "generic-order-fixture.py", "exec"), namespace)
        left, right = {"a": 1, "b": 2}, {"b": 2, "a": 1}
        self.assertEqual(left, right)
        self.assertNotEqual(namespace["solve"](left), namespace["solve"](right))
        self.assertEqual(namespace["solve"](left), namespace["solve"](left))
        self.assertFalse(result["semantic_domain"]["arbitrary_python_object_or_key_order_invariance"])

    def test_alias_set_and_region_bounds_block_analysis(self):
        source = 'def solve(data): return [' + ','.join('[]' for _ in range(pb.MAX_VALUE_REFS + 1)) + ']\n'
        self.rejected(source, "ANALYSIS_LIMIT")
        self.rejected('def solve(data):\n a=[]\n b=[]\n return 0\n', "ANALYSIS_LIMIT", limits={"regions": 2})


class NativeSourceTests(unittest.TestCase):
    def test_integer_only_facet_catches_dead_float_operations_without_changing_generic_admission(self):
        profile, ir, proposal, packages = self.context()
        for expression in ('data[0] / 1', 'data[0] ** -1', 'data[0] ** data[0]', '0.5',
                           'data[0] ** True', 'data[0] ** False', 'data[0] ** (1-2)', 'data[0] ** (1//2)'):
            source = ('def solve(data):\n ignored = ' + expression + '\n return []\n').encode()
            generic = native_source.check_sources({"solution.py": source}, ir, profile, bindings=proposal, packages=packages)
            self.assertTrue(generic["accepted"], generic)
            self.assertFalse(generic["source_check"]["facts"]["no_floating_point"])
            required = copy.deepcopy(packages)
            required["O1"]["native"][0]["requirements"].append({"tag": "no_floating_point"})
            frozen = copy.deepcopy(ir)
            frozen["obligations"]["O1"]["formal"]["formula_ref"] = "artifact:formula@" + canonical.digest_json(required["O1"])
            checked = native_source.check_sources({"solution.py": source}, frozen, profile, bindings=proposal, packages=required)
            self.assertFalse(checked["accepted"], checked)
            sites = [item for item in checked["obligations"]["O1"]["diagnostics"] if item["code"] == "FLOATING_POINT_OPERATION"]
            self.assertEqual(1, len(sites), sites)
            self.assertEqual("/body/0/body/0/value", sites[0]["ast_path"])
            self.assertFalse(checked["obligations"]["O1"]["facets"][0]["model_facts"]["noFloatingPoint"])

    def test_safe_literal_powers_and_float_literals_have_actual_source_facts(self):
        good = pb.check_sources({"solution.py": b'def solve(data): return data[0] ** 2\n'})
        self.assertTrue(good["accepted"])
        self.assertTrue(good["facts"]["no_floating_point"])
        self.assertEqual([], good["floating_point_sites"])
        bad = pb.check_sources({"solution.py": b'def solve(data): return 0.5\n'})
        self.assertTrue(bad["accepted"])
        self.assertFalse(bad["facts"]["no_floating_point"])
        self.assertEqual("FLOATING_POINT_OPERATION", bad["floating_point_sites"][0]["code"])

    def test_augmented_division_and_unsafe_powers_have_exact_source_sites(self):
        profile, ir, proposal, packages = self.context()
        required = copy.deepcopy(packages)
        required["O1"]["native"][0]["requirements"].append({"tag": "no_floating_point"})
        frozen = copy.deepcopy(ir)
        frozen["obligations"]["O1"]["formal"]["formula_ref"] = "artifact:formula@" + canonical.digest_json(required["O1"])
        for operation in ('/= 1', '**= -1', '**= data[0]', '**= True', '**= (1-2)'):
            source = ('def solve(data):\n x=data[0]\n x ' + operation + '\n return []\n').encode()
            result = native_source.check_sources({"solution.py": source}, frozen, profile,
                                                 bindings=proposal, packages=required)
            self.assertFalse(result["accepted"], result)
            self.assertTrue(result["source_check"]["accepted"], result)
            sites = [item for item in result["obligations"]["O1"]["diagnostics"] if item["code"] == "FLOATING_POINT_OPERATION"]
            self.assertEqual(1, len(sites), sites)
            self.assertEqual("/body/0/body/1", sites[0]["ast_path"])
            self.assertEqual(3, sites[0]["line"])
        for exponent in (0, 2):
            source = ('def solve(data):\n x=data[0]\n x **= ' + str(exponent) + '\n return []\n').encode()
            result = native_source.check_sources({"solution.py": source}, frozen, profile,
                                                 bindings=proposal, packages=required)
            self.assertTrue(result["accepted"], result)
            self.assertTrue(result["source_check"]["facts"]["no_floating_point"])

    def test_safe_literal_powers_cannot_hide_other_float_origin_sites(self):
        profile, ir, proposal, packages = self.context()
        required = copy.deepcopy(packages)
        required["O1"]["native"][0]["requirements"].append({"tag": "no_floating_point"})
        frozen = copy.deepcopy(ir)
        frozen["obligations"]["O1"]["formal"]["formula_ref"] = "artifact:formula@" + canonical.digest_json(required["O1"])
        for origin in ('data[0]/1', '0.5'):
            source = ('def origin(data): return ' + origin + '\ndef solve(data):\n x=origin(data)\n ignored=x**2\n return []\n').encode()
            result = native_source.check_sources({"solution.py": source}, frozen, profile,
                                                 bindings=proposal, packages=required)
            self.assertFalse(result["accepted"], result)
            self.assertTrue(result["source_check"]["accepted"], result)
            self.assertEqual(1, len(result["source_check"]["floating_point_sites"]))

    def integer_check(self, source):
        profile, ir, proposal, packages = self.context()
        packages["O1"]["native"][0]["requirements"].append({"tag": "no_floating_point"})
        ir["obligations"]["O1"]["formal"]["formula_ref"] = "artifact:formula@" + canonical.digest_json(packages["O1"])
        return native_source.check_sources({"solution.py": source.encode()}, ir, profile,
                                          bindings=proposal, packages=packages)

    def test_string_percent_conversion_and_augmented_formatting_fail_native_policy(self):
        for statements, path in (('ignored="%.1f" % data[0]', '/body/0/body/0/value'),
                                 ('fmt="%.1f"\n fmt %= data[0]', '/body/0/body/1')):
            source = 'def solve(data):\n ' + statements + '\n return []\n'
            result = self.integer_check(source)
            self.assertTrue(result["source_check"]["accepted"], result)
            self.assertFalse(result["accepted"], result)
            sites = result["source_check"]["floating_point_sites"]
            self.assertEqual(1, len(sites), sites)
            self.assertEqual(path, sites[0]["ast_path"])
        # This actual rounding/overflow is the reason a string result is not
        # evidence that its internal computation avoided floating point.
        self.assertEqual("9007199254740992.0", "%.1f" % (2**53 + 1))
        with self.assertRaisesRegex(OverflowError, "convert to float"):
            "%.1f" % (10**400)

    def test_typed_integer_modulo_arithmetic_merges_range_sum_and_helper_returns(self):
        examples = [
            'def solve(data):\n ignored=(data[0]*2+1)%7\n return []\n',
            'def solve(data):\n n=1\n if data[0]:\n  n=2\n else:\n  n=True\n ignored=n%7\n return []\n',
            'def solve(data):\n for i in range(len(data)):\n  ignored=(i*2+1)%7\n return []\n',
            'def solve(data):\n values=[i for i in range(len(data))]\n total=sum(values)\n ignored=total%7\n return []\n',
            'def constant(data): return 1\ndef solve(data):\n ignored=constant(data)%7\n return []\n',
            'def choice(data):\n if data:\n  return 1\n else:\n  return True\ndef solve(data):\n ignored=choice(data)%7\n return []\n',
            'def pair(data): return (1,[])\ndef solve(data):\n n,items=pair(data)\n ignored=n%7\n return []\n',
            'def solve(data):\n n=data[0]\n n %= 7\n return []\n',
            'def solve(data):\n row={"n":1}\n if data[0]:\n  row["n"]=2\n ignored=row["n"]%7\n return []\n',
        ]
        for source in examples:
            with self.subTest(source=source):
                result = self.integer_check(source)
                self.assertTrue(result["accepted"], result)
                self.assertTrue(result["source_check"]["facts"]["no_floating_point"])

    def test_unknown_string_and_cross_branch_helper_provenance_never_become_integer(self):
        examples = [
            'def solve(data):\n n=1\n if data[0]:\n  n="%.1f"\n ignored=n%data[0]\n return []\n',
            'def choice(data):\n if data:\n  return 1\n else:\n  return "%.1f"\ndef solve(data):\n ignored=choice(data)%data[0]\n return []\n',
            'def fmt(data): return "%.1f"\ndef solve(data):\n ignored=fmt(data)%data[0]\n return []\n',
            'def identity(data): return data\ndef solve(data):\n ignored=identity(data)%7\n return []\n',
            'def solve(data):\n row={"n":1}\n if data[0]:\n  row["n"]="%.1f"\n ignored=row["n"]%data[0]\n return []\n',
        ]
        for source in examples:
            with self.subTest(source=source):
                result = self.integer_check(source)
                self.assertTrue(result["source_check"]["accepted"], result)
                self.assertFalse(result["accepted"], result)
                self.assertFalse(result["obligations"]["O1"]["facets"][0]["model_facts"]["noFloatingPoint"])

    def test_loop_alias_merges_do_not_duplicate_floating_point_sites(self):
        result = self.integer_check('def solve(data):\n n=1\n for i in data:\n  ignored=n%i\n  n="%.1f"\n return []\n')
        self.assertTrue(result["source_check"]["accepted"], result)
        self.assertFalse(result["accepted"], result)
        self.assertEqual(1, result["source_check"]["floating_point_sites_count"])
        self.assertEqual("/body/0/body/1/body/0/value", result["source_check"]["floating_point_sites"][0]["ast_path"])

    def test_floating_point_diagnostic_limit_cannot_restore_positive_source_fact(self):
        source = ('def solve(data):\n' + '\n'.join(' ignored=data[0]/1' for _ in range(10)) + '\n return []\n').encode()
        result = pb.check_sources({"solution.py": source}, typed_args={"solve": [{"list": "Int"}]}, limits={"diagnostics": 2})
        self.assertTrue(result["accepted"], result)
        self.assertFalse(result["facts"]["no_floating_point"])
        self.assertEqual(10, result["floating_point_sites_count"])
        self.assertEqual(2, len(result["floating_point_sites"]))
        self.assertTrue(result["floating_point_sites_truncated"])

    def context(self, native=True):
        zero = "sha256:" + "0" * 64
        profile = {"dsl": dsl.ENCODING_V2, "profile_id": "generic-boundary-fixture", "records": {},
                   "symbols": {"step": {"lean_decl": "Generic.step", "decl_hash": zero,
                                          "args": [{"list": "Int"}], "result": {"list": "Int"}}},
                   "enums": {}, "predicates": {}}
        requirements = [{"tag": "entry", "file": "solution.py", "qualname": "solve", "arity": 1},
                        {"tag": "pure_json"}, {"tag": "no_external_io"}, {"tag": "input_preserved"},
                        {"tag": "standard_runtime_only"}, {"tag": "deterministic"}]
        facet = {"requirement_id": "source", "definition": "Generic.source", "definition_hash": zero,
                 "symbol": "step", "lean_decl": "Generic.step", "decl_hash": zero,
                 "requirements": requirements, "model_version": native_contract.MODEL_VERSION,
                 "model_source_hash": native_contract.model_source_hash()}
        package = ({"encoding": native_contract.ENCODING, "native": [facet], "value": None}
                   if native else {"encoding": dsl.ENCODING_V2, "formula": {"tag": "true"}})
        ir = {"obligations": {"O1": {"role": "guarantee", "kind": "postcondition", "required": True,
            "formal": {"representation": "contract_facets" if native else "contract_dsl",
                       "formula_ref": "artifact:formula@" + canonical.digest_json(package)}}}}
        proposal = {"bindings": [{"symbol": "step", "object": {"file": "solution.py", "qualname": "solve"}}]}
        return profile, ir, proposal, {"O1": package}

    def run_check(self, source=b"def solve(data): return [x+1 for x in data]\n", **changes):
        profile, ir, proposal, packages = self.context()
        return native_source.check_sources({"solution.py": source}, changes.get("ir", ir),
            changes.get("profile", profile), bindings=changes.get("bindings", proposal), packages=changes.get("packages", packages))

    def test_native_requirements_are_hash_bound_and_have_per_obligation_receipts(self):
        result = self.run_check()
        self.assertTrue(result["accepted"], result)
        self.assertTrue(result["obligations"]["O1"]["accepted"])
        self.assertTrue(result["obligations"]["O1"]["facets"][0]["accepted"])
        payload = copy.deepcopy(result); digest = payload.pop("receipt_hash")
        self.assertEqual(digest, canonical.digest_json(payload))

    def test_binding_proposal_and_link_identity_normalize_to_identical_receipts(self):
        profile, ir, proposal, packages = self.context()
        linked = {"bindings": [{"symbol": "step", "implementation_object": {"file": "solution.py", "qualname": "solve",
                   "source_hash": "sha256:" + "1" * 64, "lineno": 1}, "obligations": ["O1"]}]}
        args = ({"solution.py": b"def solve(data): return [x+1 for x in data]\n"}, ir, profile)
        self.assertEqual(native_source.check_sources(*args, bindings=proposal, packages=packages),
                         native_source.check_sources(*args, bindings=linked, packages=packages))

    def test_source_violation_scopes_exact_rule_and_ast_site_to_required_guarantee(self):
        result = self.run_check(b"def solve(data):\n data.append(0)\n return data\n")
        self.assertFalse(result["accepted"])
        scoped = result["obligations"]["O1"]["diagnostics"][0]
        self.assertEqual("BORROWED_WRITE", scoped["code"])
        self.assertEqual("/body/0/body/0/value", scoped["ast_path"])
        diagnostics = native_source.diagnostics(result)
        self.assertEqual(["O1"], diagnostics[0].obligations)
        self.assertEqual(scoped, diagnostics[0].details["native_source"])

    def test_wrong_required_layout_and_detached_target_binding_block(self):
        profile, ir, proposal, packages = self.context()
        wrong = {"bindings": [{"symbol": "step", "object": {"file": "implementation.py", "qualname": "solve"}}]}
        result = native_source.check_sources({"implementation.py": b"def solve(data): return data\n"}, ir, profile,
                                             bindings=wrong, packages=packages)
        self.assertFalse(result["accepted"])
        self.assertIn("ENTRY_MISMATCH", [d["code"] for d in result["obligations"]["O1"]["diagnostics"]])
        self.assertFalse(self.run_check(bindings={"bindings": []})["accepted"])

    def test_missing_tampered_and_forged_native_packages_are_not_accepted(self):
        profile, ir, proposal, packages = self.context()
        for mutate in (lambda p: p.clear(), lambda p: p["O1"]["native"][0]["requirements"].pop(),
                       lambda p: p["O1"]["native"][0].update(accepted=True)):
            changed = copy.deepcopy(packages); mutate(changed)
            result = self.run_check(packages=changed)
            self.assertFalse(result["accepted"])
            self.assertIn("NATIVE_REQUIREMENT_BINDING", [d["code"] for d in result["diagnostics"]])

    def test_current_native_model_and_endpoint_anchors_must_match(self):
        profile, ir, proposal, packages = self.context()
        for field in ("decl_hash", "model_source_hash", "model_version"):
            changed = copy.deepcopy(packages)
            changed["O1"]["native"][0][field] = "changed"
            rebound = copy.deepcopy(ir)
            rebound["obligations"]["O1"]["formal"]["formula_ref"] = "artifact:formula@" + canonical.digest_json(changed["O1"])
            result = self.run_check(ir=rebound, packages=changed)
            self.assertFalse(result["accepted"])

    def test_generic_v2_is_checked_and_legacy_v1_is_unchanged(self):
        profile, ir, proposal, packages = self.context(native=False)
        source = {"solution.py": b"def solve(data):\n data.append(0)\n return data\n"}
        result = native_source.check_sources(source, ir, profile, bindings=proposal, packages=packages)
        self.assertFalse(result["accepted"])
        self.assertTrue(result["enabled"])
        self.assertFalse(result["obligations"]["O1"]["accepted"])
        profile.pop("dsl")
        legacy = native_source.check_sources(source, ir, profile, bindings=proposal, packages=packages)
        self.assertEqual({"format": native_source.FORMAT, "enabled": False, "accepted": True,
                          "obligations": {}, "diagnostics": []}, legacy)


if __name__ == "__main__":
    unittest.main()
