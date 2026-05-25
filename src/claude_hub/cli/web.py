"""`claude-hub web` — local web UI for spawned sessions.

Reads ~/.claude-hub/spawns.json and exposes a tiny HTTP server that lists,
stops, and cleans tracked spawns. Also runs an auto-titler that synthesizes
an `ai-title` record for short-lived spawned sessions so they show up in
Claude's `--resume` picker.

Serves on 127.0.0.1:8765 by default.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

STATE_DIR = Path.home() / ".claude-hub"
SPAWNS_FILE = STATE_DIR / "spawns.json"
PROJECTS_ROOT = Path.home() / ".claude" / "projects"
STOP_GRACE_SECONDS = 5.0
TITLER_INTERVAL_SECONDS = 10.0
TITLE_MAX_LEN = 60


def _load_spawns() -> list[dict]:
    if not SPAWNS_FILE.exists():
        return []
    try:
        return json.loads(SPAWNS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_spawns(entries: list[dict]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SPAWNS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    tmp.replace(SPAWNS_FILE)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError, OSError):
        return False
    # Zombies still answer signal 0 but cannot be killed; treat them as dead.
    try:
        r = subprocess.run(
            ["ps", "-o", "state=", "-p", str(pid)],
            capture_output=True, text=True, timeout=2,
        )
        if r.stdout.strip().startswith("Z"):
            return False
    except (OSError, subprocess.SubprocessError):
        pass
    return True


def _kill_pid(pid: int) -> bool:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    deadline = time.monotonic() + STOP_GRACE_SECONDS
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    time.sleep(0.2)
    return not _pid_alive(pid)


def _humanize_started(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    now = datetime.now(timezone.utc)
    delta = now - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        rel = f"{secs}s ago"
    elif secs < 3600:
        rel = f"{secs // 60}m ago"
    elif secs < 86400:
        rel = f"{secs // 3600}h ago"
    else:
        rel = f"{secs // 86400}d ago"
    return f"{dt.astimezone().strftime('%H:%M')} ({rel})"


def _encode_cwd(path: str) -> str:
    """Match Claude's encoding for ~/.claude/projects/<encoded-cwd>/."""
    return path.replace("/", "-")


def _latest_jsonl(cwd: str) -> Path | None:
    encoded = _encode_cwd(cwd)
    folder = PROJECTS_ROOT / encoded
    if not folder.is_dir():
        return None
    jsonls = list(folder.glob("*.jsonl"))
    if not jsonls:
        return None
    return max(jsonls, key=lambda p: p.stat().st_mtime)


def _latest_session_id(cwd: str) -> str | None:
    jsonl = _latest_jsonl(cwd)
    if not jsonl:
        return None
    try:
        with open(jsonl, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    sid = json.loads(line).get("sessionId")
                except json.JSONDecodeError:
                    continue
                if sid:
                    return sid
    except OSError:
        return None
    return None


def _sessions_payload() -> list[dict]:
    entries = _load_spawns()
    home = str(Path.home())
    out = []
    for e in entries:
        path = e.get("path", "")
        display_path = path.replace(home, "~", 1) if path.startswith(home) else path
        session_id = _latest_session_id(path)
        resume_cmd = (
            f"cd {path} && claude --resume {session_id}" if session_id else None
        )
        out.append({
            "name": e.get("name"),
            "path": path,
            "display_path": display_path,
            "pid": e.get("pid"),
            "env_url": e.get("env_url"),
            "started_at": e.get("started_at"),
            "started_human": _humanize_started(e.get("started_at", "")),
            "alive": _pid_alive(int(e.get("pid", 0))),
            "session_id": session_id,
            "resume_cmd": resume_cmd,
        })
    return out


def _stop_session(name: str) -> dict:
    entries = _load_spawns()
    target = next((e for e in entries if e.get("name") == name), None)
    if target is None:
        return {"ok": False, "error": "unknown name"}
    pid = int(target.get("pid", 0))
    if _pid_alive(pid):
        killed = _kill_pid(pid)
        if not killed:
            return {"ok": False, "error": "failed to kill process"}
    remaining = [e for e in entries if e.get("name") != name]
    _save_spawns(remaining)
    return {"ok": True}


def _clean_session(name: str) -> dict:
    entries = _load_spawns()
    if not any(e.get("name") == name for e in entries):
        return {"ok": False, "error": "unknown name"}
    remaining = [e for e in entries if e.get("name") != name]
    _save_spawns(remaining)
    return {"ok": True}


# --- Auto-titler ---------------------------------------------------------
# Claude's `--resume` picker hides JSONLs that lack an `ai-title` entry.
# Short-lived spawned sessions die before Claude's background titler runs,
# so we synthesize one from the first user prompt. Runs in a daemon thread.


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            c.get("text", "") for c in content
            if isinstance(c, dict) and c.get("type") == "text"
        )
    return ""


