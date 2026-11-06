#!/usr/bin/env python3
"""Builds the Ashproof demo video from real recordings of the public demo and a real offline check.

    python docs/video/capture.py <cap> home limits evidence github card normal attack kill
    python docs/video/build.py <cap> <out dir> [--plan]

Pipeline:
  1. term: runs the receipt checks for real in <cap>/term and keeps the text unedited. Nothing on the terminal
     screen comes from anywhere else.
  2. edge-tts speaks each scene and returns word timings. A clip or a box names the phrase it starts on, so the
     picture follows the voice instead of a hand-set clock.
  3. Each output frame is the recorded frame for its source time, with a highlight box, a caption or a speed label on
     top. A wait that is shortened gets a label saying so, computed from the times, not typed in.
  4. ffmpeg encodes H.264, places each narration at its scene time, muxes AAC, and makes a smaller copy if the file
     is over 50 MB.

Requires ffmpeg and ffprobe on PATH, `pip install edge-tts pillow`, and the Windows fonts named below.
"""
import asyncio
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
W, H, FPS = 1920, 1080, 30
FONT_DIR = pathlib.Path(os.environ.get("FONT_DIR", "C:/Windows/Fonts"))
UI = str(FONT_DIR / "seguisb.ttf")
MONO, MONO_B = str(FONT_DIR / "consola.ttf"), str(FONT_DIR / "consolab.ttf")
EMBER, STAMP, INK = (240, 163, 60), (248, 81, 73), (42, 26, 2)
BOX_COLORS = {"ember": EMBER, "red": STAMP, "green": (63, 185, 80)}
DISSOLVE = 0.25
LABEL_FROM = 1.5  # a clip played this much faster than real time, or more, gets a speed label


def run(cmd, **kw):
    print("$", " ".join(str(c) for c in cmd)[:220], flush=True)
    subprocess.run([str(c) for c in cmd], check=True, timeout=kw.pop("timeout", 1500), **kw)


def duration(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], timeout=30)
    return float(out.decode().strip())


# ---- voice ----

async def tts(text, voice, rate, mp3):
    import edge_tts
    words = []
    com = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    with open(mp3, "wb") as f:
        async for chunk in com.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                words.append({"t": chunk["offset"] / 1e7, "d": chunk["duration"] / 1e7, "w": chunk["text"]})
    return words


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def phrase_time(scene, phrase):
    joined, owner = "", []
    for i, w in enumerate(scene["words"]):
        n = norm(w["w"])
        joined += n
        owner += [i] * len(n)
    at = joined.find(norm(phrase))
    if at < 0:
        sys.exit(f"phrase not spoken in {scene['id']}: {phrase!r}\nspoken: {' '.join(w['w'] for w in scene['words'])}")
    return scene["voice_at"] + scene["words"][owner[at]]["t"]


def voice_scene(scene, sb, tmp):
    text = scene.get("tts", scene["narration"])
    key = hashlib.sha256(f"{sb['voice']}|{sb['rate']}|{text}".encode()).hexdigest()[:16]
    mp3, meta = tmp / f"{key}.mp3", tmp / f"{key}.json"
    if not (mp3.exists() and meta.exists()):
        meta.write_text(json.dumps(asyncio.run(tts(text, sb["voice"], sb["rate"], mp3))), encoding="utf-8")
    scene["mp3"], scene["words"] = mp3, json.loads(meta.read_text(encoding="utf-8"))


def plan(sb, tmp):
    """Scene start times, then the output window of every clip and the time of every box."""
    t = 0.0
    for s in sb["scenes"]:
        voice_scene(s, sb, tmp)
        s["start"] = t
        s["voice_at"] = t + s.get("lead", 0.2)
        last = s["words"][-1]
        s["voice_end"] = s["voice_at"] + last["t"] + last["d"]
        s["end"] = s["voice_end"] + s.get("tail", 0.45)
        clips = s["clips"]
        for i, c in enumerate(clips):
            c["t0"] = s["start"] if i == 0 else phrase_time(s, c["on"]) - 0.1
        for i, c in enumerate(clips):
            c["t1"] = clips[i + 1]["t0"] if i + 1 < len(clips) else s["end"]
            if "seg" not in c:
                continue
            window = c["t1"] - c["t0"]
            span = c["to"] - c["from"]
            c["speed"] = span / window if c.get("fit") else 1.0
            if c["speed"] >= LABEL_FROM and not c.get("nolabel"):  # nolabel: a page scroll, not a wait
                what = c.get("what", "Wait")
                c["label"] = f"{what}: {span:.0f} s of real time, sped up {c['speed']:.0f}x"
            for b in c.get("boxes", []):
                b["t"] = phrase_time(s, b["on"]) - 0.1 if b.get("on") else c["t0"]
            for z in [c.get("zoom")] if c.get("zoom") else []:
                z["t"] = phrase_time(s, z["on"]) - 0.1 if z.get("on") else c["t0"]
        for b in s.get("term", []):
            b["t"] = phrase_time(s, b["on"]) - 0.1 if b.get("on") else s["start"]
        t = s["end"]
    return t


