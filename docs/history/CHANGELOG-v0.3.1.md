# LoopGrid v0.3.1

## Portable evidence continuity fix

LoopGrid v0.3 uses a workspace-wide append-only hash chain. When a historical decision is replayed after other decisions have been recorded, the replay event can be separated from the original decision events by unrelated ledger events. A per-decision export containing only the target decision events therefore does not contain enough information to prove chain continuity across that gap.

v0.3.1 fixes this by adding `chain-witness.jsonl` to evidence bundles. It contains proof-only bridge nodes for intervening ledger events: sequence number, content hash, previous chain hash, chain hash, signature and key ID. It does not include the other decisions' payloads.

The standalone verifier now merges target events and witness nodes, validates target content hashes, validates all signatures and chain math, verifies sequence completeness and verifies the chain across the exported ledger span.

A regression test covers the exact three-decision demo → replay middle decision → export → offline verify flow.
