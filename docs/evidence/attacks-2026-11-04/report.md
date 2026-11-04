# Attack suite report

**31 of 32 scenarios contained, 1 succeeded, 0 harness errors.** PASS means the attack failed. FAIL means the attack worked.
Failures we do not claim to stop: A24.

## Environment

- date_utc: `2026-11-04T12:29:49Z`
- kernel_host: `6.18.54.1-microsoft-standard-WSL2`
- runsc: `runsc version release-20261026.0`
- platform: `systrap`
- python: `3.12.3`
- git_head: `f0a9503`
- uncommitted_changes_in_sandbox_or_brz: `False`

## Results

| ID | Category | Attack | First run | Now | Time |
|---|---|---|---|---|---|
| C01 | control | Honest work still runs (negative control) | - | **PASS** | 3.2 s |
| A01 | filesystem | Write outside /work (host root) | PASS | **PASS** | 0.4 s |
| A02 | filesystem | Read host secrets and host paths | FAIL | **PASS** | 0.4 s |
| A03 | filesystem | Symlink out of /work/out into host files | FAIL | **PASS** | 0.4 s |
| A04 | filesystem | FIFO and device files in /work/out | FAIL | **PASS** | 0.8 s |
| A05 | filesystem | Plant a symlink so the next step's setup writes on the host | FAIL | **PASS** | 2.0 s |
| A06 | filesystem | Path traversal in step_id | FAIL | **PASS** | 0.3 s |
| A07 | kernel | See or signal host processes | PASS | **PASS** | 0.4 s |
| A08 | kernel | Gain root or capabilities | PASS | **PASS** | 1.5 s |
| A09 | resources | Fork bomb | PASS | **PASS** | 3.1 s |
| A10 | resources | Memory bomb | FAIL | **PASS** | 3.2 s |
| A11 | resources | CPU spin past the timeout | PASS | **PASS** | 4.3 s |
| A12 | resources | Disk fill | FAIL | **PASS** | 1.6 s |
| A13 | resources | stdout flood into the root runner | FAIL | **PASS** | 6.3 s |
| A14 | resources | Daemon that outlives its step | PASS | **PASS** | 4.9 s |
| A15 | resources | Residue between steps | PASS | **PASS** | 0.5 s |
| A16 | network | TCP exfiltration with the network off | PASS | **PASS** | 0.8 s |
| A17 | network | DNS exfiltration with the network off | PASS | **PASS** | 2.8 s |
| A18 | network | Step attacks the runner API | PASS | **PASS** | 0.5 s |
| A19 | egress | Egress allowlist against real packets | PASS | **PASS** | 12.4 s |
| A20 | egress | DNS tunnel through the allowed resolver | FAIL | **PASS** | 1.2 s |
| A21 | secrets | Secret written to an output file | PASS | **PASS** | 0.4 s |
| A22 | secrets | Secret printed to stdout and stderr | FAIL | **PASS** | 0.4 s |
| A23 | secrets | Hide a secret from the scanner | FAIL | **PASS** | 1.1 s |
| A24 | secrets | Encrypted exfiltration past the scanner | FAIL | **FAIL** | 0.4 s |
| A25 | tokens | Token replay | PASS | **PASS** | 0.5 s |
| A26 | tokens | Forged and misused tokens | PASS | **PASS** | 0.3 s |
| A27 | tokens | Tampered step payload under a valid token | FAIL | **PASS** | 0.3 s |
| A28 | tokens | Tampered step result in transit | FAIL | **PASS** | 0.9 s |
| A29 | control-plane | Prompt injection in step output changes the plan (repair path) | FAIL | **PASS** | 0.6 s |
| A30 | control-plane | Prompt injection talks the verifier into passing bad work | PASS | **PASS** | 0.9 s |
| A31 | control-plane | Kill switch against a hostile step | PASS | **PASS** | 0.5 s |

## What the first run found

