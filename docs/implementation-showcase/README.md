# TaskFlow implementation showcase

This directory is a local-host evidence bundle for the capstone. `index.html` shows every
implemented area and every screenshot; the full lab manual embeds the same screenshots in
Appendix C. A screenshots-only companion PDF is generated beside the full manual.

## Files

- `index.html` - interactive evidence gallery and links to the live app, full PDF and GitHub repo.
- `slides/*.html` - standalone evidence slides used to produce consistent screenshots.
- `screenshots/*.png` - all 14 captured screenshots.
- `evidence.json` - structured local endpoint responses, command output, GitHub Actions status
  and repository inventory used to render the slides.
- `Implementation-Evidence-Screenshots.pdf` - direct PDF containing every screenshot.
- `DevOps-and-Automation-Lab-Manual.pdf` - symlink to the full template-styled manual so the
  local static showcase can serve it without escaping its document root.
- `assets/*.css` - local, dependency-free styling for the slides and gallery.

## What the evidence covers

- Live TaskFlow UI on `0.0.0.0:8010`, REST responses, OpenAPI routes and response headers.
- Local `make configure-check`, `make validate`, `make lint`, `make test` and release gates.
- Successful GitHub Actions CI run with quality, security, image scan, SBOM and keyless signing.
- Application, container, local-runtime, CI/CD, Terraform, GitOps, observability, security,
  backup/DR and documentation inventories.
- All ten generated architecture/evidence diagrams and a complete screenshot gallery.
- Previously documented Docker-independent runtime and local Kubernetes control-plane checks.
  Those historical checks are summarized from `docs/validation-evidence.md`; only the TaskFlow
  application is required to be live when the screenshot script is rerun.

## Reproduce

From the repository root:

```bash
make evidence-install
PORT=8010 HOST=0.0.0.0 FORWARDED_ALLOW_IPS='*' \
  APP_VERSION=1.0.0 APP_GIT_SHA="$(git rev-parse --short HEAD)" \
  DATABASE_URL=sqlite:///./.cache/taskflow-evidence.db \
  .venv/bin/python -m app
make evidence
make evidence-showcase
```

`make evidence` seeds sample tasks in the disposable SQLite database, captures the screenshots,
regenerates the full PDF/DOCX/Markdown lab manual and the screenshots-only PDF. The first run
installs a headless Chromium binary from the npm registry into `.cache/browser` and extracts it
under `/tmp`; set `CHROMIUM_EXECUTABLE` to use an existing Chromium binary instead.

`make evidence-showcase` serves this directory on `0.0.0.0:8011`. The "Open live TaskFlow app"
button derives the matching port-8010 preview host from the current port-8011 preview host.
