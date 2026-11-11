"""Records a real Chrome page with Playwright: a CDP screencast, one JPEG per painted frame, with its capture time.

Nothing is drawn into the page except a small mouse pointer, because headless Chrome has none and a viewer needs to see
what was clicked. The pointer has `pointer-events: none`, so it cannot change what a click does.
"""

from __future__ import annotations

import base64
import json
import pathlib
import threading
import time

BASE = "https://45-76-6-117.sslip.io"
SCALE = 1.5  # a 1280x720 CSS window at this scale gives 1920x1080 frames, with text a viewer can read

POINTER_JS = r"""
(() => {
  const add = () => {
    if (document.getElementById("__pointer")) return;
    const p = document.createElement("div");
    p.id = "__pointer";
    p.style.cssText = "position:fixed;left:-40px;top:-40px;width:26px;height:26px;z-index:2147483647;pointer-events:none;" +
      "transition:left .45s cubic-bezier(.3,.7,.3,1),top .45s cubic-bezier(.3,.7,.3,1)";
    p.innerHTML = '<svg width="26" height="26" viewBox="0 0 26 26"><path d="M3 2 L3 21 L8.2 16.4 L11.8 24 L15.2 22.4 L11.6 15 L18.6 15 Z" fill="#fff" stroke="#000" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    document.documentElement.appendChild(p);
    const at = sessionStorage.getItem("__pointer");
    if (at) { const [x, y] = at.split(","); p.style.transition = "none"; p.style.left = x + "px"; p.style.top = y + "px"; requestAnimationFrame(() => { p.style.transition = "left .45s cubic-bezier(.3,.7,.3,1),top .45s cubic-bezier(.3,.7,.3,1)"; }); }
  };
  window.__pointTo = (x, y) => { add(); const p = document.getElementById("__pointer"); p.style.left = x + "px"; p.style.top = y + "px"; sessionStorage.setItem("__pointer", x + "," + y); };
  if (document.documentElement) add();
  document.addEventListener("DOMContentLoaded", add);
})();
"""


class Recorder:
    """Saves frames to <out>/f000001.jpg and an index with the time of each. Marks name moments for the storyboard."""

    def __init__(self, page, out: pathlib.Path, quality: int = 90):
        self.page, self.out, self.quality = page, out, quality
        self.out.mkdir(parents=True, exist_ok=True)
        self.frames: list[dict] = []
        self.marks: dict[str, float] = {}
        self.t0 = 0.0
        self.lock = threading.Lock()
        self.cdp = None

    def _on_frame(self, ev):
        with self.lock:
            n = len(self.frames) + 1
            name = f"f{n:06d}.jpg"
            self.frames.append({"name": name, "t": time.time() - self.t0})
        (self.out / name).write_bytes(base64.b64decode(ev["data"]))
        try:
            self.cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
        except Exception:
            pass

    def start(self):
        self.t0 = time.time()
        self.cdp = self.page.context.new_cdp_session(self.page)
        self.cdp.on("Page.screencastFrame", self._on_frame)
        self.cdp.send(
            "Page.startScreencast",
            {"format": "jpeg", "quality": self.quality, "maxWidth": 1920, "maxHeight": 1080, "everyNthFrame": 1},
        )

    def mark(self, name: str) -> float:
        t = time.time() - self.t0
        self.marks[name] = round(t, 2)
        print(f"  [{t:7.2f}] {name}", flush=True)
        return t

    def stop(self, extra: dict | None = None):
        self.page.wait_for_timeout(300)
        self.cdp.send("Page.stopScreencast")
        data = {"frames": self.frames, "marks": self.marks, "end": time.time() - self.t0, **(extra or {})}
        (self.out / "index.json").write_text(json.dumps(data, indent=0), encoding="utf-8")


def new_page(pw):
    # A real device scale factor, not an emulated one: an emulated factor makes the screencast return 1280x720 frames.
    browser = pw.chromium.launch(
        channel="chrome",
        headless=True,
        args=[f"--force-device-scale-factor={SCALE}", "--window-size=1296,814", "--hide-scrollbars"],
    )
    ctx = browser.new_context(no_viewport=True, color_scheme="dark", accept_downloads=True)
    ctx.add_init_script(POINTER_JS)
    page = ctx.new_page()
    page.set_default_timeout(30000)
    return browser, ctx, page


def point(page, selector_or_xy, pause: float = 0.55):
    """Moves the visible pointer to an element or a point and returns the point."""
    if isinstance(selector_or_xy, tuple):
        x, y = selector_or_xy
    else:
        box = page.locator(selector_or_xy).first.bounding_box()
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.evaluate("([x, y]) => window.__pointTo(x, y)", [x, y])
    page.mouse.move(x, y)
    page.wait_for_timeout(int(pause * 1000))
    return x, y


def click(page, selector):
    point(page, selector)
    page.locator(selector).first.click()


def scroll_to(page, selector, top: int = 64, ms: int = 900):
    """Smooth scroll that puts an element `top` CSS pixels below the window's top edge, then waits for it to end."""
    page.evaluate(
        """([sel, top]) => { const e = document.querySelector(sel); if (!e) return;
           window.scrollTo({ top: e.getBoundingClientRect().top + scrollY - top, behavior: "smooth" }); }""",
        [selector, top],
    )
    page.wait_for_timeout(ms)
