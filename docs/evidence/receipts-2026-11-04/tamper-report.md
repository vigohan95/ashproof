# Receipt tamper detection

A real receipt (status `verified`, 26 events, both sandboxes in gVisor in WSL, scripted models, no cloud VM) attacked in copies. Each copy was checked by `brz/audit/offline_verify.py` run as `python -I -S`, so nothing but the standard library was loaded.

| Tamper | Verifier said | Exit | Reason |
|---|---|---|---|
| control: untouched receipt | OK | 0 | - |
| flip one byte in a step hash | TAMPERED | 1 | step s1: stdout_sha256 does not match the chain |
| delete a step from the chain | TAMPERED | 1 | event 10: sequence gap, found seq 11 |
| delete a step from the table, reseal receipt_sha256 | TAMPERED | 1 | steps table ['s1'] does not match the chain ['s1', 's2'] |
| reorder steps in the chain | TAMPERED | 1 | event 9: sequence gap, found seq 10 |
| reorder steps in the table, reseal receipt_sha256 | TAMPERED | 1 | steps table ['s2', 's1'] does not match the chain ['s1', 's2'] |
| change an exit code in the table, reseal receipt_sha256 | TAMPERED | 1 | step s1: exit_code does not match the chain |
| full rewrite of chain and receipt, no pin | OK | 0 | - |
| full rewrite of chain and receipt, head pinned | TAMPERED | 1 | head hash differs from the pinned value 4009b3fa1f87c30e8b07fe98db696225e3a7d27b045e6d86943a4039b211ce3c |

Sweep: every one of the 23632 bytes of the file was flipped in turn (XOR 0x01). 1 flips went undetected, and 0 of those changed any parsed value. An undetected flip that changes no value is a last digit of a long float that rounds to the same double: the hashes cover values, not the file's bytes. Undetected contexts: `['sd": 0.018033999999999998,\n ']`.

The one row that says OK after an edit is deliberate: a hash chain has no key, so a forger who recomputes every hash produces a consistent file. Only a head hash kept elsewhere exposes that, which is what the next row shows, and the tool prints a warning whenever no pin is given.

Reproduce: `python brz/audit/offline_verify.py docs/evidence/receipts-2026-11-04/receipt.json`