# ---- recorded frames ----

class Segment:
    def __init__(self, base, name):
        self.dir = base / name
        idx = json.loads((self.dir / "index.json").read_text(encoding="utf-8"))
        self.frames = idx["frames"]
        self.times = [f["t"] for f in self.frames]
        self.cache = {}

    def at(self, t):
        import bisect
        i = max(0, bisect.bisect_right(self.times, t) - 1)
        return i

    def image(self, i):
        if i not in self.cache:
            if len(self.cache) > 8:
                self.cache.clear()
            im = Image.open(self.dir / self.frames[i]["name"]).convert("RGB")
            if im.size != (W, H):  # the window is one row short at this scale; repeat the edge, do not resample text
                full = Image.new("RGB", (W, H))
                full.paste(im, (0, 0))
                if im.size[1] < H:
                    full.paste(im.crop((0, im.size[1] - 1, W, im.size[1])), (0, im.size[1]))
                im = full
            self.cache[i] = im
        return self.cache[i]


# ---- overlays ----

def fit_text(draw, text, font, width):
    words, lines, line = text.split(), [], ""
    for w in words:
        trial = (line + " " + w).strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            lines.append(line)
            line = w
    lines.append(line)
    return lines


def caption(img, text, top=False):
    """A dark band with white text, at the bottom unless the bottom holds what the viewer should read."""
    d = ImageDraw.Draw(img, "RGBA")
    font = ImageFont.truetype(UI, 34)
    lines = fit_text(d, text, font, W - 240)
    h = 46 * len(lines) + 26
    y = 26 if top else H - h - 26
    widest = max(d.textlength(x, font=font) for x in lines)
    x0 = (W - widest) / 2 - 28
    d.rounded_rectangle([x0, y, W - x0, y + h], 10, fill=(8, 10, 14, 225))
    for i, line in enumerate(lines):
        d.text(((W - d.textlength(line, font=font)) / 2, y + 11 + 46 * i), line, font=font, fill=(255, 255, 255, 255))


def speed_label(img, text):
    d = ImageDraw.Draw(img, "RGBA")
    font = ImageFont.truetype(UI, 32)
    w = d.textlength(text, font=font)
    x, y = W - w - 64, 20
    d.rounded_rectangle([x, y, x + w + 40, y + 58], 8, fill=EMBER + (245,))
    d.text((x + 20, y + 8), text, font=font, fill=INK + (255,))


def ease(k):
    k = max(0.0, min(1.0, k))
    return k * k * (3 - 2 * k)


def view_rect(zoom, t):
    if not zoom:
        return (0.0, 0.0, float(W), float(H))
    k = ease((t - zoom["t"]) / 0.6)
    x0, y0, x1 = zoom["rect"][:3]
    y1 = y0 + (x1 - x0) * H / W
    return (x0 * k, y0 * k, W + (x1 - W) * k, H + (y1 - H) * k)


def apply_view(img, rect):
    if rect == (0.0, 0.0, float(W), float(H)):
        return img
    return img.resize((W, H), Image.LANCZOS, box=rect)


def draw_box(img, b, rect, t):
    color = BOX_COLORS[b.get("color", "ember")]
    alpha = int(255 * ease((t - b["t"]) / 0.2))
    sx, sy = W / (rect[2] - rect[0]), H / (rect[3] - rect[1])
    x0, y0, x1, y1 = b["rect"]
    r = [(x0 - rect[0]) * sx, (y0 - rect[1]) * sy, (x1 - rect[0]) * sx, (y1 - rect[1]) * sy]
    ImageDraw.Draw(img, "RGBA").rounded_rectangle(r, 8, outline=color + (alpha,), width=5)


# ---- terminal ----

TERM_SIZE, TERM_ROW, TERM_X, TERM_Y = 30, 41, 58, 104


