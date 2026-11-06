#!/usr/bin/env python3
"""Records the real public demo for the video. Each segment is one continuous recording of Chrome on the live site.

    python docs/video/capture.py <out dir> home limits evidence github      # no live task
    python docs/video/capture.py <out dir> normal                           # one live task
    python docs/video/capture.py <out dir> attack                           # one live task, downloads the receipt
    python docs/video/capture.py <out dir> kill                             # one live task, presses the kill switch

The demo allows one task at a time and 6 per hour from one address. Run the live segments one after another. Each one
writes <out dir>/<segment>/index.json: frame times, named moments, and the task as the API reported it.

Requires `pip install playwright` and Google Chrome.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from rec import BASE, Recorder, click, new_page, point, scroll_to  # noqa: E402

REPO_CSV = "https://github.com/vigohan95/ashproof/blob/main/apps/control_plane/scenarios.py#L19-L24"
DONE = {"verified", "failed", "killed", "error"}
TASK_TIMEOUT = 330


def wait_idle(ctx):
    """A stranger may be using the demo. Waits for the one task slot instead of failing."""
    for _ in range(90):
        h = ctx.request.get(BASE + "/health").json()
        if not h["running_id"]:
            return h
        print("  demo busy with", h["running_id"], flush=True)
        time.sleep(5)
    sys.exit("the demo stayed busy for 7 minutes")


def task(ctx, tid):
    return ctx.request.get(f"{BASE}/tasks/{tid}").json()


def wait_for(page, ctx, tid, test, what, limit=TASK_TIMEOUT):
    start = time.time()
    while time.time() - start < limit:
        d = task(ctx, tid)
        if test(d):
            return d
        page.wait_for_timeout(400)
    sys.exit(f"gave up waiting for {what} on task {tid}: {task(ctx, tid)['status']}")


def scroll_h2(page, text, top=58, ms=900):
    page.evaluate(
        """([text, top]) => { const e = [...document.querySelectorAll("h2")].find(h => h.textContent.trim().toLowerCase().startsWith(text.toLowerCase()));
           if (e) window.scrollTo({ top: e.getBoundingClientRect().top + scrollY - top, behavior: "smooth" }); }""",
        [text, top],
    )
    page.wait_for_timeout(ms)


def slow_scroll(page, selector, top, seconds):
    """Linear scroll over a set time, for reading a long table."""
    page.evaluate(
        """([sel, top, ms]) => new Promise(done => {
             const e = document.querySelector(sel); const from = scrollY;
             const to = e.getBoundingClientRect().top + scrollY - top; const t0 = performance.now();
             const step = t => { const k = Math.min(1, (t - t0) / ms); window.scrollTo(0, from + (to - from) * k); k < 1 ? requestAnimationFrame(step) : done(); };
             requestAnimationFrame(step); })""",
        [selector, top, int(seconds * 1000)],
    )


def seg_home(page, ctx, r):
    r.start()
    page.goto(BASE + "/", wait_until="load")
    r.mark("loaded")
    page.wait_for_selector("#roll .ln")
    r.mark("replay_started")
    page.wait_for_selector("#roll .total", timeout=25000)
    r.mark("replay_done")
    page.wait_for_timeout(2500)
    point(page, "text=Open the receipt")
    page.wait_for_timeout(800)


def seg_limits(page, ctx, r):
    page.goto(BASE + "/", wait_until="load")
    page.wait_for_timeout(600)
    r.start()
    scroll_h2(page, "What it does not do", top=90, ms=1100)
    r.mark("limits")
    page.wait_for_timeout(3000)


def seg_evidence(page, ctx, r):
    r.start()
    page.goto(BASE + "/ui/evidence", wait_until="load")
    r.mark("loaded")
    page.wait_for_timeout(3500)
    r.mark("scroll")
    slow_scroll(page, "tr.deny", 300, 7)
    r.mark("a24")
    page.wait_for_timeout(3000)


def seg_github(page, ctx, r):
    page.goto(REPO_CSV, wait_until="load")
    page.wait_for_timeout(2000)
    page.mouse.click(32, 32)  # the Files panel's collapse button: more room for the long injected line
    page.mouse.move(900, 300)
    page.wait_for_timeout(1500)
    r.start()
    r.mark("shown")
    page.wait_for_timeout(4000)


def seg_card(page, ctx, r):
    """The end card is the one screen that is not the product, so it is plain HTML and says only what the README says."""
    page.goto((pathlib.Path(__file__).resolve().parent / "endcard.html").as_uri(), wait_until="networkidle")
    page.wait_for_timeout(800)
    r.out.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(r.out / "f000001.jpg"), type="jpeg", quality=95)
    r.frames.append({"name": "f000001.jpg", "t": 0.0})


def run_task(page, ctx, r, button):
    """Clicks a home page button and returns the new task's id."""
    wait_idle(ctx)
    r.start()
    page.goto(BASE + "/", wait_until="load")
    page.wait_for_selector("#roll .ln")
    page.wait_for_timeout(1500)
    r.mark("home")
    click(page, button)
    r.mark("clicked")
    page.wait_for_url("**/ui/tasks/*")
    tid = page.url.rsplit("/", 1)[1]
    r.mark("task_page")
    print("  task", tid, flush=True)
    return tid


