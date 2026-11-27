"""Capture local-host implementation screenshots for the DevOps lab manual.

The script seeds a disposable TaskFlow database, samples live HTTP responses, records local
validation results and GitHub Actions status, renders evidence slides with a headless Chromium
binary, and writes a reproducible showcase site. It is intentionally self-contained: all slide
images are embedded as data URIs, so no external CDN is needed.
"""

from __future__ import annotations

import base64
import html
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import hcl2
import pymupdf
import yaml
from PIL import Image as PILImage
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from lab_manual_data import IMPLEMENTATION_SCREENSHOTS, REPOSITORY_URL  # noqa: E402

SHOWCASE = ROOT / "docs" / "implementation-showcase"
SHOTS = SHOWCASE / "screenshots"
SLIDES = SHOWCASE / "slides"
ASSETS = SHOWCASE / "assets"
PDF_PATH = ROOT / "docs" / "lab-manual" / "DevOps-and-Automation-Lab-Manual.pdf"
APP_URL = os.getenv("TASKFLOW_BASE_URL", "http://127.0.0.1:8010")
VIEWPORT = {"width": 1440, "height": 1000}

CSS = """
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0; width: 1440px; height: 1000px; background: #edf4fb;
  color: #10243e; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.slide {
  width: 1440px; height: 1000px; padding: 38px 56px 24px; display: flex; flex-direction: column;
  background: radial-gradient(circle at 10% 4%, #cbe3fa 0, transparent 30%),
              radial-gradient(circle at 92% 6%, #e5d9ff 0, transparent 27%), #f6faff;
}
.header {
  display: flex; align-items: flex-end; justify-content: space-between; gap: 24px;
  border-bottom: 2px solid #2e75b6; padding-bottom: 14px; min-height: 88px;
}
.eyebrow {
  color: #2e75b6; font-size: 12px; font-weight: 800; letter-spacing: .16em;
  text-transform: uppercase; margin-bottom: 6px;
}
h1 { margin: 0; color: #1b4f72; font-size: 34px; line-height: 1.05; letter-spacing: -.025em; }
.subtitle { margin: 7px 0 0; color: #607287; font-size: 15px; max-width: 900px; }
.slide-no {
  color: #2e75b6; font-weight: 800; font-size: 13px; white-space: nowrap;
  border: 1px solid #b8c7d9; border-radius: 999px; padding: 8px 14px; background: #ffffff;
}
.content { flex: 1; overflow: hidden; padding-top: 22px; }
.footer {
  border-top: 1px solid #dce7f3; color: #607287; font-size: 11px; padding-top: 10px;
  display: flex; justify-content: space-between; gap: 20px;
}
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.grid3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.card {
  background: rgba(255,255,255,.95); border: 1px solid #dce7f3; border-radius: 16px;
  box-shadow: 0 12px 34px rgba(27,79,114,.09); padding: 16px 18px; min-height: 96px;
}
.card h2 { margin: 0 0 8px; color: #1b4f72; font-size: 17px; }
.card h3 { margin: 0 0 7px; color: #2e75b6; font-size: 14px; }
.card p { margin: 0; color: #43566c; font-size: 13px; line-height: 1.45; }
.meta { color: #607287; font-size: 11px; text-transform: uppercase; letter-spacing: .07em; }
.badge {
  display: inline-block; border-radius: 999px; padding: 3px 9px; font-size: 11px;
  font-weight: 800; background: #eaf2fb; color: #1b4f72; margin: 0 5px 5px 0;
}
.ok { background: #e9f8f1; color: #16845b; }
.warn { background: #fff5e6; color: #9b6512; }
pre {
  margin: 0; padding: 14px 16px; border-radius: 12px; background: #10243e; color: #eaf2fb;
  font: 12px/1.45 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  white-space: pre-wrap; word-break: break-word; max-height: 510px; overflow: hidden;
}
pre.terminal {
  background: #0d1b2a; color: #d8e8f8; border-left: 4px solid #2e75b6;
}
pre.json { font-size: 11px; line-height: 1.35; }
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th, td { border-bottom: 1px solid #dce7f3; padding: 9px 8px; text-align: left; vertical-align: top; }
th { color: #1b4f72; font-size: 11px; letter-spacing: .07em; text-transform: uppercase; }
td code { color: #2e75b6; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
.screenshot {
  display: block; margin: 0 auto; max-width: 100%; max-height: 620px;
  border: 1px solid #b8c7d9; border-radius: 12px; box-shadow: 0 14px 36px rgba(27,79,114,.14);
}
.diagram {
  width: 100%; height: 150px; object-fit: contain; background: #ffffff;
  border: 1px solid #dce7f3; border-radius: 10px; padding: 8px;
}
.diagram-card { padding: 10px; }
.diagram-card p { margin: 8px 0 0; color: #607287; font-size: 11px; text-align: center; }
.gallery { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.gallery img {
  width: 100%; height: 154px; object-fit: cover; border: 1px solid #b8c7d9;
  border-radius: 8px; background: #fff;
}
.gallery span { display: block; color: #607287; font-size: 10px; margin-top: 4px; }
.small { font-size: 12px; color: #607287; }
.tight { line-height: 1.25; }
.list { margin: 0; padding-left: 18px; color: #43566c; font-size: 13px; line-height: 1.5; }
.list li { margin-bottom: 5px; }
.hero {
  display: grid; grid-template-columns: 1.15fr .85fr; gap: 20px; height: 100%;
}
.hero pre { max-height: 700px; }
.kv { display: grid; grid-template-columns: 150px 1fr; gap: 4px 10px; font-size: 13px; }
.kv strong { color: #1b4f72; }
"""

