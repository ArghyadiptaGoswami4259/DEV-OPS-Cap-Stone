"""Dependency-free browser UI for the TaskFlow preview and smoke tests."""

from __future__ import annotations

import html
from string import Template

from .config import Settings

PAGE = Template(
    """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TaskFlow Control Plane</title>
  <style>
    :root {
      --ink: #10243e; --muted: #607287; --line: #dce7f3; --blue: #1b4f72;
      --accent: #2e75b6; --bg: #edf4fb; --card: #ffffff; --green: #16845b;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0; min-height: 100vh; color: var(--ink); background:
      radial-gradient(circle at 12% 8%, #cae3fa 0, transparent 34%),
      radial-gradient(circle at 88% 5%, #e4d7ff 0, transparent 30%), var(--bg);
      font: 15px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    .shell { max-width: 1080px; margin: 0 auto; padding: 44px 22px 56px; }
    header { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
    .eyebrow { color: var(--accent); font-weight: 750; letter-spacing: .14em; text-transform: uppercase; font-size: 12px; }
    h1 { font-size: clamp(34px, 5vw, 58px); line-height: 1.02; margin: 10px 0 8px; letter-spacing: -.04em; }
    .lede { color: var(--muted); max-width: 620px; margin: 0; font-size: 17px; }
    .status { border: 1px solid #bfe4d4; color: var(--green); background: #effbf5; padding: 10px 15px; border-radius: 999px; font-weight: 700; white-space: nowrap; }
    .grid { display: grid; grid-template-columns: 1.15fr .85fr; gap: 20px; margin-top: 30px; }
    .card { background: rgba(255,255,255,.94); border: 1px solid var(--line); border-radius: 20px; box-shadow: 0 18px 50px rgba(27,79,114,.10); padding: 24px; }
    h2 { font-size: 18px; margin: 0 0 16px; }
    label { display: block; font-size: 12px; font-weight: 750; color: var(--muted); margin: 12px 0 6px; text-transform: uppercase; letter-spacing: .06em; }
    input, textarea, select, button { font: inherit; }
    input, textarea, select { width: 100%; border: 1px solid var(--line); border-radius: 10px; padding: 11px 12px; background: #fbfdff; color: var(--ink); }
    textarea { min-height: 86px; resize: vertical; }
    button { cursor: pointer; border: 0; border-radius: 10px; padding: 11px 16px; font-weight: 700; background: var(--blue); color: white; }
    button.secondary { background: #eaf2fb; color: var(--blue); }
    button.danger { background: #fff1f1; color: #a33636; padding: 7px 10px; font-size: 12px; }
    .row { display: flex; gap: 10px; align-items: center; }
    .row > * { flex: 1; }
    .row button { flex: 0 0 auto; margin-top: 12px; }
    .meta { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin: 18px 0 0; }
    .chip { background: #f4f8fc; border: 1px solid var(--line); border-radius: 12px; padding: 12px; }
    .chip small { display: block; color: var(--muted); text-transform: uppercase; letter-spacing: .06em; }
    .chip strong { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 13px; }
    .task { display: flex; justify-content: space-between; gap: 14px; padding: 13px 0; border-top: 1px solid var(--line); }
    .task:first-child { border-top: 0; }
    .task h3 { margin: 0 0 4px; font-size: 15px; }
    .task p { margin: 0; color: var(--muted); font-size: 13px; }
    .badge { display: inline-block; font-size: 11px; font-weight: 800; text-transform: uppercase; border-radius: 999px; padding: 3px 8px; background: #eaf2fb; color: var(--blue); }
    .links { margin-top: 18px; display: flex; flex-wrap: wrap; gap: 10px; }
    .links a { color: var(--blue); font-weight: 700; text-decoration: none; border-bottom: 1px solid #a9c9e5; }
    .empty { color: var(--muted); text-align: center; padding: 26px 0; }
    footer { color: var(--muted); font-size: 12px; text-align: center; margin-top: 28px; }
    @media (max-width: 760px) { .grid { grid-template-columns: 1fr; } header { flex-direction: column; } }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <div class="eyebrow">Cloud-native reference application</div>
        <h1>TaskFlow</h1>
        <p class="lede">A small, observable and secure API that travels through the complete DevOps delivery pipeline: commit, build, test, scan, publish, deploy, observe and roll back.</p>
      </div>
      <div class="status" id="health">Checking health...</div>
    </header>
    <section class="grid">
      <article class="card">
        <h2>Task board</h2>
        <form id="task-form">
          <label for="title">Title</label>
          <input id="title" name="title" maxlength="160" required placeholder="Verify canary analysis">
          <label for="description">Description</label>
          <textarea id="description" name="description" maxlength="2000" placeholder="Optional detail"></textarea>
          <div class="row">
            <div>
              <label for="status">Status</label>
              <select id="status" name="status">
                <option value="todo">To do</option>
                <option value="in_progress">In progress</option>
                <option value="done">Done</option>
              </select>
            </div>
            <button type="submit">Add task</button>
          </div>
        </form>
        <div id="tasks" class="task-list"><div class="empty">Loading tasks...</div></div>
      </article>
      <aside class="card">
        <h2>Release identity</h2>
        <p style="color:var(--muted);margin-top:-6px">Every response carries a request ID and W3C trace context. Prometheus scrapes request rate, latency, in-flight requests and readiness.</p>
        <div class="meta">
          <div class="chip"><small>Service</small><strong>$app_name</strong></div>
          <div class="chip"><small>Environment</small><strong>$environment</strong></div>
          <div class="chip"><small>Version</small><strong>$version</strong></div>
          <div class="chip"><small>Commit</small><strong>$commit</strong></div>
        </div>
        <div class="links">
          <a href="/healthz">/healthz</a><a href="/readyz">/readyz</a>
          <a href="/metrics">/metrics</a><a href="/docs">/docs</a>
          <a href="/api/v1/info">/api/v1/info</a>
        </div>
        <hr style="border:0;border-top:1px solid var(--line);margin:22px 0">
        <h2>Delivery signals</h2>
        <p style="color:var(--muted);font-size:13px;margin:0">CI gates: tests, lint, types, SAST, dependency and image scans, SBOM, IaC policy and signed images. Production uses an Argo Rollouts canary with Prometheus analysis and automatic abort.</p>
      </aside>
    </section>
    <footer>TaskFlow DevOps capstone | Structured JSON logs | Prometheus metrics | W3C trace context</footer>
  </main>
  <script>
    const tasksEl = document.getElementById('tasks');
    const healthEl = document.getElementById('health');
    async function refreshHealth() {
      try {
        const response = await fetch('/healthz');
        const body = await response.json();
        healthEl.textContent = response.ok ? 'Healthy - ' + body.version : 'Unhealthy';
        healthEl.style.color = response.ok ? '#16845b' : '#a33636';
      } catch (error) { healthEl.textContent = 'Health unavailable'; }
    }
    function escapeHtml(value) {
      return String(value || '').replace(/[&<>"']/g, function (character) {
        return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character];
      });
    }
    async function refreshTasks() {
      const response = await fetch('/api/v1/tasks?limit=50');
      const body = await response.json();
      if (!body.items.length) { tasksEl.innerHTML = '<div class="empty">No tasks yet. Add the first delivery check.</div>'; return; }
      tasksEl.innerHTML = body.items.map(function (task) {
        return '<div class="task"><div><h3>' + escapeHtml(task.title) + ' <span class="badge">' + escapeHtml(task.status) + '</span></h3><p>' + escapeHtml(task.description || '') + '</p></div><button class="danger" data-id="' + task.id + '">Delete</button></div>';
      }).join('');
      tasksEl.querySelectorAll('button.danger').forEach(function (button) {
        button.addEventListener('click', async function () {
          await fetch('/api/v1/tasks/' + button.dataset.id, {method: 'DELETE'});
          refreshTasks();
        });
      });
    }
    document.getElementById('task-form').addEventListener('submit', async function (event) {
      event.preventDefault();
      const payload = {
        title: document.getElementById('title').value,
        description: document.getElementById('description').value || null,
        status: document.getElementById('status').value
      };
      const response = await fetch('/api/v1/tasks', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)
      });
      if (response.ok) { event.target.reset(); document.getElementById('status').value = 'todo'; refreshTasks(); }
      else { alert('Could not create task. Check /docs for the schema.'); }
    });
    refreshHealth(); refreshTasks();
  </script>
</body>
</html>"""
)


def render_index(settings: Settings) -> str:
    return PAGE.safe_substitute(
        app_name=html.escape(settings.app_name),
        version=html.escape(settings.version),
        commit=html.escape(settings.git_sha),
        environment=html.escape(settings.environment),
    )
