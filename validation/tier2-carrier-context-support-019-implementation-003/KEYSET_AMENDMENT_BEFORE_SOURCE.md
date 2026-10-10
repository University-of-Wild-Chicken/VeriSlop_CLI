# Exact key-set amendment before source repair

Root supplied the concrete generic counterexample `Object.keys({"a,b":0}).sort().join(",") === ["a","b"].sort().join(",")`. Thus the new checkpointKeys helper's comma-joined comparison is not an exact key-set predicate, even though later guards may reject particular output records. No task data or hidden author trace is involved.

Replace only the new checkpointKeys helper with sorted-array length and element equality, and add this exact negative control plus a valid exact-set positive control. Original legacy reader/VIEW APIs remain byte-exact; their downstream Python closed-view checks are not altered here. Rebuild unsealed candidate003 and update its collector source binding. All prior candidate checkpoint, strict Unicode and SHA-256 source checks must remain valid. No production or frozen qualification is modified.