def follow_boot(page, ctx, r, tid):
    """Plan, then the VM table through boot. Marks every state a viewer sees change."""
    wait_for(page, ctx, tid, lambda d: d.get("plan"), "the plan")
    r.mark("plan")
    page.wait_for_timeout(900)
    scroll_h2(page, "Plan")
    r.mark("plan_shown")
    page.wait_for_timeout(5000)
    d = wait_for(page, ctx, tid, lambda d: d["sandboxes"], "the VMs")
    scroll_h2(page, "Sandbox VMs")
    r.mark("vms")
    d = wait_for(
        page,
        ctx,
        tid,
        lambda d: all(s.get("active_at") for s in d["sandboxes"]) and len(d["sandboxes"]) >= 2,
        "active VMs",
    )
    r.mark("vms_active")
    return d


def seg_normal(page, ctx, r):
    tid = run_task(page, ctx, r, "button.alt >> nth=0")
    follow_boot(page, ctx, r, tid)
    wait_for(page, ctx, tid, lambda d: d["steps"], "the first step")
    r.mark("step_done")
    wait_for(page, ctx, tid, lambda d: d.get("verdict") or d["status"] in DONE, "the verdict")
    page.wait_for_timeout(2300)
    scroll_h2(page, "Verification")
    r.mark("verdict")
    page.wait_for_timeout(1500)
    wait_for(page, ctx, tid, lambda d: d["status"] in DONE, "the end")
    r.mark("done")
    page.wait_for_timeout(2500)
    page.locator("#verdict details summary").first.click()  # safe now: the page stops refreshing when the task ends
    r.mark("hashes_open")
    page.wait_for_timeout(5000)
    scroll_h2(page, "Sandbox VMs")
    r.mark("vm_404")
    page.wait_for_timeout(5000)
    page.evaluate("window.scrollTo({top:0,behavior:'smooth'})")
    page.wait_for_timeout(1000)
    r.mark("top")
    page.wait_for_timeout(2500)
    click(page, "#receipt-link")
    page.wait_for_url("**/receipt")
    page.wait_for_selector("#tamper-btn:not([disabled])")
    r.mark("receipt")
    page.wait_for_timeout(3000)
    return {"task": task(ctx, tid)}


