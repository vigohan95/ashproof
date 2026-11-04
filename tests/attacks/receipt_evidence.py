"""Tamper evidence on a real receipt: ``python -m tests.attacks.receipt_evidence --out DIR``.

Runs one honest two-step task through the real orchestrator with both sandboxes in real gVisor, keeps the
receipt, then attacks copies of it and checks each with the offline verifier run as ``python -I -S``.
VM create/delete is skipped (no cloud here), so the receipt's proof of destruction reads "local runner stopped".
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from . import harness as H
from .scenarios import Ctx, _gvisor_backend

STEP_1 = """
import csv, json, os
rows = list(csv.DictReader(open(os.path.join(os.environ['BRZ_INPUT'], 'sales.csv'))))
tot = {}
for r in rows:
    tot[r['region']] = tot.get(r['region'], 0) + float(r['amount'])
json.dump(dict(sorted(tot.items())), open(os.path.join(os.environ['BRZ_OUT'], 'summary.json'), 'w'), sort_keys=True)
print('totals written')
"""
STEP_2 = """
import json, os
tot = json.load(open(os.path.join(os.environ['BRZ_OUT'], 'summary.json')))
open(os.path.join(os.environ['BRZ_OUT'], 'report.md'), 'w').write(f"north {tot['north']}, south {tot['south']}")
print('report written')
"""
PLAN = {
    "task_summary": "Total sales per region and write a short report",
    "steps": [
        {"id": "s1", "title": "totals", "kind": "python", "code": STEP_1, "expected_outputs": ["summary.json"]},
        {"id": "s2", "title": "report", "kind": "python", "code": STEP_2, "expected_outputs": ["report.md"]},
    ],
    "required_domains": [],
    "assertions": ["file_contains:report.md:north 15.0"],
    "est_cost_usd": 0.01,
    "est_minutes": 1,
    "risk_notes": [],
}


def run_task(ctx: Ctx):
    from brz.llm import FakeLLM, Planner, Verifier
    from brz.orchestrator import Orchestrator, OrchestratorConfig, TaskRequest

    def respond(messages: list[dict]) -> str:
        if "independent verifier" in str(messages[0].get("content")):
            return json.dumps({"satisfies_task": True, "confidence": 0.9, "reasons": ["totals match"], "concerns": []})
        return json.dumps(PLAN)

    llm = FakeLLM(respond, model="scripted-model")
    orch = Orchestrator(
        planner=Planner(llm),
        verifier=Verifier(llm),
        backend=_gvisor_backend(ctx, "receipt"),
        config=OrchestratorConfig(runner_ready_interval_s=0.2, runner_ready_timeout_s=20),
    )

    async def go():
        request = TaskRequest(
            task="Total the amount column per region in sales.csv and write report.md",
            budget_usd=5,
            files={"sales.csv": b"region,amount\nnorth,10\nsouth,20\nnorth,5\n"},
        )
        return await orch.run(orch.new_task(request))

    return asyncio.run(go())


def _canon(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _reseal(d: dict) -> None:
    body = {k: v for k, v in d.items() if k != "receipt_sha256"}
    d["receipt_sha256"] = hashlib.sha256(_canon(body).encode("utf-8")).hexdigest()


def _rechain(d: dict, event_hash) -> None:
    prev = "0" * 64
    for ev in d["audit_events"]:
        ev["prev_hash"] = prev
        ev["hash"] = event_hash(ev)
        prev = ev["hash"]
    d["audit_head_hash"] = prev
    d["audit_chain"]["head_hash"] = prev
    _reseal(d)


def tamper_cases(raw: bytes, event_hash) -> list[tuple[str, bytes, list[str]]]:
    def edited(fn) -> bytes:
        d = json.loads(raw)
        fn(d)
        return json.dumps(d, indent=2).encode("utf-8")

    def primary(d: dict, step: str) -> int:
        return next(
            i
            for i, e in enumerate(d["audit_events"])
            if e["kind"] == "step.finished" and e["data"]["role"] == "primary" and e["data"]["step_id"] == step
        )

    def flip_one_byte() -> bytes:
        pos = raw.index(b'"stdout_sha256"') + 20
        out = bytearray(raw)
        out[pos] ^= 0x01
        return bytes(out)

    def delete_event(d: dict) -> None:
        del d["audit_events"][primary(d, "s2")]

    def delete_table_row(d: dict) -> None:
        del d["steps"][1]
        _reseal(d)

    def swap_events(d: dict) -> None:
        a, b = primary(d, "s1"), primary(d, "s2")
        d["audit_events"][a], d["audit_events"][b] = d["audit_events"][b], d["audit_events"][a]

    def swap_table(d: dict) -> None:
        d["steps"].reverse()
        _reseal(d)

    def pass_a_failed_task(d: dict) -> None:
        d["steps"][0]["exit_code"] = 1
        _reseal(d)

    def rewrite(d: dict) -> None:
        i = primary(d, "s1")
        forged = "0" * 64
        d["audit_events"][i]["data"]["stdout_sha256"] = forged
        d["steps"][0]["stdout_sha256"] = forged
        _rechain(d, event_hash)

    head = json.loads(raw)["audit_head_hash"]
    return [
        ("control: untouched receipt", raw, []),
        ("flip one byte in a step hash", flip_one_byte(), []),
        ("delete a step from the chain", edited(delete_event), []),
        ("delete a step from the table, reseal receipt_sha256", edited(delete_table_row), []),
        ("reorder steps in the chain", edited(swap_events), []),
        ("reorder steps in the table, reseal receipt_sha256", edited(swap_table), []),
        ("change an exit code in the table, reseal receipt_sha256", edited(pass_a_failed_task), []),
        ("full rewrite of chain and receipt, no pin", edited(rewrite), []),
        ("full rewrite of chain and receipt, head pinned", edited(rewrite), ["--expect-head", head]),
    ]


def verify_with_cli(tool: str, path: Path, extra: list[str]) -> dict:
    p = subprocess.run(
        [sys.executable, "-I", "-S", tool, str(path), "--json", *extra],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    out = json.loads(p.stdout)
    return {"exit_code": p.returncode, "ok": out["ok"], "problems": out["problems"]}


def main() -> int:
    from brz.audit import offline_verify as ov

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    canaries = H.Canaries()
    canaries.install()
    ctx = Ctx(canaries)
    try:
        receipt = run_task(ctx)
    finally:
        for r in ctx.runners:
            r.stop()
        canaries.remove()
    raw = receipt.to_json().encode("utf-8")
    (out / "receipt.json").write_bytes(raw)
    (out / "receipt.md").write_text(receipt.to_markdown(), encoding="utf-8")
    print(f"status {receipt.status}, {len(receipt.audit_events)} events, head {receipt.audit_head_hash}")

    tool = ov.__file__
    work = out / "_tampered.json"
    cases = []
    for name, data, extra in tamper_cases(raw, ov.event_hash):
        work.write_bytes(data)
        cases.append({"case": name, **verify_with_cli(tool, work, extra)})
        print(cases[-1])
    work.unlink()

    t = time.perf_counter()
    survivors = []
    changed_a_value = []
    honest = json.loads(raw)
    for pos in range(len(raw)):
        flipped = bytearray(raw)
        flipped[pos] ^= 0x01
        if ov.verify_bytes(bytes(flipped))["ok"]:
            survivors.append(pos)
            if json.loads(bytes(flipped)) != honest:
                changed_a_value.append(pos)
    sweep = {
        "bytes_in_file": len(raw),
        "single_byte_flips_tried": len(raw),
        "flips_undetected": len(survivors),
        "undetected_positions": survivors[:20],
        "undetected_contexts": [raw[max(p - 24, 0) : p + 4].decode("utf-8", "replace") for p in survivors[:20]],
        "undetected_flips_that_changed_a_parsed_value": len(changed_a_value),
        "seconds": round(time.perf_counter() - t, 1),
    }
    print(sweep)

    expected = {c["case"]: c["case"].startswith("control") or c["case"].endswith("no pin") for c in cases}
    as_expected = all(c["ok"] == expected[c["case"]] for c in cases) and not changed_a_value
    result = {
        "receipt_status": receipt.status,
        "audit_events": len(receipt.audit_events),
        "audit_head_hash": receipt.audit_head_hash,
        "receipt_sha256": receipt.receipt_sha256,
        "cases": cases,
        "byte_flip_sweep": sweep,
        "all_as_expected": as_expected,
    }
    (out / "tamper-results.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
    lines = [
        "# Receipt tamper detection",
        "",
        f"A real receipt (status `{receipt.status}`, {len(receipt.audit_events)} events, both sandboxes in gVisor in "
        "WSL, scripted models, no cloud VM) attacked in copies. Each copy was checked by `brz/audit/offline_verify.py` "
        "run as `python -I -S`, so nothing but the standard library was loaded.",
        "",
        "| Tamper | Verifier said | Exit | Reason |",
        "|---|---|---|---|",
    ]
    for c in cases:
        reason = (c["problems"] or ["-"])[0].replace("|", "\\|")[:110]
        lines.append(f"| {c['case']} | {'OK' if c['ok'] else 'TAMPERED'} | {c['exit_code']} | {reason} |")
    lines += [
        "",
        f"Sweep: every one of the {sweep['bytes_in_file']} bytes of the file was flipped in turn (XOR 0x01). "
        f"{sweep['flips_undetected']} flips went undetected, and "
        f"{sweep['undetected_flips_that_changed_a_parsed_value']} "
        "of those changed any parsed value. An undetected flip that changes no value is a last digit of a long float "
        "that rounds to the same double: the hashes cover values, not the file's bytes. "
        f"Undetected contexts: `{sweep['undetected_contexts']}`.",
        "",
        "The one row that says OK after an edit is deliberate: a hash chain has no key, so a forger who recomputes "
        "every hash produces a consistent file. Only a head hash kept elsewhere exposes that, which is what the next "
        "row shows, and the tool prints a warning whenever no pin is given.",
        "",
        "Reproduce: `python brz/audit/offline_verify.py docs/evidence/receipts-2026-11-04/receipt.json`",
        "",
    ]
    (out / "tamper-report.md").write_text("\n".join(lines), encoding="utf-8")
    print("as expected:", as_expected)
    return 0 if as_expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