- **A02 Read host secrets and host paths.** The step's root is no longer the host root. It is a skeleton with /usr read-only and a few /etc entries.
- **A03 Symlink out of /work/out into host files.** Outputs are read with lstat and O_NOFOLLOW; only regular files return, the rest are listed as skipped. The first run returned the runner's HMAC key through /work/out/stolen.key.
- **A04 FIFO and device files in /work/out.** Same change. The first run read /dev/zero through a link until the memory guard killed the runner.
- **A05 Plant a symlink so the next step's setup writes on the host.** Every /work directory is lstat-checked before a step, files are created fresh with O_NOFOLLOW, chown does not follow links. The first run wrote and chowned the decoy directory as root.
- **A06 Path traversal in step_id.** Step ids must match a strict pattern, in the runner and in the plan model.
- **A10 Memory bomb.** memory.swap is now set. The first run held 5.3 GiB against a 1.4 GiB limit by spilling into host swap.
- **A12 Disk fill.** A watchdog polls /work every 50 ms and kills the step at 2 GiB (exit 125). The first run wrote all 3 GiB.
- **A13 stdout flood into the root runner.** stdout and stderr are drained through capped readers. The first run grew the root runner past 2 GB.
- **A20 DNS tunnel through the allowed resolver.** Port 53 is closed after boot. Names are resolved once and pinned in /etc/hosts for the step. The first run delivered the tunnelled query to the resolver.
- **A22 Secret printed to stdout and stderr.** Streams are scanned and redacted in the runner before they leave it, and the findings reach /scan. A dirty scan now fails the task.
- **A23 Hide a secret from the scanner.** The scanner decodes base64 and hex one level, reads binary files, and no longer skips directories by name.
- **A27 Tampered step payload under a valid token.** Exec tokens now carry the sha256 of the step body. The first run executed swapped code under a valid token.
- **A28 Tampered step result in transit.** Replies carry an HMAC over the body and the request's token. The first run accepted a forged result.
- **A29 Prompt injection in step output changes the plan (repair path).** A repair may change code only. Turning on the network, raising the timeout or dropping expected outputs fails the task and is written to the chain. The first run executed the widened step, in two sandboxes.

## Details

### C01 Honest work still runs (negative control): PASS

- Attempted: Not an attack. Under the same sandbox: a Python step reads an input CSV and writes JSON, a re-run gives the same hash, a shell step uses sort, awk, grep and sed, and a needs_network step fetches https://example.com with curl through a name pinned in the hosts file (real TLS, certificates from the skeleton's /etc/ssl).
- Expected: All of it works. Without this control, 'every attack failed' could just mean 'nothing runs'.
- Observed:

```json
{
 "python": {
  "exit": 0,
  "stdout": "kernel 4.19.0-gvisor uid 1000\n",
  "summary.json": "{\"north\": 15.0, \"south\": 20.0}"
 },
 "rerun_identical": true,
 "shell": {
  "exit": 0,
  "stdout": "one\n2\ntools-ok\n",
  "stderr": ""
 },
 "needs_network": {
  "exit": 0,
  "stdout": "HTTP 200",
  "stderr": ""
 },
 "scan_clean": true
}
```

### A01 Write outside /work (host root): PASS

- Attempted: Step opens /etc, /usr/bin, /bin, /root, /var, /opt and /home paths for writing and tries to rename /etc/passwd.
- Expected: Every write fails inside the sandbox; no new file exists on the host afterwards.
- Observed:

```json
{
 "inside_sandbox": {
  "/etc/brz-pwn": "Permission denied",
  "/usr/bin/brz-pwn": "Permission denied",
  "/bin/brz-pwn": "Permission denied",
  "/root/brz-pwn": "No such file or directory",
  "/var/brz-pwn": "No such file or directory",
  "/opt/brz-pwn": "No such file or directory",
  "/home/brz-pwn": "No such file or directory",
  "rename /etc/passwd": "Read-only file system"
 },
 "files_on_host": [],
 "exit_code": 0
}
```

### A02 Read host secrets and host paths: PASS

- Attempted: Step reads the runner's HMAC key file /etc/brz/token.key, a root-only canary, /etc/shadow, a world-readable host canary, the runner's /proc entries, the Windows drives /mnt/c and /mnt/d, and the bundle directory.
- Expected: No canary value and no host-only path is visible to the step.
- Observed:

