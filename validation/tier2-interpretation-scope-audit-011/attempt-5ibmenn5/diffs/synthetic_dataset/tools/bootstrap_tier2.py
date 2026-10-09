--- frozen010/synthetic_dataset/tools/bootstrap_tier2.py
+++ current/synthetic_dataset/tools/bootstrap_tier2.py
@@ -430,38 +430,49 @@
                          "delivery_revised": any(s["delivery_revised"] for s in row["source_mappings"])} for row in mapping]
     revision_note = ("\n\nExplicit delivery revision and requirement identity metadata:\n"
         "This is a new canonical restricted-source delivery request. The functional clauses, stated domains and "
-        "public example values above retain their original meaning. Preserve these requirement IDs, roles and "
-        "required flags in the interpretation. IDs mapped across a delivery revision now state the specified "
-        "typed pure source properties; their previous delivery assurance is unchanged. Each functional guarantee "
-        "requires its complete mathematical statement and universal implementation refinement; illustrative "
-        "examples do not replace it. The clause offsets below refer to the revised text above.\n" +
-        canonical.dumps(request_metadata).decode() +
-        "\nRequested endpoint: Tier 2 / restricted_source, backend vscore/0.3, END_TO_END_VERIFIED. "
-        "Runtime campaigns are not requested. This request claims normative restricted-source execution only, "
-        "with natural-language correspondence, host tooling, the pinned Lean kernel, hashing and OS/hardware "
-        "explicitly trusted. No machine-code, compiler, runtime or physical-resource assurance is claimed.\n")
+        "public example values above retain their original meaning. IDs mapped across a delivery revision now "
+        "state the specified typed pure source properties; their previous delivery assurance is unchanged. "
+        "Each functional guarantee requires its complete mathematical statement and universal implementation "
+        "refinement; illustrative examples do not replace it. The clause offsets below refer to the revised "
+        "text above.\n" + canonical.dumps(request_metadata).decode() + "\n")
     required_source = source_policy(identities, operational_ids=operational_ids)
     classification = {"value_required_default": True, "source_only_operational_ids": sorted(operational_ids)}
     policy_note = ("\nMandatory requested source-facet specification:\n"
-        "This is a frozen request constraint, not accepted obligation IR or proof evidence. Every listed original "
-        "required guarantee retains the globally requested source delivery: canonical file program.vscore.json, "
-        "one typed entry solve of arity 1, and all seven closed source properties below. Include the exact source "
-        "requirements in its formal contract; a mathematical result-existence or equality theorem cannot replace "
+        "Every listed original required guarantee retains the globally requested source delivery: canonical file "
+        "program.vscore.json, one typed entry solve of arity 1, and all seven closed source properties below. "
+        "A mathematical result-existence or equality theorem cannot replace "
         "entry identity, purity, input preservation, effect restrictions or exact non-floating-point semantics. "
-        "For every value_required=true row also preserve the complete functional formula and universal source "
-        "implementation refinement as a mixed source/value guarantee, including functional safety properties and "
+        "For every value_required=true row the source must implement the complete functional formula with "
+        "universal source implementation refinement, including functional safety properties and "
         "invariants. Value facets are required by default regardless of category. Only the explicitly classified "
         "operational IDs below are source-only, retaining their source requirements rather than being replaced "
         "by value equalities. Assumptions, exclusions and "
-        "separate non-vacuity witnesses are not source-policy rows. These constraints will be independently "
-        "checked against kernel-reconstructed contract facets before proof, after acceptance and at closure.\n" +
+        "separate non-vacuity witnesses are not source-policy rows.\n" +
         canonical.dumps(classification).decode() + "\n" + canonical.dumps(required_source).decode() + "\n")
+    # Instructions about the supervisor's run are preregistered input context,
+    # separate from the software request and its requirement citation manifest.
+    workflow_text = ("Supervisor workflow context for this verification run:\n"
+        "Preserve these requirement IDs, roles and required flags in the interpretation.\n"
+        "This is a frozen request constraint, not accepted obligation IR or proof evidence. "
+        "Include the exact source requirements in its formal contract. For every value_required=true row "
+        "preserve the complete functional formula and universal source implementation refinement as a mixed "
+        "source/value guarantee. These constraints will be independently checked against kernel-reconstructed "
+        "contract facets before proof, after acceptance and at closure.\n"
+        "Requested endpoint: Tier 2 / restricted_source, backend vscore/0.3, END_TO_END_VERIFIED. "
+        "Runtime campaigns are not requested. This request claims normative restricted-source execution only, "
+        "with natural-language correspondence, host tooling, the pinned Lean kernel, hashing and OS/hardware "
+        "explicitly trusted. No machine-code, compiler, runtime or physical-resource assurance is claimed.\n"
+        "This context describes requirements of the run and does not establish their satisfaction.\n")
+    workflow_bytes = workflow_text.encode("utf-8")
+    workflow_context = {"encoding": "utf-8", "text": workflow_text,
+                        "byte_length": len(workflow_bytes), "sha256": canonical.digest(workflow_bytes)}
     final = revised + revision_note.encode() + policy_note.encode()
     return final, {"format": "verislop.delivery-revision/0.1", "original_request_sha256": canonical.digest(original),
                    "revised_request_sha256": canonical.digest(final), "edits": edits, "segments": segments,
                    "identity_mapping": mapping, "public_examples_sha256": canonical.digest(example_data[1]),
                    "source_policy_format": SOURCE_POLICY_FORMAT, "source_policy_sha256": canonical.digest_json(required_source),
                    "source_policy_classification": classification,
+                   "workflow_context": workflow_context,
                    "functional_bytes_preserved": True, "old_delivery_assurance_relabelled": False}
 
 
@@ -599,11 +610,15 @@
                                           operational_ids=SOURCE_ONLY_OPERATIONAL_IDS[task["id"]])
         required_source = source_policy(metadata["identities"], operational_ids=SOURCE_ONLY_OPERATIONAL_IDS[task["id"]])
         policy_path = "requests/" + task["id"] + "/source-policy.json"
+        revision_path = "requests/" + task["id"] + "/delivery-revision.json"
         if (task.get("source_policy_classification") != revision["source_policy_classification"]
                 or task.get("source_policy_path") != policy_path
                 or task.get("source_policy_sha256") != canonical.digest_json(required_source)
                 or protocol["input_files"].get(policy_path) != canonical.digest_json(required_source)
                 or _regular(cohort / policy_path) != canonical.dumps(required_source)
+                or task.get("revision_path") != revision_path
+                or protocol["input_files"].get(revision_path) != canonical.digest_json(revision)
+                or _regular(cohort / revision_path) != canonical.dumps(revision)
                 or revised != _regular(cohort / task["revised_prompt_path"])
                 or revision != load(cohort / task["revision_path"])
                 or task["original_request_sha256"] != canonical.digest(original)
