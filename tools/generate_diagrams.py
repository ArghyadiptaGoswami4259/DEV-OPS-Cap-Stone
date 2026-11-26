"""Generate original architecture and expected-output evidence diagrams."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "diagrams"
FONT_DIR = ROOT / "docs" / "lab-manual" / "assets" / "fonts"
FONT = str(FONT_DIR / "DejaVuSans.ttf")
FONT_BOLD = str(FONT_DIR / "DejaVuSans-Bold.ttf")

W, H = 1600, 900
BLUE = "#1B4F72"
ACCENT = "#2E75B6"
PALE = "#EAF2FB"
INK = "#17324D"
MUTED = "#607287"
GREEN = "#16845B"
RED = "#B23B3B"
GREY = "#DCE7F3"
WHITE = "#FFFFFF"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT, size)


def wrap(text: str, fnt: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if ImageDraw.Draw(Image.new("RGB", (1, 1))).textlength(candidate, font=fnt) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def base_image(index: int, title: str, subtitle: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, W, 118), fill=BLUE)
    draw.text((56, 30), f"EXPERIMENT {index:02d}", font=font(22, True), fill="#9CC7EA")
    draw.text((56, 62), title, font=font(36, True), fill=WHITE)
    draw.text(
        (W - 56, 62),
        "TaskFlow DevOps Capstone",
        font=font(20),
        fill="#C8DEF1",
        anchor="ra",
    )
    draw.line((56, 150, W - 56, 150), fill=ACCENT, width=3)
    draw.text((56, 168), subtitle, font=font(22), fill=MUTED)
    draw.line((56, H - 72, W - 56, H - 72), fill=GREY, width=2)
    draw.text((56, H - 54), "Original expected verification evidence", font=font(18), fill=MUTED)
    draw.text((W - 56, H - 54), "Dev Ops and Automation Lab Manual", font=font(18), fill=MUTED, anchor="ra")
    return image, draw


def box(
    draw: ImageDraw.ImageDraw,
    rect: tuple[int, int, int, int],
    title: str,
    detail: str = "",
    fill: str = PALE,
    border: str = ACCENT,
) -> None:
    draw.rounded_rectangle(rect, radius=18, fill=fill, outline=border, width=3)
    x1, y1, x2, y2 = rect
    draw.text((x1 + 24, y1 + 20), title, font=font(25, True), fill=BLUE)
    if detail:
        y = y1 + 62
        for line in wrap(detail, font(19), x2 - x1 - 48)[:3]:
            draw.text((x1 + 24, y), line, font=font(19), fill=INK)
            y += 27


def arrow(
    draw: ImageDraw.ImageDraw,
    start: tuple[int, int],
    end: tuple[int, int],
    color: str = ACCENT,
) -> None:
    draw.line((*start, *end), fill=color, width=5)
    import math

    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    length = 18
    spread = 0.55
    p1 = (
        end[0] - length * math.cos(angle - spread),
        end[1] - length * math.sin(angle - spread),
    )
    p2 = (
        end[0] - length * math.cos(angle + spread),
        end[1] - length * math.sin(angle + spread),
    )
    draw.polygon([end, p1, p2], fill=color)


def chip(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, color: str = GREEN) -> None:
    fnt = font(18, True)
    width = int(draw.textlength(text, font=fnt)) + 34
    draw.rounded_rectangle((x, y, x + width, y + 40), radius=20, fill=WHITE, outline=color, width=2)
    draw.text((x + 17, y + 9), text, font=fnt, fill=color)


def save(image: Image.Image, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    image.save(OUT / name, optimize=True)


def diagram_01() -> None:
    image, d = base_image(1, "End-to-end platform blueprint", "Commit, build, secure, deploy, observe, and recover")
    nodes = [
        (55, 260, 280, 410, "Git commit", "Conventional Commit, PR, CODEOWNERS"),
        (330, 260, 555, 410, "CI gates", "Tests, SAST, image scan, SBOM"),
        (605, 260, 830, 410, "Signed image", "GHCR immutable digest + Cosign"),
        (880, 260, 1105, 410, "GitOps state", "Environment Kustomize overlays"),
        (1155, 260, 1545, 410, "Argo CD", "Sync, prune and self-heal"),
    ]
    for n in nodes:
        box(d, n[:4], n[4], n[5])
    for i in range(len(nodes) - 1):
        arrow(d, (nodes[i][2] + 5, 335), (nodes[i + 1][0] - 5, 335))
    box(d, (225, 500, 620, 680), "Kubernetes Rollout", "Canary 20/50/100, HPA, PDB, migration Job")
    box(d, (680, 500, 1075, 680), "Observability", "Prometheus, Grafana, Loki, trace IDs, alerts")
    box(d, (1135, 500, 1530, 680), "Recoverability", "Auto abort, Velero, RDS snapshots, Git revert")
    arrow(d, (1325, 410), (425, 500))
    arrow(d, (620, 590), (680, 590))
    arrow(d, (1075, 590), (1135, 590))
    for x, label in [(70, "Reproducible"), (390, "Policy-gated"), (720, "Immutable"), (1040, "Declarative")]:
        chip(d, x, 735, label)
    save(image, "01-architecture.png")


def diagram_02() -> None:
    image, d = base_image(2, "Version control and release traceability", "Short-lived branches, protected delivery and immutable release records")
    d.line((110, 330, 1490, 330), fill=BLUE, width=7)
    d.text((110, 285), "main / protected", font=font(22, True), fill=BLUE)
    for x in (270, 610, 950, 1290):
        d.ellipse((x - 14, 316, x + 14, 344), fill=ACCENT)
    d.line((270, 330, 380, 235), fill=ACCENT, width=5)
    d.line((380, 235, 520, 235), fill=ACCENT, width=5)
    d.line((520, 235, 610, 330), fill=ACCENT, width=5)
    d.text((340, 198), "feat/api-filter", font=font(20, True), fill=INK)
    d.line((950, 330, 1060, 235), fill=ACCENT, width=5)
    d.line((1060, 235, 1200, 235), fill=ACCENT, width=5)
    d.line((1200, 235, 1290, 330), fill=ACCENT, width=5)
    d.text((1020, 198), "fix/rollout", font=font(20, True), fill=INK)
    for x, title, detail in [
        (80, "Pre-commit", "Ruff, pytest, manifest parse"),
        (440, "Pull request", "Review, CODEOWNERS, CI checks"),
        (800, "Merge", "Squash, conventional subject"),
        (1160, "Release", "Digest, signature, Git tag"),
    ]:
        box(d, (x, 430, x + 330, 610), title, detail)
    chip(d, 80, 680, "No direct push")
    chip(d, 430, 680, "Required checks")
    chip(d, 800, 680, "Signed evidence")
    chip(d, 1160, 680, "Rollback by digest")
    save(image, "02-version-control.png")


def diagram_03() -> None:
    image, d = base_image(3, "Containerization and image hardening", "Multi-stage build, non-root runtime and immutable release identity")
    layers = [
        (180, 250, 820, 330, "Builder stage", "python:3.12-slim + exact requirements in /opt/venv"),
        (180, 350, 820, 430, "Runtime stage", "Only the virtualenv, app code, migrations and alembic.ini"),
        (180, 450, 820, 530, "Security context", "UID 10001, read-only rootfs, dropped capabilities, seccomp"),
        (180, 550, 820, 630, "Runtime contract", "Port 8080, /healthz, structured stdout logs, no shell entrypoint"),
    ]
    for item in layers:
        box(d, item[:4], item[4], item[5])
    box(d, (900, 250, 1510, 630), "Image evidence", "Labels: version, Git SHA, source, license\nHealthcheck: GET /healthz\n.dockerignore excludes .git, .env and caches\nCompose: app + PostgreSQL + optional observability")
    for x, _, label in [
        (920, 680, "Reproducible"),
        (1120, 680, "Non-root"),
        (1320, 680, "Health checked"),
    ]:
        chip(d, x, 680, label)
    save(image, "03-container.png")


def diagram_04() -> None:
    image, d = base_image(4, "CI quality and supply-chain gates", "Every commit is verified before an immutable artifact is published")
    gates = [
        "Ruff + MyPy", "Pytest + coverage", "CodeQL + Bandit", "Gitleaks", "pip-audit",
        "Trivy FS + image", "SBOM + provenance", "Cosign signature",
    ]
    for i, label in enumerate(gates):
        x = 70 + (i % 4) * 380
        y = 250 + (i // 4) * 175
        box(d, (x, y, x + 330, y + 125), f"{i + 1}. {label}", "Fail closed on high/critical findings")
        chip(d, x + 14, y + 84, "PASS", GREEN)
    box(d, (470, 620, 1130, 745), "Published artifact", "ghcr.io/<repository>/taskflow@sha256:<digest>")
    save(image, "04-ci-gates.png")


def diagram_05() -> None:
    image, d = base_image(5, "Infrastructure automation with Terraform", "Versioned state and environment-specific AWS building blocks")
    box(d, (590, 260, 1010, 400), "Terraform root module", "Pinned providers, modules and tfvars")
    resources = [
        (60, 460, "VPC", "3 AZs, private subnets, NAT"),
        (350, 460, "EKS", "Managed nodes, IRSA, logs"),
        (640, 460, "ECR", "Immutable, encrypted, scan"),
        (930, 460, "RDS", "KMS, backups, private access"),
        (1220, 460, "S3 + IAM", "Velero state and least privilege"),
    ]
    for x, y, title, detail in resources:
        box(d, (x, y, x + 290, y + 160), title, detail)
        arrow(d, (800, 400), (x + 145, y), ACCENT)
    box(d, (330, 680, 1270, 780), "Remote state", "Versioned S3 bucket + DynamoDB lock table; no state files in Git")
    save(image, "05-terraform.png")


def diagram_06() -> None:
    image, d = base_image(6, "Kubernetes orchestration", "Declarative workload, traffic, scaling, policy and migration objects")
    d.rounded_rectangle((55, 230, 1545, 720), radius=24, outline=BLUE, width=4)
    d.text((85, 245), "Kubernetes namespace (restricted Pod Security)", font=font(22, True), fill=BLUE)
    items = [
        (90, 320, "Ingress / TLS", "WAF + rate limits"),
        (360, 320, "Service", "Shared traffic front end"),
        (630, 320, "Argo Rollout", "Canary + probes + securityContext"),
        (900, 320, "TaskFlow Pods", "Non-root / read-only / resources"),
        (1170, 320, "PostgreSQL", "Migrations + persistent data"),
    ]
    for i, (x, y, title, detail) in enumerate(items):
        box(d, (x, y, x + 250, y + 170), title, detail)
        if i:
            arrow(d, (items[i - 1][0] + 255, y + 85), (x - 5, y + 85))
    for x, y, title, detail in [
        (90, 545, "HPA + PDB", "CPU, memory, disruption budget"),
        (400, 545, "NetworkPolicy", "Default deny, explicit DNS/DB/ingress"),
        (710, 545, "ServiceMonitor", "Scrape /metrics every 15 seconds"),
        (1020, 545, "Alembic Job", "PreSync migration with DB wait"),
        (1330, 545, "ExternalSecret", "Secrets Manager through IRSA"),
    ]:
        box(d, (x, y, x + 230, y + 145), title, detail, fill=WHITE, border=GREY)
    save(image, "06-kubernetes.png")


def diagram_07() -> None:
    image, d = base_image(7, "GitOps and environment promotion", "Staging automation and protected production approval")
    stages = [
        (70, 280, "CI digest", "Signed sha256 artifact"),
        (420, 280, "Staging overlay", "Automated [skip ci] commit"),
        (770, 280, "Argo CD", "Reconcile desired state"),
        (1120, 280, "Staging canary", "SLO analysis and smoke tests"),
    ]
    for i, (x, y, title, detail) in enumerate(stages):
        box(d, (x, y, x + 300, y + 170), title, detail)
        if i:
            arrow(d, (stages[i - 1][0] + 305, y + 85), (x - 5, y + 85))
    box(d, (420, 530, 770, 680), "Production approval", "Protected GitHub Environment, reviewer identity, strict release gate")
    box(d, (870, 530, 1220, 680), "Production overlay", "Immutable digest, release tag, audit evidence")
    arrow(d, (1270, 450), (595, 530), ACCENT)
    arrow(d, (770, 605), (870, 605), ACCENT)
    chip(d, 90, 735, "No mutable latest tag")
    chip(d, 420, 735, "Signature verified")
    chip(d, 800, 735, "Approval recorded")
    chip(d, 1180, 735, "Self-heal enabled")
    save(image, "07-gitops.png")


def diagram_08() -> None:
    image, d = base_image(8, "Monitoring, logging and alerting", "Metrics, structured logs, trace correlation and SLO dashboards")
    charts = [
        (70, 250, "Request rate", GREEN),
        (450, 250, "5xx ratio", RED),
        (830, 250, "p95 latency", ACCENT),
        (1210, 250, "Ready replicas", BLUE),
    ]
    for x, y, title, color in charts:
        d.rounded_rectangle((x, y, x + 320, y + 240), radius=16, fill=WHITE, outline=GREY, width=3)
        d.text((x + 20, y + 20), title, font=font(23, True), fill=BLUE)
        points = [(x + 25 + i * 35, y + 190 - (i * 17 + 20) % 150) for i in range(9)]
        d.line(points, fill=color, width=5, joint="curve")
        for px, py in points:
            d.ellipse((px - 4, py - 4, px + 4, py + 4), fill=color)
    box(d, (70, 540, 740, 720), "Structured JSON logs", "timestamp, level, trace_id, route, status, duration_ms -> Loki")
    box(d, (800, 540, 1530, 720), "Alerting and response", "PrometheusRule, Alertmanager, LogQL, SLO error budget")
    chip(d, 90, 755, "X-Trace-ID correlation")
    chip(d, 430, 755, "15s scrape interval")
    chip(d, 800, 755, "Critical + warning routes")
    chip(d, 1190, 755, "Resolved transitions")
    save(image, "08-observability.png")


def diagram_09() -> None:
    image, d = base_image(9, "Security controls and policy enforcement", "Shift-left scanning, admission control, runtime isolation and secret hygiene")
    controls = [
        "CodeQL / Bandit", "Gitleaks", "Trivy / pip-audit", "Cosign + SBOM",
        "Kyverno", "Pod Security", "NetworkPolicy", "External Secrets", "IRSA",
    ]
    for i, label in enumerate(controls):
        x = 70 + (i % 3) * 500
        y = 250 + (i // 3) * 145
        box(d, (x, y, x + 440, y + 115), label, "Prevent, detect or contain", fill=PALE)
    box(d, (330, 700, 1270, 790), "Defence in depth", "Source -> build -> artifact -> admission -> runtime -> response", fill=WHITE)
    save(image, "09-security.png")


def diagram_10() -> None:
    image, d = base_image(10, "Canary analysis and automatic recovery", "Metric-gated 20/50/100 promotion with a stable fallback")
    d.line((120, 390, 1480, 390), fill=BLUE, width=8)
    points = [(230, "20%"), (680, "50%"), (1180, "100%")]
    for x, label in points:
        d.ellipse((x - 18, 372, x + 18, 408), fill=ACCENT)
        d.text((x, 330), label, font=font(30, True), fill=BLUE, anchor="mm")
    box(d, (120, 470, 520, 650), "Analysis #1", "5xx < 2%, p95 < 500 ms, ready > 0")
    box(d, (570, 470, 970, 650), "Analysis #2", "Three one-minute measurements each")
    box(d, (1020, 470, 1480, 650), "Promote or abort", "Healthy at 100% or Degraded on failure")
    arrow(d, (230, 410), (320, 470), ACCENT)
    arrow(d, (680, 410), (770, 470), ACCENT)
    arrow(d, (1180, 410), (1250, 470), ACCENT)
    d.line((1250, 470, 1250, 710, 320, 710, 320, 650), fill=RED, width=5)
    arrow(d, (320, 710), (320, 650), RED)
    d.text((790, 690), "SLO breach -> abort -> stable ReplicaSet", font=font(22, True), fill=RED, anchor="mm")
    save(image, "10-canary.png")


def main() -> None:
    for function in (
        diagram_01,
        diagram_02,
        diagram_03,
        diagram_04,
        diagram_05,
        diagram_06,
        diagram_07,
        diagram_08,
        diagram_09,
        diagram_10,
    ):
        function()
    print(f"Generated {len(list(OUT.glob('*.png')))} evidence diagrams in {OUT}")


if __name__ == "__main__":
    main()
