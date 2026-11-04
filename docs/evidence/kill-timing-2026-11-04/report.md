# Kill switch timing under gVisor

30 runs on runsc version release-20261026.0, platform systrap, WSL2 kernel 6.18.54.1-microsoft-standard-WSL2, 2026-11-04T12:34:55Z. Hostile step: 5 processes ignoring SIGTERM, four of them spinning on the CPU.

T0 is immediately before `POST /revoke` is sent with a signed token. All figures in milliseconds.

| Measure | min | p50 | p95 | max | mean |
|---|---|---|---|---|---|
| Kill to every host process of the sandbox gone | 10.72 | 13.23 | 20.52 | 21.58 | 13.87 |
| Kill to HTTP reply | 1.67 | 2.44 | 4.74 | 4.84 | 2.73 |
| Last heartbeat written, relative to kill | -1.82 | 0.15 | 2.35 | 2.49 | 0.24 |

The kill reached a running step in 30 of 30 runs: HTTP 200, and the step's own call ended 410. Nothing was left afterwards in 30 of 30 runs: no runsc or gVisor process, `runsc list` empty.

A negative heartbeat figure means the last beat was written before T0. The harness polls /proc with a 0.2 ms sleep between checks. The figures come from one workstation, not from a Vultr VM.

Not in these numbers: the control-plane half of the kill switch, `DELETE /v2/instances/{id}` until GET returns 404. That needs Vultr.

Reproduce: `scripts/wsl-evidence.sh kill_timing --out <dir> --runs 30`