class Terminal:
    """Real command output laid out in rows. Colour is the only thing added, and it depends on the text alone."""

    def __init__(self, blocks):
        self.font = ImageFont.truetype(MONO, TERM_SIZE)
        self.bold = ImageFont.truetype(MONO_B, TERM_SIZE)
        self.adv = self.font.getlength("M")
        self.cols = int((W - 2 * TERM_X) // self.adv)
        self.blocks = blocks

    def wrap(self, line):
        rows = []
        while len(line) > self.cols:
            cut = line.rfind(" ", 1, self.cols)
            cut = cut if cut > 0 else self.cols
            rows.append(line[:cut])
            line = "  " + line[cut:].lstrip()
        rows.append(line)
        return rows

    @staticmethod
    def color(row):
        if row.startswith(("OK:", "signature: valid", "public log: found")):
            return (126, 231, 135)
        if row.startswith(("TAMPERED", "  - ")):
            return (255, 123, 114)
        if row.startswith(("note:", "      A copy")):
            return (242, 190, 70)
        return (230, 230, 230)

    def render(self, shown):
        """`shown` is a list of (block index, typed fraction, output visible)."""
        img = Image.new("RGB", (W, H), (11, 14, 20))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([26, 22, W - 26, H - 22], 12, fill=(17, 21, 28))
        d.rounded_rectangle([26, 22, W - 26, 84], 12, fill=(27, 33, 44))
        d.rectangle([26, 70, W - 26, 84], fill=(27, 33, 44))
        for i, c in enumerate(((255, 95, 87), (254, 188, 46), (40, 200, 64))):
            d.ellipse([52 + 34 * i, 43, 72 + 34 * i, 63], fill=c)
        title = "receipt.json downloaded from task d6aa0eff8681, offline, Python only"
        d.text(((W - self.font.getlength(title)) / 2, 36), title, font=self.font, fill=(154, 164, 178))
        y = TERM_Y
        for i, typed, out in shown:
            b = self.blocks[i]
            cmd = b["show"][: int(len(b["show"]) * typed + 0.5)]
            for j, row in enumerate(self.wrap("$ " + cmd)):
                if j == 0:
                    d.text((TERM_X, y), "$", font=self.bold, fill=(126, 231, 135))
                    d.text((TERM_X + 2 * self.adv, y), row[2:], font=self.bold, fill=(255, 255, 255))
                else:
                    d.text((TERM_X, y), row, font=self.bold, fill=(255, 255, 255))
                y += TERM_ROW
            if out:
                for line in b["text"].rstrip("\n").split("\n"):
                    if line == "":
                        continue
                    for row in self.wrap(line):
                        d.text((TERM_X, y), row, font=self.font, fill=self.color(row))
                        y += TERM_ROW
            y += 6
        return img


def capture_terminal(sb, cap):
    """Runs the checks in a folder that holds only the verifier, the receipt and two copies of the log."""
    term = cap / "term"
    term.mkdir(exist_ok=True)
    shutil.copy(next(cap.glob("receipt-*.json")), term / "receipt.json")
    shutil.copy(cap / "anchors.jsonl", term / "anchors.jsonl")
    shutil.copy(ROOT / "brz/audit/offline_verify.py", term / "offline_verify.py")
    shutil.copy(ROOT / "docs/evidence/vultr-2026-11-06/anchors-checkpoint.jsonl", term / "anchors-checkpoint.jsonl")
    for extra in ("tampered.json", "session.txt"):
        (term / extra).unlink(missing_ok=True)
    blocks = []
    for spec in sb["terminal"]:
        cmd = [sys.executable if c == "{python}" else c for c in spec["run"]]
        p = subprocess.run(cmd, cwd=term, capture_output=True, text=True, encoding="utf-8", timeout=60)
        if p.returncode != spec.get("exit", 0):
            sys.exit(f"{spec['show']} exited {p.returncode}:\n{p.stdout}{p.stderr}")
        blocks.append({"show": spec["show"], "text": p.stdout})
    (cap / "term-session.txt").write_text("".join(f"$ {b['show']}\n{b['text']}" for b in blocks), encoding="utf-8", newline="\n")
    return blocks


# ---- render ----

def clip_at(scene, t):
    clips = scene["clips"]
    for c in reversed(clips):
        if t >= c["t0"]:
            return c
    return clips[0]


def scene_frame(s, t, segs, term):
    """Returns the image for output time t, and a key that is equal when two frames would be identical."""
    if "term" in s:
        shown = []
        for b in s["term"]:
            if t < b["t"]:
                break
            typed = min(1.0, (t - b["t"]) / b.get("type_s", 0.7))
            shown.append((b["block"], typed, typed >= 1.0))
        key = ("term", s["id"], tuple(shown))
        return (lambda: term.render(shown)), key, None
    c = clip_at(s, t)
    seg = segs[c["seg"]]
    src = c["from"] + (t - c["t0"]) * c["speed"]
    i = seg.at(min(src, c["to"]))
    rect = view_rect(c.get("zoom"), t)
    boxes = [b for b in c.get("boxes", []) if t >= b["t"]]
    key = (c["seg"], i, rect, tuple((b["t"], int(min(1.0, (t - b["t"]) / 0.2) * 8)) for b in boxes), id(c))

    def make():
        img = apply_view(seg.image(i), rect).copy()
        for b in boxes:
            draw_box(img, b, rect, t)
        if c.get("label"):
            speed_label(img, c["label"])
        if c.get("caption"):
            caption(img, c["caption"], c.get("caption_top", False))
        return img
    return make, key, c


def render(sb, total, cap, video):
    segs = {n: Segment(cap, n) for n in {c["seg"] for s in sb["scenes"] for c in s["clips"] if "seg" in c}}
    term = Terminal(sb["_blocks"])
    enc = subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p", "-g", "60", str(video)],
        stdin=subprocess.PIPE,
    )
    n = int(total * FPS)
    last_key, last_img, prev_clip, prev_end = None, None, None, None
    si = 0
    scenes = sb["scenes"]
    for f in range(n):
        t = f / FPS
        while si + 1 < len(scenes) and t >= scenes[si + 1]["start"]:
            si += 1
        s = scenes[si]
        make, key, c = scene_frame(s, t, segs, term)
        unit = c if c is not None else s
        if unit is not prev_clip:
            prev_end = last_img
            prev_clip = unit
            unit_start = c["t0"] if c is not None else s["start"]
        if key != last_key or last_img is None:
            last_img = make()
            last_key = key
        out = last_img
        since = t - unit_start
        if prev_end is not None and since < DISSOLVE:
            out = Image.blend(prev_end, last_img, ease(since / DISSOLVE))
        enc.stdin.write(out.tobytes())
        if f % 300 == 0:
            print(f"  frame {f}/{n}", flush=True)
    enc.stdin.close()
    if enc.wait(timeout=600) != 0:
        sys.exit("ffmpeg failed")


