"""brz_runner: the program that runs INSIDE the throwaway sandbox VM.

Standard library only (it is shipped by cloud-init onto a bare Ubuntu image). It accepts
HMAC-signed, single-use, scoped, expiring step requests from the control plane, executes
each step under gVisor ``runsc --platform=systrap`` (or a plain subprocess with
``--no-gvisor`` for local tests), captures stdout/stderr/output files, reads the nftables
egress log and runs a secret-hygiene scan.

It never holds a cloud credential or an inference key: the only secret it knows is the
per-task token key, which can do nothing outside this VM.
"""

__version__ = "0.1.0"
