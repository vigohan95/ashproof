# Kill switch on real Vultr VMs

Measured from the control plane's audit events: `kill.requested` to the last `vm.destroyed`, which is

written after `GET /v2/instances/{id}` returned 404. Each task had two VMs. Vultr plan vhp-1c-1gb-amd, ewr.

## kill-step: 5 runs

Button to both VMs 404: median 0.52 s, min 0.35 s, max 1.11 s.

| task | state at kill | final | step killed | tokens revoked (s) | both 404 (s) | VMs | all 404 |
|---|---|---|---|---|---|---|---|
| 40303d78f489 | running | killed | True | 0.012 | 0.517 | 2 | True |
| def42ffeb355 | running | killed | True | 0.011 | 1.108 | 2 | True |
| 4183c5cfec05 | running | killed | True | 0.01 | 0.563 | 2 | True |
| 15054bccb8d2 | running | killed | True | 0.011 | 0.35 | 2 | True |
| 32d757f86235 | running | killed | True | 0.014 | 0.458 | 2 | True |

## kill-boot: 3 runs

Button to both VMs 404: median 21.79 s, min 20.04 s, max 77.12 s.

| task | state at kill | final | step killed | tokens revoked (s) | both 404 (s) | VMs | all 404 |
|---|---|---|---|---|---|---|---|
| 199ed2ac2a34 | provisioning | killed | False | None | 21.785 | 2 | True |
| 706fa63d1e02 | provisioning | killed | False | None | 20.038 | 2 | True |
| 06c02213bdee | provisioning | killed | False | None | 77.124 | 2 | True |