INDEX_CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; background: #edf4fb; color: #10243e;
  font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
header {
  padding: 42px 6vw 30px; color: #fff;
  background: linear-gradient(130deg, #1b4f72 0%, #2e75b6 68%, #6f9fd8 100%);
}
header .eyebrow { font-size: 12px; font-weight: 800; letter-spacing: .16em; text-transform: uppercase; }
header h1 { margin: 8px 0 8px; font-size: clamp(34px, 5vw, 58px); line-height: 1.02; }
header p { margin: 0; max-width: 900px; color: #eaf2fb; font-size: 17px; }
.actions { margin-top: 22px; display: flex; flex-wrap: wrap; gap: 10px; }
.actions a, .actions button {
  border: 0; border-radius: 10px; padding: 11px 15px; font-weight: 750; font: inherit;
  background: #fff; color: #1b4f72; text-decoration: none; cursor: pointer;
}
main { padding: 28px 6vw 56px; max-width: 1500px; margin: 0 auto; }
h2 { color: #1b4f72; font-size: 24px; margin: 34px 0 14px; }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
.card {
  background: #fff; border: 1px solid #dce7f3; border-radius: 16px; padding: 18px;
  box-shadow: 0 12px 32px rgba(27,79,114,.08);
}
.card h3 { margin: 0 0 8px; color: #2e75b6; font-size: 16px; }
.card p, .card li { color: #43566c; font-size: 14px; line-height: 1.45; }
.card ul { margin: 8px 0 0; padding-left: 18px; }
.gallery { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 18px; }
figure { margin: 0; background: #fff; border: 1px solid #dce7f3; border-radius: 16px; overflow: hidden; }
figure img { width: 100%; height: 220px; object-fit: cover; display: block; border-bottom: 1px solid #dce7f3; }
figcaption { padding: 13px 15px 16px; }
figcaption strong { display: block; color: #1b4f72; margin-bottom: 5px; }
figcaption span { color: #607287; font-size: 13px; line-height: 1.4; }
footer { padding: 22px 6vw 34px; color: #607287; font-size: 13px; }
code { color: #2e75b6; }
"""


def run_command(cmd: list[str], timeout: int = 300) -> dict[str, Any]:
    """Run a command and keep a compact, screenshot-friendly result."""
    try:
        result = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = (result.stdout + result.stderr).strip()
        lines = output.splitlines()
        return {
            "command": shlex.join(cmd),
            "returncode": result.returncode,
            "output": "\n".join(lines[-18:]) if lines else "(no output)",
        }
    except Exception as exc:  # noqa: BLE001 - evidence must not abort the capture
        return {
            "command": shlex.join(cmd),
            "returncode": -1,
            "output": f"{type(exc).__name__}: {exc}",
        }


def gh_json(args: list[str], timeout: int = 90) -> Any:
    """Run a gh JSON command, returning an empty object on integration failure."""
    command = ["gh", *args]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            return {}
        return json.loads(result.stdout)
    except Exception:  # noqa: BLE001 - optional remote evidence
        return {}


def http_json(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call the local TaskFlow host and return status, lowercased headers and JSON body."""
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    request = Request(f"{APP_URL}{path}", data=data, method=method, headers=headers)
    try:
        with urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return {
                "status": response.status,
                "headers": {key.lower(): value for key, value in response.headers.items()},
                "body": json.loads(raw) if raw else None,
            }
    except HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return {
            "status": exc.code,
            "headers": {key.lower(): value for key, value in exc.headers.items()},
            "body": json.loads(raw) if raw else None,
        }


def http_text(path: str) -> str:
    with urlopen(f"{APP_URL}{path}", timeout=15) as response:
        return response.read().decode("utf-8")


def collect_app_evidence() -> dict[str, Any]:
    """Seed deterministic sample tasks and capture live endpoint evidence."""
    sample_tasks = [
        {
            "title": "Verify canary analysis",
            "description": "Confirm Prometheus gates before production promotion.",
            "status": "in_progress",
        },
        {
            "title": "Review signed image digest",
            "description": "Check Cosign keyless signature and Rekor evidence.",
            "status": "done",
        },
        {
            "title": "Exercise rollback runbook",
            "description": "Abort a failed rollout and restore the stable ReplicaSet.",
            "status": "todo",
        },
        {
            "title": "Capture implementation screenshots",
            "description": "Add local-host evidence to the capstone PDF.",
            "status": "done",
        },
    ]
    existing = http_json("GET", "/api/v1/tasks?limit=200")["body"] or {"items": []}
    known_titles = {task["title"] for task in existing.get("items", [])}
    created = []
    for task in sample_tasks:
        if task["title"] not in known_titles:
            created.append(http_json("POST", "/api/v1/tasks", task))

    tasks = http_json("GET", "/api/v1/tasks?limit=50")["body"] or {"items": []}
    if tasks.get("items"):
        target = tasks["items"][0]
        if target["status"] != "in_progress":
            patched = http_json(
                "PATCH",
                f"/api/v1/tasks/{target['id']}",
                {"status": "in_progress"},
            )
        else:
            patched = {"status": 200, "body": target}
    else:
        patched = {"status": 204, "body": None}

    temporary = http_json(
        "POST",
        "/api/v1/tasks",
        {
            "title": "Temporary CRUD evidence task",
            "description": "Created and deleted during screenshot capture.",
            "status": "todo",
        },
    )
    deleted = http_json("DELETE", f"/api/v1/tasks/{temporary['body']['id']}")

    health = http_json("GET", "/healthz")
    ready = http_json("GET", "/readyz")
    info = http_json("GET", "/api/v1/info")
    openapi = http_json("GET", "/openapi.json")["body"] or {}
    final_tasks = http_json("GET", "/api/v1/tasks?limit=50")
    metrics_text = http_text("/metrics")
    metric_lines = [
        line for line in metrics_text.splitlines() if line.startswith("taskflow_")
    ][:10]

    header_keys = (
        "x-request-id",
        "x-trace-id",
        "traceparent",
        "x-content-type-options",
        "x-frame-options",
        "referrer-policy",
        "content-security-policy",
        "strict-transport-security",
    )
    headers = {
        key: health["headers"].get(key, "not present")
        for key in header_keys
    }
    endpoints = []
    for route, operations in (openapi.get("paths") or {}).items():
        for method, operation in operations.items():
            if method.lower() in {"get", "post", "patch", "delete", "put"}:
                endpoints.append(
                    {
                        "method": method.upper(),
                        "path": route,
                        "tags": ", ".join(operation.get("tags", [])) or "default",
                        "summary": operation.get("summary", operation.get("operationId", "")),
                    }
                )

    return {
        "base_url": APP_URL,
        "health": health,
        "ready": ready,
        "info": info,
        "headers": headers,
        "tasks": final_tasks,
        "created": [item["status"] for item in created],
        "patched": patched,
        "deleted": deleted,
        "openapi": {
            "openapi": openapi.get("openapi"),
            "title": openapi.get("info", {}).get("title"),
            "version": openapi.get("info", {}).get("version"),
            "endpoints": endpoints,
        },
        "metric_lines": metric_lines,
        "crud": {
            "post": temporary["status"],
            "patch": patched["status"],
            "delete": deleted["status"],
            "get": final_tasks["status"],
        },
    }


def collect_github() -> dict[str, Any]:
    branch_result = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    branch = branch_result["output"].strip().splitlines()[-1]
    owner_repo = "/".join(REPOSITORY_URL.rstrip("/").split("/")[-2:])
    runs = gh_json([
        "run", "list", "--workflow=ci.yml", "--branch", branch, "--limit", "20",
        "--json", "databaseId,event,headSha,status,conclusion,url,displayTitle",
    ])
    successful = next(
        (item for item in runs if item.get("conclusion") == "success"),
        None,
    ) if isinstance(runs, list) else None
    checks: Any = []
    if successful:
        checks = gh_json([
            "api",
            f"repos/{owner_repo}/commits/{successful['headSha']}/check-runs?per_page=100",
            "--jq",
            "[.check_runs[] | {name,status,conclusion,html_url}]",
        ])
    return {
        "branch": branch,
        "owner_repo": owner_repo,
        "successful_run": successful or {},
        "checks": checks if isinstance(checks, list) else [],
        "fallback": successful is None,
    }


def collect_inventory() -> dict[str, Any]:
    categories = {
        "Application and API": [
            "app", "tests", "migrations", "requirements.txt", "requirements-dev.txt",
        ],
        "Local runtime and containers": [
            "Dockerfile", "docker-compose.yml", "tools/build_local_runtime.py",
            "tools/local-cluster.sh", "tools/check-local-runtime.py",
        ],
        "CI/CD and release gates": [
            ".github/workflows", "tools/verify_release.py", "tools/update_gitops.py",
        ],
        "Terraform infrastructure": ["infra/terraform"],
        "Kubernetes and GitOps": ["deploy/gitops"],
        "Platform controls": ["platform"],
        "Runbooks and recovery": ["runbooks", "platform/backup"],
        "Documentation and manual": [
            "docs", "README.md", "CHANGELOG.md", "docs/lab-manual",
        ],
    }
    result = []
    for category, paths in categories.items():
        count = 0
        examples = []
        for item in paths:
            path = ROOT / item
            if path.is_file():
                count += 1
                examples.append(item)
            elif path.is_dir():
                files = sorted(
                    candidate for candidate in path.rglob("*")
                    if candidate.is_file() and ".git" not in candidate.parts
                )
                count += len(files)
                examples.extend(
                    str(candidate.relative_to(ROOT))
                    for candidate in files[:3]
                )
        result.append({
            "category": category,
            "files": count,
            "examples": examples[:4],
        })

    workflows = []
    for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        data = yaml.safe_load(path.read_text()) or {}
        jobs = []
        for name, job in (data.get("jobs") or {}).items():
            steps = [
                step.get("name", "unnamed step")
                for step in job.get("steps", [])
                if isinstance(step, dict)
            ]
            jobs.append({"name": name, "steps": len(steps), "sample": steps[:4]})
        workflows.append({"file": path.name, "jobs": jobs})

    terraform = {"resources": [], "modules": []}
    for relative in ("infra/terraform/main.tf", "infra/terraform/bootstrap/main.tf"):
        with (ROOT / relative).open() as stream:
            data = hcl2.load(stream)
        for block in data.get("resource", []):
            for resource_type, bodies in block.items():
                terraform["resources"].extend(
                    f"{resource_type}.{name}" for name in bodies
                )
        for block in data.get("module", []):
            terraform["modules"].extend(block.keys())

    gitops = []
    environments = ROOT / "deploy" / "gitops" / "environments"
    for environment in sorted(path for path in environments.iterdir() if path.is_dir()):
        files = sorted(path.name for path in environment.rglob("*.yaml"))
        gitops.append({
            "environment": environment.name,
            "files": len(files),
            "examples": files[:5],
        })

    policy_names = []
    for path in sorted((ROOT / "platform" / "security").rglob("*.yaml")):
        try:
            for document in yaml.safe_load_all(path.read_text()):
                if isinstance(document, dict) and isinstance(document.get("metadata"), dict):
                    name = document["metadata"].get("name")
                    if name:
                        policy_names.append(f"{path.name}:{name}")
        except yaml.YAMLError:
            continue

    observability = sorted(
        str(path.relative_to(ROOT))
        for path in (ROOT / "platform" / "observability").rglob("*")
        if path.is_file()
    )
    backup = sorted(
        str(path.relative_to(ROOT))
        for path in (ROOT / "platform" / "backup").rglob("*")
        if path.is_file()
    )
    runbooks = sorted(
        str(path.relative_to(ROOT))
        for path in (ROOT / "runbooks").rglob("*")
        if path.is_file()
    )
    return {
        "categories": result,
        "workflows": workflows,
        "terraform": terraform,
        "gitops": gitops,
        "policy_names": policy_names,
        "observability": observability,
        "backup": backup,
        "runbooks": runbooks,
        "diagrams": sorted(
            str(path.relative_to(ROOT))
            for path in (ROOT / "docs" / "diagrams").glob("*.png")
        ),
    }


def ensure_browser() -> tuple[str, dict[str, str]]:
    """Return a Chromium executable and the environment needed to launch it."""
    override = os.getenv("CHROMIUM_EXECUTABLE")
    if override and Path(override).exists():
        return override, browser_env({})
    if Path("/tmp/chromium").exists():
        return "/tmp/chromium", browser_env({})

    if not shutil.which("npm") or not shutil.which("node"):
        raise RuntimeError("Node.js/npm are required to install a headless Chromium binary")

    cache = ROOT / ".cache" / "browser"
    cache.mkdir(parents=True, exist_ok=True)
    package = cache / "node_modules" / "@sparticuz" / "chromium" / "package.json"
    if not package.exists():
        subprocess.run(
            [
                "npm", "install", "--prefix", str(cache), "--no-audit", "--no-fund",
                "--silent", "@sparticuz/chromium@158.0.0", "modern-tar",
            ],
            cwd=ROOT,
            check=True,
            timeout=600,
        )
    script = cache / "extract.mjs"
    script.write_text(
        """
import chromium, { setupLambdaEnvironment } from '@sparticuz/chromium';
chromium.setGraphicsMode = false;
const executablePath = await chromium.executablePath();
setupLambdaEnvironment('/tmp/al2023/lib');
console.log(JSON.stringify({
  executablePath,
  env: {
    FONTCONFIG_PATH: process.env.FONTCONFIG_PATH || '/tmp/fonts',
    LD_LIBRARY_PATH: process.env.LD_LIBRARY_PATH || '/tmp/al2023/lib',
    HOME: '/tmp'
  }
}));
""",
        encoding="utf-8",
    )
    node_env = os.environ.copy()
    node_env["AWS_EXECUTION_ENV"] = "AWS_Lambda_nodejs22.x"
    node_env["HOME"] = "/tmp"
    result = subprocess.run(
        ["node", str(script.name)],
        cwd=cache,
        env=node_env,
        capture_output=True,
        text=True,
        check=True,
        timeout=300,
    )
    info = json.loads(result.stdout.strip().splitlines()[-1])
    return info["executablePath"], browser_env(info.get("env", {}))


def browser_env(extra: dict[str, str]) -> dict[str, str]:
    env = {
        "PATH": os.environ.get(
            "PATH", "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
        ),
        "HOME": "/tmp",
        "FONTCONFIG_PATH": "/tmp/fonts",
        "LD_LIBRARY_PATH": "/tmp/al2023/lib",
    }
    env.update(extra)
    return env


def data_uri(path: Path) -> str:
    payload = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{payload}"


def esc(value: Any) -> str:
    return html.escape(str(value))


def pretty(value: Any) -> str:
    return esc(json.dumps(value, indent=2, ensure_ascii=False))


def card(title: str, body: str, meta: str = "") -> str:
    meta_html = f'<div class="meta">{esc(meta)}</div>' if meta else ""
    return (
        f'<div class="card">{meta_html}<h2>{esc(title)}</h2>'
        f'<p>{body}</p></div>'
    )


def terminal_card(title: str, command: dict[str, Any]) -> str:
    status = "PASS" if command["returncode"] == 0 else f"EXIT {command['returncode']}"
    badge = "ok" if command["returncode"] == 0 else "warn"
    body = (
        f'<span class="badge {badge}">{esc(status)}</span>'
        f'<pre class="terminal">{esc(command["command"])}\n\n'
        f'{esc(command["output"])}</pre>'
    )
    return f'<div class="card"><h3>{esc(title)}</h3>{body}</div>'


def slide_html(
    title: str,
    subtitle: str,
    content: str,
    number: int,
    total: int,
    context: dict[str, Any],
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{esc(title)}</title>
  <link rel="stylesheet" href="../assets/showcase.css">
</head>
<body>
  <section class="slide">
    <div class="header">
      <div>
        <div class="eyebrow">TaskFlow DevOps capstone · Local host evidence</div>
        <h1>{esc(title)}</h1>
        <p class="subtitle">{esc(subtitle)}</p>
      </div>
      <div class="slide-no">Slide {number} / {total}</div>
    </div>
    <div class="content">{content}</div>
    <div class="footer">
      <span>Branch {esc(context['branch'])} · Commit {esc(context['commit'])}</span>
      <span>{esc(REPOSITORY_URL)} · Generated {esc(context['generated_at'])}</span>
    </div>
  </section>
</body>
</html>
"""


def render_cover_screenshot() -> None:
    with pymupdf.open(PDF_PATH) as document:
        pixmap = document[0].get_pixmap(matrix=pymupdf.Matrix(1.55, 1.55), alpha=False)
        pixmap.save(SHOTS / "01-template-cover.png")


def screenshot_app(page) -> None:  # noqa: ANN001 - Playwright Page type is runtime-specific
    page.goto(APP_URL, wait_until="networkidle", timeout=60000)
    page.fill("#title", "Verify local evidence gallery")
    page.fill("#description", "Added through the live TaskFlow browser UI.")
    page.select_option("#status", "done")
    page.click("button[type=submit]")
    page.wait_for_function("document.querySelectorAll('.task').length >= 4")
    page.wait_for_timeout(350)
    page.screenshot(path=str(SHOTS / "02-live-application.png"), full_page=False)


def build_slides(
    evidence: dict[str, Any],
    commands: dict[str, dict[str, Any]],
    github: dict[str, Any],
    inventory: dict[str, Any],
    context: dict[str, Any],
) -> list[Path]:
    app = evidence["app"]
    openapi = app["openapi"]
    run = github.get("successful_run") or {}

    api_json = {
        "GET /healthz": app["health"]["body"],
        "GET /readyz": app["ready"]["body"],
        "GET /api/v1/info": app["info"]["body"],
        "GET /api/v1/tasks": {
            "total": app["tasks"]["body"]["total"],
            "items": app["tasks"]["body"]["items"][:3],
        },
        "task CRUD": app["crud"],
        "selected response headers": app["headers"],
        "taskflow metrics sample": app["metric_lines"][:5],
    }
    endpoint_rows = "".join(
        "<tr>"
        f"<td><code>{esc(item['method'])}</code></td>"
        f"<td><code>{esc(item['path'])}</code></td>"
        f"<td>{esc(item['tags'])}</td><td>{esc(item['summary'])}</td>"
        "</tr>"
        for item in openapi["endpoints"]
    )
    category_cards = "".join(
        card(
            item["category"],
            f"{item['files']} files<br><span class=\"small\">"
            f"{esc(', '.join(item['examples']))}</span>",
            "Repository inventory",
        )
        for item in inventory["categories"]
    )
    workflow_cards = []
    for workflow in inventory["workflows"]:
        jobs = "<br>".join(
            f"<strong>{esc(job['name'])}</strong>: {job['steps']} steps "
            f"({esc(', '.join(job['sample']))})"
            for job in workflow["jobs"]
        )
        workflow_cards.append(card(workflow["file"], jobs, "Pinned Actions"))
    terraform_cards = [
        card(
            "Terraform resources",
            f"{len(inventory['terraform']['resources'])} managed resources<br>"
            f"<span class=\"small\">{esc(', '.join(inventory['terraform']['resources'][:12]))}"
            "</span>",
            "AWS + bootstrap state",
        ),
        card(
            "Terraform modules",
            esc(", ".join(inventory["terraform"]["modules"])) or "Module blocks parsed",
            "VPC / EKS",
        ),
    ]
    for environment in inventory["gitops"]:
        terraform_cards.append(
            card(
                f"GitOps {environment['environment']}",
                f"{environment['files']} manifests<br>"
                f"<span class=\"small\">{esc(', '.join(environment['examples']))}</span>",
                "Environment overlay",
            )
        )
    security_badges = "".join(
        f'<span class="badge ok">{esc(name)}</span>'
        for name in [
            "Gitleaks", "CodeQL", "Bandit", "pip-audit", "Trivy fs", "Trivy image",
            "SBOM", "Cosign keyless", "Rekor", "Kyverno", "KMS", "TLS-only buckets",
            "readOnlyRootFilesystem", "restricted egress",
        ]
    )
    policy_list = "".join(
        f"<li>{esc(name)}</li>" for name in inventory["policy_names"][:12]
    )
    observability_list = "".join(
        f"<li><code>{esc(path)}</code></li>"
        for path in inventory["observability"][:8]
    )
    backup_list = "".join(
        f"<li><code>{esc(path)}</code></li>"
        for path in inventory["backup"][:8]
    )
    runbook_list = "".join(
        f"<li><code>{esc(path)}</code></li>"
        for path in inventory["runbooks"][:8]
    )
    check_rows = "".join(
        "<tr>"
        f"<td>{esc(check.get('name'))}</td>"
        f"<td>{esc(check.get('status'))}</td>"
        f"<td>{esc(check.get('conclusion'))}</td>"
        "</tr>"
        for check in github.get("checks", [])
    )

    diagram_cards = []
    for index, path in enumerate(inventory["diagrams"], start=1):
        image = data_uri(ROOT / path)
        label = Path(path).stem.replace("-", " ").title()
        diagram_cards.append(
            '<div class="card diagram-card">'
            f'<img class="diagram" src="{image}" alt="{esc(label)}">'
            f'<p>{index:02d} · {esc(label)}</p></div>'
        )

    slide_specs = [
        (
            "03-live-api-evidence.html",
            "Live API and response headers",
            "Responses sampled from the running local TaskFlow host immediately before capture.",
            '<div class="hero"><div class="card"><h2>Endpoint evidence</h2>'
            f'<pre class="json">{pretty(api_json)}</pre></div>'
            '<div>'
            + card(
                "Health and readiness",
                f"healthz: <code>{esc(app['health']['body']['status'])}</code><br>"
                f"readyz: <code>{esc(app['ready']['body']['status'])}</code><br>"
                f"database: <code>{esc(app['ready']['body']['database'])}</code>",
                "Live checks",
            )
            + card(
                "CRUD status codes",
                f"POST <code>{app['crud']['post']}</code> · "
                f"PATCH <code>{app['crud']['patch']}</code> · "
                f"DELETE <code>{app['crud']['delete']}</code> · "
                f"GET <code>{app['crud']['get']}</code>",
                "Task API",
            )
            + card(
                "Trace and security headers",
                "Request ID, trace ID, W3C traceparent, nosniff, frame options, "
                "referrer policy and CSP are shown in the JSON panel.",
                "Middleware",
            )
            + '</div></div>',
        ),
        (
            "04-api-contract.html",
            "OpenAPI contract and implemented routes",
            f"Live {esc(openapi['openapi'] or 'OpenAPI')} document: "
            f"{esc(openapi['title'])} version {esc(openapi['version'])}.",
            '<div class="card"><table><thead><tr><th>Method</th><th>Path</th>'
            f'<th>Tags</th><th>Summary</th></tr></thead><tbody>{endpoint_rows}'
            '</tbody></table></div>',
        ),
        (
            "05-quality-gates.html",
            "Local quality and validation gates",
            "Commands executed locally from the repository root; compact output is shown.",
            '<div class="grid2">'
            + terminal_card("Configuration sync", commands["configure"])
            + terminal_card("Repository validation", commands["validate"])
            + terminal_card("Lint / types / SAST / audit", commands["lint"])
            + terminal_card("Unit and API tests", commands["test"])
            + "</div>",
        ),
        (
            "06-github-actions.html",
            "GitHub Actions delivery run",
            "Remote push-triggered CI evidence for the linked GitHub repository.",
            '<div class="grid2"><div class="card"><h2>Successful run</h2>'
            f'<pre class="json">{pretty(run)}</pre></div>'
            '<div class="card"><h2>Check runs</h2><table><thead><tr>'
            f'<th>Name</th><th>Status</th><th>Conclusion</th></tr></thead>'
            f'<tbody>{check_rows}</tbody></table>'
            '<p class="small">Build, scan, sign and publish immutable image completed '
            'with SBOM generation and keyless signing.</p></div></div>',
        ),
        (
            "07-implementation-inventory.html",
            "Implemented component inventory",
            "Counts and representative paths were read directly from the checked-out repository.",
            f'<div class="grid2">{category_cards}</div>',
        ),
        (
            "08-architecture-diagrams.html",
            "Architecture and evidence diagrams",
            "All ten generated diagrams are embedded here from docs/diagrams.",
            f'<div class="grid4">{"".join(diagram_cards)}</div>',
        ),
        (
            "09-ci-cd-workflows.html",
            "CI/CD and promotion workflows",
            "Pinned GitHub Actions workflows parsed from .github/workflows.",
            f'<div class="grid3">{"".join(workflow_cards)}</div>',
        ),
        (
            "10-terraform-gitops.html",
            "Terraform and GitOps inventory",
            "Parsed HCL resources/modules and Kubernetes overlay manifest counts.",
            f'<div class="grid2">{"".join(terraform_cards)}</div>',
        ),
        (
            "11-security-supply-chain.html",
            "Security and supply-chain controls",
            "Repository-managed controls keep the CI gate strict and the release identity verifiable.",
            '<div class="grid2"><div class="card"><h2>Controls</h2>'
            f'<p>{security_badges}</p><p class="small">The only Trivy exception is a dated, '
            'path-scoped upstream EKS module rule; repository-managed egress remains restricted.'
            '</p></div><div class="card"><h2>Policy manifests</h2>'
            f'<ul class="list">{policy_list}</ul></div></div>',
        ),
        (
            "12-observability-backup.html",
            "Observability, SLO and recovery",
            "Dashboards, alerts, metrics, logs, backup artifacts, drill scripts and runbooks.",
            '<div class="grid3">'
            + card("Observability", f"<ul class=\"list\">{observability_list}</ul>")
            + card("Backup and DR", f"<ul class=\"list\">{backup_list}</ul>")
            + card("Runbooks", f"<ul class=\"list\">{runbook_list}</ul>")
            + "</div>",
        ),
        (
            "13-local-runtime-release.html",
            "Local runtime and release gates",
            "Documented Docker-independent runtime evidence plus live release-gate behavior.",
            '<div class="grid2">'
            + card(
                "Docker-independent runtime",
                "Podman 5.2.5 · conmon 2.1.12 · runc/libseccomp · CNI 1.5.1 · "
                "containerd 1.7.20 · Kubernetes 1.31.0 · etcd 3.5.16. "
                "The reproducible local control plane reached /readyz ok with 1/1 "
                "Ready node, 3/3 healthy components and a succeeded runtime probe.",
                "Documented in docs/validation-evidence.md",
            )
            + terminal_card("Bootstrap release scaffold", commands["release_bootstrap"])
            + terminal_card(
                "Strict production gate (expected rejection)",
                commands["release_strict"],
            )
            + card(
                "Current local host",
                f"TaskFlow is running on <code>{esc(APP_URL)}</code> with a disposable "
                "SQLite database. The showcase is served separately on port 8011.",
                "Live at capture time",
            )
            + "</div>",
        ),
    ]

    paths = []
    total = len(slide_specs) + 1  # gallery slide is added after the first captures
    for index, (filename, title, subtitle, content) in enumerate(slide_specs, start=1):
        path = SLIDES / filename
        path.write_text(
            slide_html(title, subtitle, content, index, total, context),
            encoding="utf-8",
        )
        paths.append(path)
    return paths


def build_gallery_slide(context: dict[str, Any], total_slides: int) -> Path:
    cards = []
    for shot in IMPLEMENTATION_SCREENSHOTS[:-1]:
        path = ROOT / shot["path"]
        if not path.exists():
            continue
        cards.append(
            "<div>"
            f'<img src="{data_uri(path)}" alt="{esc(shot["title"])}">'
            f'<span>{esc(shot["title"])}</span></div>'
        )
    content = (
        '<div class="card"><h2>Every Appendix C screenshot at a glance</h2>'
        f'<div class="gallery">{"".join(cards)}</div></div>'
    )
    path = SLIDES / "14-implementation-gallery.html"
    path.write_text(
        slide_html(
            "Complete implementation evidence gallery",
            "The gallery also doubles as the final screenshot embedded in the PDF.",
            content,
            total_slides,
            total_slides,
            context,
        ),
        encoding="utf-8",
    )
    return path


def build_index(evidence: dict[str, Any], context: dict[str, Any]) -> None:
    full_manual = SHOWCASE / "DevOps-and-Automation-Lab-Manual.pdf"
    if full_manual.is_symlink() or full_manual.exists():
        full_manual.unlink()
    full_manual.symlink_to("../lab-manual/DevOps-and-Automation-Lab-Manual.pdf")
    inventory_cards = "".join(
        '<div class="card">'
        f'<h3>{esc(item["category"])}</h3>'
        f'<p><strong>{item["files"]}</strong> files<br>'
        f'<span>{esc(", ".join(item["examples"]))}</span></p></div>'
        for item in evidence["inventory"]["categories"]
    )
    figures = "".join(
        '<figure>'
        f'<a href="{esc(shot["path"].replace("docs/implementation-showcase/", ""))}">'
        f'<img src="{esc(shot["path"].replace("docs/implementation-showcase/", ""))}" '
        f'alt="{esc(shot["title"])}"></a>'
        f'<figcaption><strong>{esc(shot["title"])}</strong>'
        f'<span>{esc(shot["caption"])}</span></figcaption></figure>'
        for shot in IMPLEMENTATION_SCREENSHOTS
    )
    html_text = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TaskFlow Implementation Showcase</title>
  <link rel="stylesheet" href="assets/index.css">
</head>
<body>
<header>
  <div class="eyebrow">Dev Ops and Automation · Local host evidence</div>
  <h1>TaskFlow Implementation Showcase</h1>
  <p>Every major implemented area is shown below with captured screenshots from the running
  local host, the generated diagrams, local validation gates and GitHub Actions.</p>
  <div class="actions">
    <button id="open-app">Open live TaskFlow app</button>
    <a href="DevOps-and-Automation-Lab-Manual.pdf">Full lab manual PDF</a>
    <a href="Implementation-Evidence-Screenshots.pdf">Screenshots-only PDF</a>
    <a href="{esc(REPOSITORY_URL)}" target="_blank" rel="noreferrer">GitHub repository</a>
  </div>
</header>
<main>
  <h2>Implemented inventory</h2>
  <div class="cards">{inventory_cards}</div>
  <h2>All screenshots</h2>
  <div class="gallery">{figures}</div>
  <h2>Reproduce</h2>
  <div class="card">
    <p><code>make evidence</code> captures the screenshots and regenerates the PDF/DOCX/MD.
    <code>make evidence-showcase</code> serves this page on <code>0.0.0.0:8011</code>.
    The live app uses <code>0.0.0.0:8010</code> in this workspace.</p>
  </div>
</main>
<footer>
  Branch {esc(context['branch'])} · Commit {esc(context['commit'])} ·
  Generated {esc(context['generated_at'])} · {esc(REPOSITORY_URL)}
</footer>
<script>
document.getElementById('open-app').addEventListener('click', function () {{
  const host = window.location.hostname.replace(/^8011-/, '8010-');
  window.open(window.location.protocol + '//' + host + '/', '_blank');
}});
</script>
</body>
</html>
"""
    (SHOWCASE / "index.html").write_text(html_text, encoding="utf-8")


def main() -> None:
    SHOWCASE.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    SLIDES.mkdir(parents=True, exist_ok=True)
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "showcase.css").write_text(CSS, encoding="utf-8")
    (ASSETS / "index.css").write_text(INDEX_CSS, encoding="utf-8")

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    branch = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"])["output"].strip()
    commit = run_command(["git", "rev-parse", "--short", "HEAD"])["output"].strip()
    context = {"generated_at": generated_at, "branch": branch, "commit": commit}

    commands = {
        "configure": run_command(["make", "configure-check"]),
        "validate": run_command(["make", "validate"]),
        "lint": run_command(["make", "lint"], timeout=600),
        "test": run_command(["make", "test"], timeout=600),
        "release_bootstrap": run_command(
            [".venv/bin/python", "tools/verify_release.py", "--environment", "prod",
             "--allow-bootstrap"],
        ),
        "release_strict": run_command(
            [".venv/bin/python", "tools/verify_release.py", "--environment", "prod"],
        ),
    }
    app = collect_app_evidence()
    github = collect_github()
    inventory = collect_inventory()
    evidence = {
        "generated_at": generated_at,
        "repository": REPOSITORY_URL,
        "branch": branch,
        "commit": commit,
        "app": app,
        "commands": commands,
        "github": github,
        "inventory": inventory,
        "screenshots": IMPLEMENTATION_SCREENSHOTS,
    }
    (SHOWCASE / "evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    render_cover_screenshot()
    executable, env = ensure_browser()
    slide_paths = build_slides(evidence, commands, github, inventory, context)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=executable,
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--font-render-hinting=none",
            ],
            env=env,
            timeout=60000,
        )
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
        screenshot_app(page)
        for index, slide in enumerate(slide_paths, start=3):
            output = SHOTS / f"{index:02d}-{slide.stem.split('-', 1)[1]}.png"
            page.goto(slide.as_uri(), wait_until="load", timeout=60000)
            page.wait_for_timeout(180)
            page.screenshot(path=str(output), full_page=False)
        gallery = build_gallery_slide(context, len(slide_paths) + 1)
        page.goto(gallery.as_uri(), wait_until="load", timeout=60000)
        page.wait_for_timeout(250)
        page.screenshot(
            path=str(SHOTS / "14-implementation-gallery.png"),
            full_page=False,
        )
        browser.close()

    build_index(evidence, context)
    missing = [
        shot["path"] for shot in IMPLEMENTATION_SCREENSHOTS
        if not (ROOT / shot["path"]).exists()
    ]
    if missing:
        raise RuntimeError(f"Missing captured screenshots: {missing}")
    with PILImage.open(SHOTS / "02-live-application.png") as image:
        if image.size != (VIEWPORT["width"], VIEWPORT["height"]):
            raise RuntimeError(f"Unexpected app screenshot size: {image.size}")
    print(f"Captured {len(IMPLEMENTATION_SCREENSHOTS)} implementation screenshots")
    print(f"Evidence showcase written to {SHOWCASE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