def mix_audio(sb, total, wav):
    inputs, parts = [], []
    for i, s in enumerate(sb["scenes"]):
        inputs += ["-i", str(s["mp3"])]
        ms = int(s["voice_at"] * 1000)
        parts.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(sb["scenes"])))
    filt = ";".join(parts) + f";{mix}amix=inputs={len(sb['scenes'])}:normalize=0:duration=longest,apad,atrim=0:{total:.3f},loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000"
    run(["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", filt, "-ac", "2", "-ar", "48000", wav])


def main():
    cap, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    only_plan = "--plan" in sys.argv
    sb = json.loads((HERE / "storyboard.json").read_text(encoding="utf-8"))
    tmp = cap / "build"
    tmp.mkdir(exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    sb["_blocks"] = capture_terminal(sb, cap)
    total = plan(sb, tmp)
    words = 0
    for s in sb["scenes"]:
        words += len(s["narration"].split())
        print(f"{s['id']:<12} {s['start']:6.1f} -> {s['end']:6.1f}  voice ends {s['voice_end']:6.1f}")
        for c in s["clips"]:
            if "seg" in c:
                print(f"    {c['seg']:<9} {c['from']:7.2f}-{c['to']:7.2f} at {c['t0']:6.1f}-{c['t1']:6.1f} speed {c['speed']:.2f} {c.get('label', '')}")
    print(f"total {total:.1f} s, {words} words")
    times = {s["id"]: [round(s["start"], 2), round(s["end"], 2)] for s in sb["scenes"]}
    (tmp / "timeline.json").write_text(json.dumps(times, indent=1), encoding="utf-8")
    if only_plan:
        return
    video, wav = tmp / "video.mp4", tmp / "voice.wav"
    only = os.environ.get("REUSE_VIDEO") and video.exists()
    if not only:
        render(sb, total, cap, video)
    mix_audio(sb, total, wav)
    final = out / sb["output"]
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", final])
    mb = final.stat().st_size / 1e6
    print(f"{final}: {duration(final):.1f} s, {mb:.1f} MB")
    if mb > 50:
        small = out / sb["output_small"]
        kbps = int(48 * 8000 / duration(final)) - 128
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", final, "-c:v", "libx264", "-preset", "slow", "-b:v", f"{kbps}k", "-maxrate", f"{kbps * 2}k", "-bufsize", f"{kbps * 4}k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", small])
        print(f"{small}: {small.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