def _derive_title(jsonl: Path) -> tuple[str | None, str | None]:
    """Return (sessionId, title) for the file, or (None, None) if not ready.

    Ready means: file has ai-title? -> skip; otherwise needs at least one
    user message and one assistant message to title.
    """
    has_user = False
    has_assistant = False
    first_user_text = ""
    session_id: str | None = None
    try:
        with open(jsonl, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = d.get("type")
                if not session_id:
                    session_id = d.get("sessionId")
                if t == "ai-title":
                    return (None, None)  # already titled
                if t == "user" and not has_user:
                    msg = d.get("message") or {}
                    if isinstance(msg, dict):
                        text = _extract_text(msg.get("content", ""))
                        if text.strip():
                            first_user_text = text.strip()
                            has_user = True
                elif t == "assistant":
                    has_assistant = True
    except OSError:
        return (None, None)
    if not (has_user and has_assistant and session_id):
        return (None, None)
    title = first_user_text.replace("\n", " ").strip()
    if len(title) > TITLE_MAX_LEN:
        title = title[: TITLE_MAX_LEN - 1].rstrip() + "…"
    return (session_id, title)


def _append_ai_title(jsonl: Path, session_id: str, title: str) -> bool:
    record = {"type": "ai-title", "aiTitle": title, "sessionId": session_id}
    try:
        with open(jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def _title_tracked_spawns() -> int:
    """Process every tracked spawn. Returns count of titles added."""
    added = 0
    for spawn in _load_spawns():
        cwd = spawn.get("path") or ""
        if not cwd:
            continue
        jsonl = _latest_jsonl(cwd)
        if not jsonl:
            continue
        sid, title = _derive_title(jsonl)
        if sid and title:
            if _append_ai_title(jsonl, sid, title):
                added += 1
                print(f"[titler] {jsonl.name} ← {title!r}", flush=True)
    return added


def _titler_loop(stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            _title_tracked_spawns()
        except Exception as e:  # don't crash the thread
            print(f"[titler] error: {e}", flush=True)
        stop_event.wait(TITLER_INTERVAL_SECONDS)


# --- HTML ----------------------------------------------------------------

INDEX_HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>claude-hub sessions</title>
<style>
  :root {
    --bg: #0f1115;
    --panel: #161922;
    --border: #262a36;
    --text: #e6e8ee;
    --muted: #8a8f9d;
    --accent: #6ea8fe;
    --alive: #4ade80;
    --dead: #6b7280;
    --danger: #ef4444;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 24px;
    background: var(--bg); color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif;
    font-size: 13px;
  }
  header { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; }
  h1 { font-size: 16px; font-weight: 600; margin: 0; letter-spacing: -0.01em; }
  .spacer { flex: 1; }
  button {
    background: var(--panel); color: var(--text);
    border: 1px solid var(--border); border-radius: 6px;
    padding: 6px 12px; font: inherit; cursor: pointer;
  }
  button:hover { border-color: #3a3f4e; }
  button.danger { color: var(--danger); border-color: #3a2026; }
  button.danger:hover { background: #2a1418; }
  label { color: var(--muted); display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
  table { width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
  th, td { text-align: left; padding: 10px 14px; border-bottom: 1px solid var(--border); }
  th { font-weight: 500; color: var(--muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em; }
  tr:last-child td { border-bottom: none; }
  .name { font-weight: 600; }
  .path { color: var(--muted); font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12px; }
  .pid  { color: var(--muted); font-family: ui-monospace, "SF Mono", Menlo, monospace; }
  .state { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; }
  .dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
  .dot.alive { background: var(--alive); box-shadow: 0 0 8px var(--alive); }
  .dot.dead  { background: var(--dead); }
  .empty { text-align: center; padding: 40px; color: var(--muted); }
  a { color: var(--accent); text-decoration: none; }
  a:hover { text-decoration: underline; }
  .actions { display: flex; gap: 6px; justify-content: flex-end; }
  .sid { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 12px; color: var(--muted); }
  .copy { font-size: 11px; padding: 4px 8px; }
</style>
</head>
<body>
<header>
  <h1>claude-hub sessions</h1>
  <span class="spacer"></span>
  <span id="status" style="color: var(--muted)"></span>
  <label><input type="checkbox" id="auto" checked> auto 5s</label>
  <button id="refresh">⟳ Refresh</button>
</header>
<div id="root"></div>

<script>
const root = document.getElementById('root');
const statusEl = document.getElementById('status');
const refreshBtn = document.getElementById('refresh');
const autoEl = document.getElementById('auto');
let timer = null;

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

async function load() {
  try {
    const r = await fetch('/api/sessions');
    const data = await r.json();
    render(data);
    statusEl.textContent = 'updated ' + new Date().toLocaleTimeString();
  } catch (e) {
    statusEl.textContent = 'error: ' + e.message;
  }
}

function render(sessions) {
  if (!sessions.length) {
    root.innerHTML = '<div class="empty">No sessions tracked in <code>~/.claude-hub/spawns.json</code>.</div>';
    return;
  }
  const rows = sessions.map(s => {
    const alive = s.alive;
    const action = alive
      ? `<button class="danger" data-action="stop" data-name="${escapeHtml(s.name)}">Stop</button>`
      : `<button data-action="clean" data-name="${escapeHtml(s.name)}">Clean</button>`;
    const env = s.env_url
      ? `<a href="${escapeHtml(s.env_url)}" target="_blank">open</a>`
      : '<span style="color:var(--muted)">—</span>';
    const sidShort = s.session_id ? s.session_id.slice(0, 8) : '—';
    const resume = s.resume_cmd
      ? `<button class="copy" data-copy="${escapeHtml(s.resume_cmd)}" title="${escapeHtml(s.resume_cmd)}">copy</button>`
      : '<span style="color:var(--muted)">—</span>';
    return `<tr>
      <td class="name">${escapeHtml(s.name)}</td>
      <td class="path">${escapeHtml(s.display_path)}</td>
      <td class="pid">${escapeHtml(s.pid)}</td>
      <td>${escapeHtml(s.started_human)}</td>
      <td><span class="state"><span class="dot ${alive ? 'alive' : 'dead'}"></span>${alive ? 'alive' : 'dead'}</span></td>
      <td>${env}</td>
      <td class="sid">${escapeHtml(sidShort)}</td>
      <td>${resume}</td>
      <td><div class="actions">${action}</div></td>
    </tr>`;
  }).join('');
  root.innerHTML = `<table>
    <thead><tr>
      <th>Name</th><th>Path</th><th>PID</th><th>Started</th><th>State</th><th>Env</th><th>Session</th><th>Resume</th><th></th>
    </tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

root.addEventListener('click', async (ev) => {
  const copyBtn = ev.target.closest('button[data-copy]');
  if (copyBtn) {
    const text = copyBtn.dataset.copy;
    try {
      await navigator.clipboard.writeText(text);
      const orig = copyBtn.textContent;
      copyBtn.textContent = '✓ copied';
      setTimeout(() => { copyBtn.textContent = orig; }, 1200);
    } catch (e) {
      prompt('Copy this:', text);
    }
    return;
  }
  const btn = ev.target.closest('button[data-action]');
  if (!btn) return;
  const action = btn.dataset.action;
  const name = btn.dataset.name;
  const verb = action === 'stop' ? 'Stop' : 'Remove';
  if (!confirm(`${verb} session "${name}"?`)) return;
  btn.disabled = true;
  try {
    const r = await fetch('/api/' + action, {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({name})
    });
    const data = await r.json();
    if (!data.ok) alert('Failed: ' + (data.error || 'unknown'));
  } catch (e) {
    alert('Request failed: ' + e.message);
  }
  load();
});

refreshBtn.addEventListener('click', load);

function setAuto(on) {
  if (timer) { clearInterval(timer); timer = null; }
  if (on) timer = setInterval(load, 5000);
}
autoEl.addEventListener('change', () => setAuto(autoEl.checked));

load();
setAuto(true);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # quieter logs; uncomment to debug
        pass

    def _send_json(self, status: int, payload) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._send_html(INDEX_HTML)
        elif self.path == "/api/sessions":
            self._send_json(HTTPStatus.OK, _sessions_payload())
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "invalid json"})
            return
        name = body.get("name")
        if not isinstance(name, str) or not name:
            self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": "missing name"})
            return
        if self.path == "/api/stop":
            self._send_json(HTTPStatus.OK, _stop_session(name))
        elif self.path == "/api/clean":
            self._send_json(HTTPStatus.OK, _clean_session(name))
        else:
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})


def run(args: argparse.Namespace) -> int:
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    url = f"http://{args.host}:{args.port}/"
    print(f"claude-hub web running at {url}  (Ctrl+C to stop)")

    stop_event = threading.Event()
    titler = threading.Thread(target=_titler_loop, args=(stop_event,), daemon=True)
    titler.start()
    print(f"[titler] auto-titling tracked spawns every {int(TITLER_INTERVAL_SECONDS)}s", flush=True)

    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nbye.")
    finally:
        stop_event.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Local web UI for claude-hub sessions")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="don't open browser")
    sys.exit(run(parser.parse_args()))