```json
{
 "leaked": {
  "hmac_key": false,
  "root_canary": false,
  "public_host_canary": false
 },
 "host_directories_listed": {},
 "reads": {
  "/etc/brz/token.key": "ERR No such file or directory",
  "/root/brz-canary-root.txt": "ERR No such file or directory",
  "/etc/shadow": "ERR No such file or directory",
  "/opt/brz-canary/public.txt": "ERR No such file or directory",
  "/proc/21743/environ": "ERR No such file or directory",
  "/proc/21743/cmdline": "ERR No such file or directory"
 }
}
```

### A03 Symlink out of /work/out into host files: PASS

- Attempted: Step creates /work/out/stolen.key -> /etc/brz/token.key, a link to the root canary, a link to the world-readable canary, a directory link to /, and a hard link to /etc/passwd. The runner collects /work/out as root, outside the sandbox.
- Expected: The runner returns no file content from outside /work/out, and reports what it skipped.
- Observed:

```json
{
 "http_status": 200,
 "files_returned": [],
 "leaked": {
  "hmac_key": false,
  "root_canary": false,
  "public_host_canary": false
 },
 "skipped_outputs": [
  {
   "name": "hostroot",
   "reason": "not a regular file"
  },
  {
   "name": "public.txt",
   "reason": "not a regular file"
  },
  {
   "name": "root.txt",
   "reason": "not a regular file"
  },
  {
   "name": "stolen.key",
   "reason": "not a regular file"
  }
 ],
 "stdout": "hardlink Invalid cross-device link\n"
}
```

### A04 FIFO and device files in /work/out: PASS

