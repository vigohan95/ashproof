"""Server-rendered UI (Jinja2 + a little vanilla JS, no build step).

    /  and /ui               home: what this is, a replay of a real recorded task, a live run
    /ui/tasks                task list
    /ui/evidence             attack results, kill switch and reliability numbers from real runs
    /ui/verify               check any receipt file in the browser
    /ui/new                  new task form (posts JSON to /tasks from the browser)
    /ui/tasks/{id}           live task page: polls GET /tasks/{id} every 2 s
    /ui/tasks/{id}/receipt   receipt: verification result, rendered Markdown, JSON download

The UI only talks to the public JSON API, so everything a judge clicks is something the API
can do too. Markdown rendering covers exactly the subset the receipt emits (headings, bullets,
tables, bold, inline code) - no third-party Markdown dependency.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from brz import __version__

from .presets import DEMO_CSV, PRESETS, short_title

router = APIRouter(prefix="/ui", include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
DATA = Path(__file__).parent / "data"

_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_CHECK = re.compile(r"^\[( |x)\] ")


def _inline(text: str) -> str:
    out = html.escape(text, quote=False)
    out = _INLINE_CODE.sub(r"<code>\1</code>", out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    return out


def markdown_to_html(md: str) -> str:
    """Tiny renderer for the receipt's Markdown subset. Escapes everything first."""
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    list_depth = 0

    def close_lists() -> None:
        nonlocal list_depth
        while list_depth:
            out.append("</ul>")
            list_depth -= 1

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            close_lists()
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            close_lists()
            header = [c.strip() for c in stripped.strip("|").split("|")]
            out.append(
                "<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in header) + "</tr></thead><tbody>"
            )
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                row_class = ' class="deny"' if any("DENIED" in c or "BROKEN" in c for c in cells) else ""
                out.append(f"<tr{row_class}>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            close_lists()
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2))}</h{level}>")
            i += 1
            continue
        m = re.match(r"^(\s*)-\s+(.*)$", line)
        if m:
            depth = len(m.group(1)) // 2 + 1
            while list_depth < depth:
                out.append("<ul>")
                list_depth += 1
            while list_depth > depth:
                out.append("</ul>")
                list_depth -= 1
            item = m.group(2)
            cm = _CHECK.match(item)
            if cm:
                mark = "&#10003;" if cm.group(1) == "x" else "&#10007;"
                cls = "ok" if cm.group(1) == "x" else "bad"
                item = f'<span class="{cls}">{mark}</span> ' + _inline(item[4:])
            else:
                item = _inline(item)
            out.append(f"<li>{item}</li>")
            i += 1
            continue
        close_lists()
        out.append(f"<p>{_inline(stripped)}</p>")
        i += 1
    close_lists()
    return "\n".join(out)


def _ctx(request: Request, **extra):
    deps = request.app.state.deps
    return {
        "request": request,
        "version": __version__,
        "mode": deps.mode,
        "provider": deps.backend.provider,
        "inner_isolation": deps.backend.inner_isolation,
        "demo": request.app.state.guard.status(),
        **extra,
    }


def _load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def _pinned(store, featured: dict) -> list[dict]:
    out = []
    for item in featured["pinned"]:
        state = store.tasks.get(item["id"])
        if state is not None:
            out.append({**item, "status": state.status, "total_usd": state.cost.total_usd})
    return out


@router.get("", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    store = request.app.state.store
    featured = _load("featured.json")
    replay = store.tasks.get(featured["replay"])
    return templates.TemplateResponse(
        request,
        "home.html",
        _ctx(
            request,
            replay_id=replay.id if replay else None,
            replay_when=replay.created_at.strftime("%Y-%m-%d %H:%M UTC") if replay else "",
            pinned=_pinned(store, featured),
            evidence=_load("evidence.json"),
            presets=PRESETS,
            demo_csv=DEMO_CSV,
        ),
    )


@router.get("/verify", response_class=HTMLResponse)
async def verify_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "verify.html", _ctx(request))


@router.get("/evidence", response_class=HTMLResponse)
async def evidence_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "evidence.html", _ctx(request, evidence=_load("evidence.json")))


@router.get("/tasks", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    store = request.app.state.store
    tasks = sorted(store.tasks.values(), key=lambda s: s.created_at, reverse=True)
    rows = [
        {
            "id": s.id,
            "status": s.status,
            "created_at": s.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "task": short_title(s.request.task),
            "total_usd": s.cost.total_usd,
            "vms": len(s.sandboxes),
            "destroyed": all(h.proof and h.proof.destroyed for h in s.sandboxes) if s.sandboxes else None,
            "receipt": s.receipt is not None,
        }
        for s in tasks
    ]
    return templates.TemplateResponse(request, "index.html", _ctx(request, tasks=rows))


@router.get("/new", response_class=HTMLResponse)
async def new_task(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "new.html", _ctx(request, presets=PRESETS, demo_csv=DEMO_CSV))


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
async def task_page(request: Request, task_id: str) -> HTMLResponse:
    store = request.app.state.store
    state = store.get(task_id)
    return templates.TemplateResponse(request, "task.html", _ctx(request, task_id=task_id, state=state))


@router.get("/tasks/{task_id}/receipt", response_class=HTMLResponse)
async def receipt_page(request: Request, task_id: str) -> HTMLResponse:
    store = request.app.state.store
    state = store.get(task_id)
    if state.receipt is None:
        raise HTTPException(status_code=409, detail=f"receipt not ready (task is {state.status})")
    receipt = state.receipt
    ok, problems = receipt.verify()
    return templates.TemplateResponse(
        request,
        "receipt.html",
        _ctx(
            request,
            task_id=task_id,
            receipt=receipt,
            verify_ok=ok,
            verify_problems=problems,
            receipt_html=markdown_to_html(receipt.to_markdown()),
        ),
    )
