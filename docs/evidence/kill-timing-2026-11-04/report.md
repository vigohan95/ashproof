# Kill switch timing under gVisor

30 runs on runsc version release-20261026.0, platform systrap, WSL2 kernel 6.18.54.1-microsoft-standard-WSL2, 2026-11-04T12:39:51Z. Hostile step: 5 processes ignoring SIGTERM, four of them spinning on the CPU.

T0 is immediately before `POST /revoke` is sent with a signed token. All figures in milliseconds.

| Measure | min | p50 | p95 | max | mean |
|---|---|---|---|---|---|
| Kill to every host process of the sandbox gone | 8.39 | 9.47 | 10.61 | 10.64 | 9.44 |
| Kill to HTTP reply | 1.33 | 1.52 | 2.23 | 2.54 | 1.58 |
| Last heartbeat written, relative to kill | -2.29 | -0.24 | 1.09 | 1.26 | -0.32 |

The kill reached a running step in 30 of 30 runs: HTTP 200, and the step's own call ended 410. Nothing was left afterwards in 30 of 30 runs: no runsc or gVisor process, `runsc list` empty.

A negative heartbeat figure means the last beat was written before T0. The harness polls /proc with a 0.2 ms sleep between checks. The figures come from one workstation, not from a Vultr VM.

Not in these numbers: the control-plane half of the kill switch, `DELETE /v2/instances/{id}` until GET returns 404. That needs Vultr.

An earlier batch of 30 runs the same day, at commit c979017, gave p50 13.23 ms, p95 20.52 ms and max 21.58 ms for the first row. Treat tens of milliseconds as the honest scale, not the single figure.

Reproduce: `scripts/wsl-evidence.sh kill_timing --out <dir> --runs 30`
