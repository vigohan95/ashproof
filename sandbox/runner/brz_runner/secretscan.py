"""Secret-hygiene scan (standard library only).

Runs at the end of every task inside the sandbox and answers one question for the
receipt: *did any credential exist in this VM?* It scans the process environment,
``/etc/environment``-style files and the task work tree for well-known key formats and
for suspiciously named environment variables. Findings are redacted before they leave
the VM (first 4 + last 2 characters only).

The expected result on a Ashproof sandbox is CLEAN, because the control plane
never ships a credential into the VM. The scan exists to *prove* that, not to hope it.

It also looks one level inside base64 and hex blobs, reads binary files and every directory
under the work tree. It is a tripwire, not data-loss prevention: anything encrypted passes
(attack A24 records that). The real guarantee is that there is nothing to steal and no way out.
"""

from __future__ import annotations

import base64
import binascii
import os
import re
from dataclasses import asdict, dataclass, field

# (kind, compiled regex) - formats with distinctive prefixes to keep false positives low
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("aws_access_key_id", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github_token", re.compile(r"\b(ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b")),
    ("github_fine_grained_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    ("openai_key", re.compile(r"\bsk-(proj-)?[A-Za-z0-9_-]{32,}\b")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{32,}\b")),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("stripe_key", re.compile(r"\b(sk|rk|pk)_(live|test)_[A-Za-z0-9]{16,}\b")),
    ("private_key_block", re.compile(r"-----BEGIN (RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY( BLOCK)?-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
    ("vultr_api_key", re.compile(r"\bVULTR_API_KEY\s*[=:]\s*['\"]?[A-Z0-9]{36}\b")),
    (
        "generic_assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token|password|passwd)"
            r"\s*[=:]\s*['\"]?([A-Za-z0-9_\-./+=]{16,})"
        ),
    ),
]

SENSITIVE_ENV_RE = re.compile(r"(?i)(key|token|secret|password|passwd|credential|auth)")
# env names that match the regex but are not secrets
ENV_ALLOWLIST = frozenset(
    {
        "SSH_AUTH_SOCK",
        "GPG_AGENT_INFO",
        "XAUTHORITY",
        "PYTHONDONTWRITEBYTECODE",
        "KEYBOARD",
        "BRZ_TOKEN_KEY_FILE",
        "AUTHORIZATION_MODE",
        "XDG_SESSION_KEY",
    }
)

# Absolute paths, so a step cannot hide a file by naming a directory ".git" or "run".
SKIP_ROOTS = frozenset({"/proc", "/sys", "/dev", "/run"})
# Larger than the 5 MB per-file output cap: every file that can leave the VM is scanned.
DEFAULT_MAX_FILE_BYTES = 8_000_000
B64_BLOB = re.compile(r"[A-Za-z0-9+/_-]{24,}={0,2}")
HEX_BLOB = re.compile(r"\b(?:[0-9a-fA-F]{2}){16,}\b")


@dataclass
class Finding:
    kind: str
    where: str  # "env:NAME" or "file:/path:line"
    redacted: str


@dataclass
class ScanReport:
    clean: bool
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0
    files_skipped: int = 0
    env_vars_checked: int = 0
    scanned_paths: list[str] = field(default_factory=list)
    scanner: str = "brz_runner.secretscan"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["findings_count"] = len(self.findings)
        return d


def redact(value: str) -> str:
    value = value.strip()
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * min(len(value) - 6, 12)}{value[-2:]}"


def _encoded_blobs(line: str):
    """Yield (blob, encoding, decoded text) for every base64 or hex run on the line that decodes."""
    for m in HEX_BLOB.finditer(line):
        yield m.group(0), "hex", bytes.fromhex(m.group(0)).decode("latin-1")
    for m in B64_BLOB.finditer(line):
        blob = m.group(0)
        padded = blob.rstrip("=").replace("-", "+").replace("_", "/")
        try:
            decoded = base64.b64decode(padded + "=" * (-len(padded) % 4))
        except (binascii.Error, ValueError):
            continue
        yield blob, "base64", decoded.decode("latin-1")


