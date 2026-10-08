# Stopped native Qwen experiment

**USER_STOPPED; incomplete. No completed 100-task result is claimed.**

42 completed task pairs and 85 completed arm records are retained. The completed D12 raw arm remains individually recorded; D12 CLI was interrupted and receives no invented score.

- raw: 35/43 successful recorded tasks; 349/399 hidden cases; 76/86 public cases; 43 artifacts; 43 calls.
- verislop: 0/42 successful recorded tasks; 0/389 hidden cases; 0/84 public cases; 0 artifacts; 317 calls.

Completed pairs: raw only 34, CLI only 0, both 0, neither 8. No historical experiment is pooled with these observations.

Every original completed score, case observation, response and source snapshot is preserved. The final model-catalog digest check was not run after explicit stop; `valid` remains null. Captured source hashes agree with the protocol; the current runtime also matched when STOP_SOURCE_AUDIT.json was recorded before repairs.

The partial evidence manifest seals stopped bytes. It establishes capture integrity, not experiment completion or correctness.