def seg_attack(page, ctx, r):
    tid = run_task(page, ctx, r, "#run-live")
    page.wait_for_selector("#scripted-note:visible")
    r.mark("note")
    page.wait_for_timeout(1500)
    follow_boot(page, ctx, r, tid)
    wait_for(page, ctx, tid, lambda d: d["egress"]["denied"] > 0, "refused packets")
    page.wait_for_timeout(1800)
    scroll_h2(page, "Egress attempts")
    r.mark("egress_first")
    wait_for(page, ctx, tid, lambda d: d.get("verdict") or d["status"] in DONE, "the verdict")
    page.wait_for_timeout(2200)
    r.mark("egress_all")
    page.wait_for_timeout(2500)
    wait_for(page, ctx, tid, lambda d: d["status"] in DONE, "the end")
    r.mark("done")
    page.wait_for_timeout(2500)
    page.evaluate("window.scrollTo({top:0,behavior:'smooth'})")
    page.wait_for_timeout(1100)
    r.mark("top_failed")
    page.wait_for_timeout(4500)
    scroll_h2(page, "Verification")
    r.mark("verdict")
    page.wait_for_timeout(9000)
    page.evaluate("window.scrollTo({top:0,behavior:'smooth'})")
    page.wait_for_timeout(1000)
    click(page, "#receipt-link")
    page.wait_for_url("**/receipt")
    page.wait_for_selector("#tamper-btn:not([disabled])")
    page.wait_for_timeout(1200)
    r.mark("receipt")
    scroll_to(page, "#check-panel", top=20)
    r.mark("check_pass")
    page.wait_for_timeout(4500)
    click(page, "#tamper-btn")
    page.wait_for_function("document.getElementById('check-title').classList.contains('bad')")
    r.mark("check_broken")
    page.wait_for_timeout(5500)
    click(page, "#tamper-btn")
    page.wait_for_function("document.getElementById('check-title').classList.contains('ok')")
    r.mark("check_restored")
    page.wait_for_timeout(2500)
    scroll_h2(page, "What was refused", top=30)
    r.mark("refused")
    page.wait_for_timeout(4000)
    scroll_to(page, "#check-panel + .panel", top=30)
    r.mark("script_report")
    page.wait_for_timeout(4500)
    page.evaluate("window.scrollTo({top:0,behavior:'smooth'})")
    page.wait_for_timeout(1000)
    with page.expect_download() as dl:
        click(page, "text=Download JSON")
    dl.value.save_as(str(r.out.parent / f"receipt-{tid}.json"))
    (r.out.parent / "anchors.jsonl").write_bytes(ctx.request.get(BASE + "/anchors.jsonl").body())
    r.mark("downloaded")
    return {"task": task(ctx, tid)}


def seg_kill(page, ctx, r):
    wait_idle(ctx)
    r.start()
    page.goto(BASE + "/ui/new", wait_until="load")
    page.wait_for_timeout(1000)
    click(page, "text=Long task (try the kill switch)")
    page.wait_for_timeout(1200)
    r.mark("preset")
    click(page, "#submit-btn")
    page.wait_for_url("**/ui/tasks/*")
    tid = page.url.rsplit("/", 1)[1]
    print("  task", tid, flush=True)
    r.mark("task_page")
    scroll_to(page, "h1", top=56)
    wait_for(page, ctx, tid, lambda d: d["status"] == "running", "the running step")
    r.mark("running")
    page.wait_for_timeout(7000)
    page.on("dialog", lambda dlg: dlg.accept())
    point(page, "#kill-btn")
    r.mark("press")
    page.locator("#kill-btn").click()
    r.mark("pressed")
    wait_for(
        page,
        ctx,
        tid,
        lambda d: d["status"] in DONE and all(s.get("destroyed") for s in d["sandboxes"]),
        "the kill",
        limit=120,
    )
    r.mark("killed")
    page.wait_for_timeout(2200)
    scroll_h2(page, "Sandbox VMs")
    r.mark("vm_404")
    page.wait_for_timeout(4000)
    page.evaluate("document.getElementById('events').lastElementChild.scrollIntoView({behavior:'smooth',block:'end'})")
    page.wait_for_timeout(1200)
    r.mark("events")
    page.wait_for_timeout(4000)
    return {"task": task(ctx, tid)}


SEGMENTS = {
    "home": seg_home,
    "limits": seg_limits,
    "evidence": seg_evidence,
    "github": seg_github,
    "card": seg_card,
    "normal": seg_normal,
    "attack": seg_attack,
    "kill": seg_kill,
}


def main():
    out = pathlib.Path(sys.argv[1])
    for name in sys.argv[2:]:
        print("segment", name, flush=True)
        with sync_playwright() as pw:
            browser, ctx, page = new_page(pw)
            r = Recorder(page, out / name)
            try:
                extra = SEGMENTS[name](page, ctx, r) or {}
            except BaseException:
                page.screenshot(path=str(out / f"{name}-failed.png"))
                if r.cdp:
                    r.stop({"failed": True})
                raise
            if r.cdp:
                r.stop(extra)
            else:
                (r.out / "index.json").write_text(json.dumps({"frames": r.frames, "marks": {}}), encoding="utf-8")
            print(f"  {len(r.frames)} frames", json.dumps(r.marks), flush=True)
            browser.close()


if __name__ == "__main__":
    main()