def _matches(text: str):
    for kind, rx in PATTERNS:
        for m in rx.finditer(text):
            yield kind, m


def _secret_of(kind: str, m: re.Match[str]) -> str:
    return m.group(2) if kind == "generic_assignment" else m.group(0)


def scan_text(text: str, where: str) -> list[Finding]:
    findings: list[Finding] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for kind, m in _matches(line):
            findings.append(Finding(kind=kind, where=f"{where}:{lineno}", redacted=redact(_secret_of(kind, m))))
        for blob, encoding, decoded in _encoded_blobs(line):
            for kind, _m in _matches(decoded):
                findings.append(Finding(kind=f"{kind}:{encoding}", where=f"{where}:{lineno}", redacted=redact(blob)))
    return findings


def scan_and_redact(text: str, where: str) -> tuple[str, list[Finding]]:
    """Findings in ``text``, and ``text`` with each secret replaced by its redacted form."""
    findings = scan_text(text, where)
    if not findings:
        return text, []
    out: list[str] = []
    for line in text.split("\n"):
        for kind, m in list(_matches(line)):
            secret = _secret_of(kind, m)
            line = line.replace(secret, redact(secret))
        for blob, _encoding, decoded in list(_encoded_blobs(line)):
            if any(True for _ in _matches(decoded)):
                line = line.replace(blob, "[redacted encoded secret]")
        out.append(line)
    return "\n".join(out), findings


def scan_env(environ: dict[str, str] | None = None) -> tuple[list[Finding], int]:
    env = dict(os.environ if environ is None else environ)
    findings: list[Finding] = []
    for name, value in env.items():
        if not value:
            continue
        for kind, rx in PATTERNS[:-1]:  # value formats (skip generic assignment: env has no "=")
            if rx.search(value):
                findings.append(Finding(kind=kind, where=f"env:{name}", redacted=redact(value)))
                break
        else:
            if SENSITIVE_ENV_RE.search(name) and name not in ENV_ALLOWLIST and len(value) >= 8:
                findings.append(Finding(kind="sensitive_env_name", where=f"env:{name}", redacted=redact(value)))
    return findings, len(env)


def scan_paths(paths: list[str], *, max_file_bytes: int = DEFAULT_MAX_FILE_BYTES) -> tuple[list[Finding], int, int]:
    findings: list[Finding] = []
    scanned = skipped = 0
    for root_path in paths:
        if os.path.isfile(root_path):
            candidates = [root_path]
        elif os.path.isdir(root_path):
            candidates = []
            for dirpath, dirnames, filenames in os.walk(root_path):
                dirnames[:] = [
                    d
                    for d in dirnames
                    if os.path.join(dirpath, d) not in SKIP_ROOTS and not os.path.islink(os.path.join(dirpath, d))
                ]
                for fn in filenames:
                    candidates.append(os.path.join(dirpath, fn))
        else:
            continue
        for path in candidates:
            try:
                if os.path.islink(path) or os.path.getsize(path) > max_file_bytes:
                    skipped += 1
                    continue
                with open(path, "rb") as fh:
                    data = fh.read(max_file_bytes)
            except OSError:
                skipped += 1
                continue
            scanned += 1
            findings.extend(scan_text(data.decode("utf-8", "replace"), f"file:{path}"))
    return findings, scanned, skipped


def run_scan(paths: list[str], environ: dict[str, str] | None = None, **kw) -> ScanReport:
    env_findings, env_count = scan_env(environ)
    file_findings, scanned, skipped = scan_paths(paths, **kw)
    findings = env_findings + file_findings
    return ScanReport(
        clean=not findings,
        findings=findings,
        files_scanned=scanned,
        files_skipped=skipped,
        env_vars_checked=env_count,
        scanned_paths=list(paths),
    )