- Attempted: Step leaves a FIFO in /work/out (a blocking open would hang the root runner forever and hold the step lock), then in a second run a symlink to /dev/zero (an unbounded read would exhaust the runner's memory).
- Expected: The runner answers within the HTTP timeout, stays alive and stays under the memory guard.
- Observed:

```json
{
 "fifo": {
  "http_status": 200,
  "wall_s": 0.12,
  "runner_alive": true,
  "rss_guard_tripped": false,
  "runner_peak_rss_mb": 22.6,
  "stdout": "fifo planted\n",
  "skipped_outputs": []
 },
 "dev_zero": {
  "http_status": 200,
  "wall_s": 0.12,
  "runner_alive": true,
  "rss_guard_tripped": false,
  "runner_peak_rss_mb": 22.5,
  "stdout": "zero planted\n",
  "skipped_outputs": [
   {
    "name": "zero.bin",
    "reason": "not a regular file"
   }
  ]
 }
}
```

### A05 Plant a symlink so the next step's setup writes on the host: PASS

- Attempted: Step 1 swaps /work/steps/s2, /work/steps, /work/input/data.csv or /work/out for a symlink into a decoy directory outside /work. Step 2 then makes the root runner write main.py, write an input file, chown, or collect outputs through that link.
- Expected: The decoy directory is byte-for-byte and owner-for-owner unchanged and its secret is not returned.
- Observed:

```json
{
 "step_dir": {
  "plant_exit": 0,
  "second_step_http": 200,
  "second_step_exit": 0,
  "decoy_state_after": {
   "dir_uid": 0,
   "dir_mode": "0o755",
   "files": {
    "decoy-secret.txt": {
     "uid": 0,
     "mode": "0o600",
     "size": 36
    }
   }
  },
  "decoy_secret_returned": false
 },
 "steps_root": {
  "plant_exit": 0,
  "second_step_http": 200,
  "second_step_exit": 0,
  "decoy_state_after": {
   "dir_uid": 0,
   "dir_mode": "0o755",
   "files": {
    "decoy-secret.txt": {
     "uid": 0,
     "mode": "0o600",
     "size": 36
    }
   }
  },
  "decoy_secret_returned": false
 },
 "input_file": {
  "plant_exit": 0,
  "second_step_http": 200,
  "second_step_exit": 0,
  "decoy_state_after": {
   "dir_uid": 0,
   "dir_mode": "0o755",
   "files": {
    "decoy-secret.txt": {
     "uid": 0,
     "mode": "0o600",
     "size": 36
    }
   }
  },
  "decoy_secret_returned": false
 },
 "out_dir": {
  "plant_exit": 0,
  "second_step_http": 200,
  "second_step_exit": 0,
  "decoy_state_after": {
   "dir_uid": 0,
   "dir_mode": "0o755",
   "files": {
    "decoy-secret.txt": {
     "uid": 0,
     "mode": "0o600",
     "size": 36
    }
   }
  },
  "decoy_secret_returned": false
 }
}
```

### A06 Path traversal in step_id: PASS

- Attempted: A compromised planner signs a valid token for step_id ../../../../opt/brz-decoy/evil. The runner uses the id to build the step directory and the bundle path.
- Expected: HTTP 400 before any file is written; the decoy directory is unchanged.
- Observed:

```json
{
 "http_status": 400,
 "error": "invalid step: unsafe step id: '../../../../opt/brz-decoy/evil'",
 "decoy_state_after": {
  "dir_uid": 0,
  "dir_mode": "0o755",
  "files": {
   "decoy-secret.txt": {
    "uid": 0,
    "mode": "0o600",
    "size": 36
   }
  }
 }
}
```

### A07 See or signal host processes: PASS

- Attempted: Step lists /proc, reads the kernel version, then sends SIGKILL to the runner's host pid.
- Expected: Only sandbox processes are visible, the kernel is gVisor's, and the runner survives.
- Observed:

```json
{
 "kernel_inside": "4.19.0-gvisor",
 "version_inside": "Linux version 4.19.0-gvisor #1 SMP Sun Jan 10 15:06:54 PST 2016\n",
 "pids_inside": [
  1
 ],
 "runner_pid_on_host": 22465,
 "runner_pid_visible": false,
 "runner_alive_after_kill": true,
 "kill_results": {
  "kill_22465": "No such process"
 }
}
```

### A08 Gain root or capabilities: PASS

- Attempted: Step reads its capability sets, calls setuid(0), runs su, sudo, mount, chroot and a raw socket, and tries unshare to get a user namespace.
- Expected: uid stays 1000, CapEff is zero, NoNewPrivs is set, and no privileged operation succeeds.
- Observed:

```json
{
 "uid": 1000,
 "euid": 1000,
 "status": {
  "CapPrm": "0000000000000000",
  "CapEff": "0000000000000000",
  "CapBnd": "0000000000000000",
  "NoNewPrivs": "1"
 },
 "setuid0": "Operation not permitted",
 "raw_socket": "Operation not permitted",
 "su": {
  "rc": 1,
  "out": "su: Critical error - immediate abort"
 },
 "sudo": {
  "rc": 1,
  "out": "sudo: The \"no new privileges\" flag is set, which prevents sudo from running as root.\nsudo: If sudo is running in a conta"
 },
 "mount": {
  "rc": 32,
  "out": "mount: /tmp: must be superuser to use mount.\n       dmesg(1) may have more information after failed mount system call."
 },
 "chroot": {
  "rc": 127,
  "out": "/bin/sh: 1: chroot: not found"
 },
 "unshare": {
  "rc": 0,
  "out": "uid=0(root) gid=0(root) groups=0(root)"
 },
 "privileged_commands_that_worked": []
}
```

### A09 Fork bomb: PASS

- Attempted: Python step forks up to 4000 children and keeps them alive; a second step runs the classic shell bomb b(){ b|b& };b until its timeout.
- Expected: The bomb stops near the 256 pid limit (forks and host processes both at most 300), the runner keeps answering /health, every process is gone after the step, and the next step works.
- Observed:

```json
{
 "python_bomb": {
  "forks_achieved": 100,
  "error": null,
  "exit": 2
 },
 "python_bomb_host": {
  "peak_host_processes": 227,
  "peak_host_threads": 261,
  "peak_host_rss_mb": 2177.2,
  "runner_health_worst_ms": 1.2,
  "runner_health_failures": 0
 },
 "shell_bomb": {
  "exit": 2,
  "timed_out": false
 },
 "shell_bomb_host": {
  "peak_host_processes": 208,
  "peak_host_threads": 263,
  "peak_host_rss_mb": 155.7,
  "runner_health_worst_ms": 1.9,
  "runner_health_failures": 0
 },
 "processes_left_after": [],
 "next_step_exit": 0
}
```

### A10 Memory bomb: PASS

- Attempted: Step allocates and touches 64 MiB chunks, printing a running total, up to 6 GiB (limit is 1431 MiB).
- Expected: The step cannot hold much more than the limit (allowance 10 percent) and the runner survives.
- Observed:

```json
{
 "step_peak_mib": 1408,
 "limit_mib": 1431,
 "exit_code": 137,
 "stdout_tail": "\n640\n704\n768\n832\n896\n960\n1024\n1088\n1152\n1216\n1280\n1344\n1408\n",
 "stderr_tail": "",
 "host": {
  "peak_host_processes": 7,
  "peak_host_threads": 39,
  "peak_host_rss_mb": 2778.6,
  "runner_health_worst_ms": 1.7,
  "runner_health_failures": 0
 },
 "runner_alive": true,
 "processes_left_after": []
}
```

### A11 CPU spin past the timeout: PASS

- Attempted: Step starts 4 busy processes that ignore SIGTERM, SIGINT and SIGHUP, with timeout_s=3.
- Expected: exit 124 close to 3 s, and no sandbox process left on the host.
- Observed:

```json
{
 "exit_code": 124,
 "timed_out": true,
 "wall_s": 3.01,
 "processes_left_after": [],
 "runsc_containers_left": []
}
```

### A12 Disk fill: PASS

- Attempted: Step writes 400 MiB to /tmp (256 MiB tmpfs) and then up to 3 GiB to /work/out (quota 2048 MiB).
- Expected: Both writes stop at their limit (10 percent allowance on the /work quota) and nothing large is returned.
- Observed:

```json
{
 "tmp_mib_written": 256,
 "work_mib_on_host": 2166,
 "inside": {
  "/tmp/fill:error": "No space left on device",
  "/tmp/fill": 256
 },
 "exit_code": 125,
 "error": "work quota exceeded: 2269143040 bytes used, limit 2147483648",
 "stdout_tail": "6}\n/work/out/fill 256\n/work/out/fill 512\n/work/out/fill 768\n/work/out/fill 1024\n/work/out/fill 1280\n/work/out/fill 1536\n/work/out/fill 1792\n/work/out/fill 2048\n",
 "returned_mib": 0.0
}
```

### A13 stdout flood into the root runner: PASS

- Attempted: Step writes 1 MiB blocks to stdout as fast as it can until timeout_s=6, to balloon the runner, which lives outside the sandbox.
- Expected: Runner memory grows by less than 64 MiB and stdout comes back capped.
- Observed:

```json
{
 "http_status": 200,
 "runner_rss_growth_mib": 15.0,
 "rss_guard_tripped": false,
 "stdout_chars_returned": 256000,
 "exit_code": 124,
 "timed_out": true
}
```

### A14 Daemon that outlives its step: PASS

- Attempted: Step double-forks, calls setsid, closes stdio and keeps writing a heartbeat file after the step's main process has exited.
- Expected: The heartbeat stops when the step ends and no process remains.
- Observed:

```json
{
 "wall_s": 1.122,
 "exit_code": 0,
 "heartbeat_size_1_5s_after": 187,
 "heartbeat_size_3_5s_after": 187,
 "processes_left_after": []
}
```

### A15 Residue between steps: PASS

- Attempted: Step 1 leaves a marker in /tmp and in the process environment; step 2 looks for them.
- Expected: Step 2 starts with a fresh /tmp. /work is shared on purpose.
- Observed:

```json
{
 "stdout": "marker False"
}
```

### A16 TCP exfiltration with the network off: PASS

- Attempted: needs_network=false step connects to a listener on the host's loopback and on the host's real IP, to 1.1.1.1:443, and runs curl https://example.com. It also dumps /proc/net/dev.
- Expected: All connections fail, the host listeners receive nothing, and only loopback (or nothing) is visible.
- Observed:

```json
{
 "inside": {
  "127.0.0.1:44669": "Connection refused",
  "172.27.212.136:44669": "Network is unreachable",
  "1.1.1.1:443": "Network is unreachable",
  "curl": {
   "rc": 6,
   "err": "curl: (6) Could not resolve host: example.com"
  },
  "net_dev": [
   "lo"
  ]
 },
 "host_listener_hits": []
}
```

### A17 DNS exfiltration with the network off: PASS

- Attempted: needs_network=false step resolves a hostname carrying a marker and sends raw DNS-shaped UDP datagrams to 1.1.1.1:53 and to a host UDP listener.
- Expected: Resolution and sends fail or vanish; the host UDP listener receives nothing.
- Observed:

```json
{
 "inside": {
  "getaddrinfo": "ERR [Errno -2] Name or service not known",
  "1.1.1.1:53": "Network is unreachable",
  "172.27.212.136:38315": "Network is unreachable",
  "127.0.0.1:38315": "SENT, no reply: TimeoutError"
 },
 "host_listener_hits": []
}
```

### A18 Step attacks the runner API: PASS

- Attempted: needs_network=false step calls the runner's /health and an unauthenticated /revoke on 127.0.0.1 and on the host's real IP (runner bound to 0.0.0.0).
- Expected: The runner is unreachable from the sandbox and is not revoked.
- Observed:

```json
{
 "inside": {
  "http://127.0.0.1:57423/health": "URLError: <urlopen error [Errno 111] Connection refused>",
  "http://127.0.0.1:57423/revoke": "URLError: <urlopen error [Errno 111] Connection refused>",
  "http://172.27.212.136:57423/health": "URLError: <urlopen error [Errno 101] Network is unreachable>",
  "http://172.27.212.136:57423/revoke": "URLError: <urlopen error [Errno 101] Network is unreachable>"
 },
 "reached": [],
 "runner_revoked": false
}
```

### A19 Egress allowlist against real packets: PASS

- Attempted: needs_network=true step (runsc --network=host) inside a network namespace with the repo's generated nftables ruleset connects to the allowlisted IP on 443, the same IP on 8080, a non-listed IP on 443, the cloud metadata address 169.254.169.254:80, and sends UDP to a rogue resolver. Port 8700 on the VM is also probed from a non-control-plane source.
- Expected: Only allowlisted-IP:443 connects. Every other listener receives nothing. The runner port answers the control plane only.
- Observed:

```json
{
 "inside": {
  "10.203.0.2:443": "CONNECTED b'HELLO-FROM-ALLOWED'",
  "10.203.0.2:8080": "TimeoutError",
  "10.203.0.3:443": "TimeoutError",
  "169.254.169.254:80": "TimeoutError",
  "udp rogue dns": "Operation not permitted",
  "allowed.test:443": "CONNECTED b'HELLO-FROM-ALLOWED'",
  "unpinned name": "ERR [Errno -2] Name or service not known"
 },
 "listener_hits": {
  "allowed:443": [
   "10.203.0.10",
   "10.203.0.10"
  ],
  "allowed:8080": [],
  "denied:443": [],
  "metadata:80": [],
  "rogue_dns:53": []
 },
 "runner_port_from_outsider": "TimeoutError",
 "runner_port_from_control_plane": 200,
 "exit_code": 0,
 "stderr": ""
}
```

### A20 DNS tunnel through the allowed resolver: PASS

- Attempted: needs_network=true step under the same ruleset sends a DNS query carrying data in the hostname to the one resolver the ruleset allows, which a real resolver would forward to the attacker's name server.
- Expected: The resolver receives nothing from the step.
- Observed:

```json
{
 "resolver_received": [],
 "exit_code": 0,
 "stdout": "{\"udp\": \"Operation not permitted\"}\n"
}
```

### A21 Secret written to an output file: PASS

- Attempted: Step writes a fake GitHub token (real key format, assembled at run time) to /work/out/report.txt.
- Expected: /scan reports not clean, names the file, and only a redacted form appears.
- Observed:

```json
{
 "clean": false,
 "findings": [
  {
   "kind": "github_token",
   "where": "step:s1:file:report.txt:1",
   "redacted": "ghp_************AL"
  },
  {
   "kind": "github_token",
   "where": "file:/srv/brz-attacks/a21/out/report.txt:1",
   "redacted": "ghp_************AL"
  }
 ],
 "full_value_in_report": false
}
```

### A22 Secret printed to stdout and stderr: PASS

- Attempted: Step prints the fake token to stdout and stderr and writes no file. stdout feeds the repair and verifier model prompts, so this is the shortest path out.
- Expected: The token never leaves the runner in clear, and the final scan is not clean.
- Observed:

```json
{
 "token_in_clear_in_response": false,
 "stdout": "leak ghp_************AL\n",
 "secret_findings_in_response": [
  {
   "kind": "github_token",
   "where": "step:s1:stdout:1",
   "redacted": "ghp_************AL"
  },
  {
   "kind": "github_token",
   "where": "step:s1:stderr:1",
   "redacted": "ghp_************AL"
  }
 ],
 "scan_clean": false,
 "scan_findings": [
  {
   "kind": "github_token",
   "where": "step:s1:stdout:1",
   "redacted": "ghp_************AL"
  },
  {
   "kind": "github_token",
   "where": "step:s1:stderr:1",
   "redacted": "ghp_************AL"
  }
 ]
}
```

### A23 Hide a secret from the scanner: PASS

- Attempted: Step stores the fake token base64-encoded, hex-encoded, under /work/.git, at the end of a 2 MB file and after a NUL byte in a binary file.
- Expected: Every copy is reported by /scan.
- Observed:

```json
{
 "caught": {
  "b64.txt": true,
  "hex.txt": true,
  "hidden.txt": true,
  "big.txt": true,
  "bin.dat": true
 },
 "findings_count": 9,
 "files_skipped": 0
}
```

### A24 Encrypted exfiltration past the scanner: FAIL

- Attempted: Step XORs the fake token with a key and writes the ciphertext to /work/out/data.bin.
- Expected: Pattern scanning cannot see this. Recorded so nobody reads the scanner as a data-loss guarantee.
- Accepted limitation: A pattern scanner cannot detect encrypted data. The guarantee is that the sandbox holds no secret to steal and has no route out; the scanner is a tripwire, not a DLP system.
- Observed:

```json
{
 "clean": true,
 "file_returned": true
}
```

### A25 Token replay: PASS

- Attempted: A captured exec token is replayed once sequentially, then 8 times in parallel.
- Expected: Exactly one execution; every replay gets 403.
- Observed:

```json
{
 "first": 200,
 "replay": 403,
 "replay_error": "token rejected: token already used (replay)",
 "parallel_replay_statuses": [
  200,
  403,
  403,
  403,
  403,
  403,
  403,
  403
 ],
 "steps_run": 2
}
```

### A26 Forged and misused tokens: PASS

- Attempted: Requests with a token signed by the wrong key, for another task, with exec scope on /revoke, with scan scope on /steps, bound to another step, expired, issued in the future, with a payload edited under the original signature, with an empty signature, and with no token.
- Expected: All rejected with 401/403; nothing runs and the runner is not revoked.
- Observed:

```json
{
 "wrong_key": {
  "status": 403,
  "error": "token rejected: bad signature"
 },
 "other_task": {
  "status": 403,
  "error": "token rejected: token is for a different task"
 },
 "exec_on_revoke": {
  "status": 403,
  "error": "token rejected: token scope ['exec'] does not allow 'revoke'"
 },
 "scan_on_steps": {
  "status": 403,
  "error": "token rejected: token scope ['scan'] does not allow 'exec'"
 },
 "bound_to_other_step": {
  "status": 403,
  "error": "token rejected: token is bound to step 's9', not 's1'"
 },
 "expired": {
  "status": 403,
  "error": "token rejected: token expired"
 },
 "issued_in_future": {
  "status": 403,
  "error": "token rejected: token issued in the future"
 },
 "edited_payload": {
  "status": 403,
  "error": "token rejected: bad signature"
 },
 "empty_signature": {
  "status": 403,
  "error": "token rejected: bad signature"
 },
 "missing": {
  "status": 401,
  "error": "token required"
 },
 "steps_run": 0,
 "revoked": false
}
```

### A27 Tampered step payload under a valid token: PASS

- Attempted: A man in the middle of the plain-HTTP control link keeps the valid token for step s1 and swaps the step's code, its needs_network flag, or an input file.
- Expected: HTTP 403; the swapped code never runs.
- Observed:

```json
{
 "code": {
  "status": 403,
  "error": "token rejected: token does not match this step body",
  "executed": false
 },
 "needs_network": {
  "status": 403,
  "error": "token rejected: token does not match this step body",
  "executed": false
 },
 "files": {
  "status": 403,
  "error": "token rejected: token does not match this step body",
  "executed": false
 }
}
```

### A28 Tampered step result in transit: PASS

- Attempted: A man in the middle edits the runner's reply to the real RunnerClient: changes stdout, swaps an output file and recomputes its sha256 so the existing per-file hash check still passes.
- Expected: RunnerClient rejects the reply.
- Observed:

```json
{
 "rewrote_replies": 1,
 "accepted": false,
 "error": "runner /steps: reply failed authentication (MAC mismatch)"
}
```

### A29 Prompt injection in step output changes the plan (repair path): PASS

- Attempted: A failing step prints an operator-override injection. The repair model is scripted to obey fully: it returns a step with needs_network=true, timeout 1800 s and no expected outputs. Real orchestrator, real gVisor runner, scripted worst-case model (not a real LLM).
- Expected: The widened step never runs, the network stays off, the allowlist does not grow, the task does not verify, and the rejection is in the hash chain.
- Observed:

```json
{
 "repair_model_saw_injection": true,
 "final_status": "failed",
 "steps_executed": 1,
 "plan_after_repair": [
  {
   "id": "s1",
   "needs_network": false,
   "timeout_s": 20,
   "expected_outputs": [
    "result.json"
   ]
  }
 ],
 "vm_allowlists": [
  []
 ],
 "audit_kinds": [
  "task.received",
  "task.planning",
  "cost.tokens",
  "plan.created",
  "budget.preflight",
  "task.provisioning",
  "vm.created",
  "vm.runner_ready",
  "task.running",
  "step.finished",
  "cost.tokens",
  "step.repair_rejected",
  "task.destroying",
  "vm.destroyed",
  "task.failed"
 ],
 "receipt_integrity": true,
 "receipt_problems": []
}
```

### A30 Prompt injection talks the verifier into passing bad work: PASS

- Attempted: A step exits 0 but writes the wrong result and prints an injection saying the work is verified. The verifier model is scripted to agree with confidence 1.0. Real orchestrator, real gVisor runner, two sandboxes.
- Expected: The deterministic assertion fails the task regardless of the model's verdict.
- Observed:

```json
{
 "verifier_model_saw_injection": true,
 "model_said_satisfied": true,
 "failed_checks": [
  "assert:file_contains:result.json:RIGHT"
 ],
 "final_status": "failed",
 "rerun_match": true
}
```

### A31 Kill switch against a hostile step: PASS

- Attempted: A running step ignores SIGTERM and spawns spinning children. /revoke is called mid-step, then new signed tokens are tried on /steps and /scan.
- Expected: Sandbox processes are gone, the step's HTTP call ends with 410, and every later token gets 403.
- Observed:

```json
{
 "revoke": {
  "revoked": true,
  "killed_running_step": true,
  "poweroff": false,
  "revoked_at": "2026-11-04T12:30:49.880696+00:00"
 },
 "sandbox_processes_at_kill": 13,
 "kill_to_all_gone_ms": 8.8,
 "running_step_http_status": 410,
 "processes_left_after": [],
 "new_step_token_after_kill": 403,
 "new_scan_token_after_kill": 403
}
```

