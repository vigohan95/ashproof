# After the rebuild, 2026-11-11

The control plane was recreated on 2026-11-11 (see the main README). These three tasks were then run through the
public URL, in this order, with `scripts/live_task.py`. They are lines 0 to 2 of the new public log and the recordings
the demo plays.

| File | Task id | Result |
|---|---|---|
| `csv.receipt.*` | `4295c1eeb105` | verified in 101.4 s; second VM produced identical output hashes; both VMs 404; $0.0195 |
| `refused.receipt.*` | `9748d809548f` | refused by the planner in 2.5 s; no VM created; $0.0009 |
| `compromised-agent.receipt.*` | `78b6cc1245e5` | failed in 116.5 s; 20 of 20 packets refused by the kernel; both VMs 404; $0.0190 |

`anchors-checkpoint.jsonl` is the public log as fetched after the third task (3 lines).

```bash
python brz/audit/offline_verify.py docs/evidence/vultr-2026-11-11/compromised-agent.receipt.json \
    --require-signature --anchors docs/evidence/vultr-2026-11-11/anchors-checkpoint.jsonl
```

prints `signature: valid, made with the published key` and `public log: found at line 2`.
