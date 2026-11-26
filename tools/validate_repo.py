"""Validate repository structure, manifests, supply-chain pins and lab-manual content."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import hcl2
import pymupdf
import yaml
from docx import Document

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {
    ".git",
    ".venv",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tools",
    "node_modules",
}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".docx", ".db", ".sqlite3"}
ACTION_SHA = re.compile(r"^[0-9a-f]{40}$")
ACTION_USE = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s@]+)@([^\s#]+)", re.MULTILINE)
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|PRIVATE) KEY-----"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(
        r"(?i)\b(?:password|secret|token)\s*[:=]\s*['\"][^'\"$}{]{10,}['\"]"
    ),
)
SECRET_SCAN_SKIP = (
    ".env.example",
    "deploy/gitops/environments/dev/",
    "platform/security/gitleaks.toml",
)
FORBIDDEN_MANUAL_TEXT = (
    "lavnish",
    "ipcv",
    "image processing",
    "huffman",
    "2301010181",
)
STUDENT_DETAILS = (
    "Arghyadipta Goswami",
    "2301010192",
    "Section - C",
    "Year 2023-2027",
    "Dev Ops and Automation",
)

REQUIRED = (
    "README.md",
    "Dockerfile",
    "docker-compose.yml",
    "requirements.txt",
    "pyproject.toml",
    "app/main.py",
    "tests/test_api.py",
    ".github/workflows/ci.yml",
    ".github/workflows/cd.yml",
    ".github/workflows/promote.yml",
    "infra/terraform/main.tf",
    "infra/scripts/bootstrap-local.sh",
    "deploy/gitops/apps/taskflow/base/rollout.yaml",
    "deploy/gitops/apps/taskflow/base/analysis-template.yaml",
    "deploy/gitops/environments/prod/release.yaml",
    "platform/argocd/applicationset.yaml",
    "platform/observability/grafana-dashboard-taskflow.json",
    "platform/security/kyverno-policies.yaml",
    "platform/backup/velero-schedule.yaml",
    "docs/slo.md",
    "docs/lab-manual/DevOps-and-Automation-Lab-Manual.pdf",
    "docs/lab-manual/DevOps-and-Automation-Lab-Manual.docx",
    "docs/lab-manual/DevOps-and-Automation-Lab-Manual.md",
    "docs/toolchain.md",
    "requirements-tools.txt",
    "tools/install-platform-tools.sh",
    "tools/check-platform-tools.py",
)


def iter_files(suffixes: set[str]):
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in EXCLUDED for part in path.parts):
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        if not suffixes or path.suffix.lower() in suffixes:
            yield path


def check_required(errors: list[str]) -> None:
    for relative in REQUIRED:
        if not (ROOT / relative).exists():
            errors.append(f"missing required file: {relative}")


def check_python(errors: list[str]) -> None:
    for path in iter_files({".py"}):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (OSError, SyntaxError) as exc:
            errors.append(f"Python syntax error in {path.relative_to(ROOT)}: {exc}")


def check_shell(errors: list[str]) -> None:
    for path in iter_files({".sh"}):
        result = subprocess.run(
            ["bash", "-n", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            message = detail[0] if detail else "unknown bash syntax error"
            errors.append(f"Shell syntax error in {path.relative_to(ROOT)}: {message}")


def check_yaml(errors: list[str]) -> None:
    for path in iter_files({".yml", ".yaml"}):
        try:
            list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
        except Exception as exc:  # noqa: BLE001 - report any parse error
            errors.append(f"YAML parse error in {path.relative_to(ROOT)}: {exc}")


def check_json(errors: list[str]) -> None:
    for path in iter_files({".json"}):
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"JSON parse error in {path.relative_to(ROOT)}: {exc}")


def check_hcl(errors: list[str]) -> None:
    terraform_dir = ROOT / "infra" / "terraform"
    for path in terraform_dir.rglob("*"):
        if not path.is_file() or path.suffix not in {".tf", ".tfvars", ".hcl"}:
            continue
        try:
            with path.open(encoding="utf-8") as stream:
                hcl2.load(stream)
        except Exception as exc:  # noqa: BLE001 - report any HCL parse error
            errors.append(f"HCL parse error in {path.relative_to(ROOT)}: {exc}")


def check_kustomize(errors: list[str]) -> None:
    gitops_dir = ROOT / "deploy" / "gitops"
    for path in gitops_dir.rglob("kustomization.yaml"):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for resource in data.get("resources", []):
                if isinstance(resource, str) and not (path.parent / resource).exists():
                    errors.append(
                        f"missing Kustomize resource in {path.relative_to(ROOT)}: {resource}"
                    )
            for patch in data.get("patches", []):
                if isinstance(patch, dict) and "path" in patch:
                    target = path.parent / str(patch["path"])
                    if not target.exists():
                        errors.append(
                            f"missing Kustomize patch in {path.relative_to(ROOT)}: {patch['path']}"
                        )
            release_path = path.parent / "release.yaml"
            if release_path.exists():
                release = yaml.safe_load(release_path.read_text(encoding="utf-8")) or {}
                release_digest = release.get("spec", {}).get("image", {}).get("digest")
                for image in data.get("images", []):
                    image_digest = image.get("digest")
                    if image_digest and image_digest != release_digest:
                        errors.append(
                            f"Kustomize digest does not match release.yaml in {path.parent.name}"
                        )
        except Exception as exc:  # noqa: BLE001 - report any Kustomize validation error
            errors.append(f"Kustomize validation error in {path.relative_to(ROOT)}: {exc}")


def check_actions(errors: list[str]) -> None:
    for path in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = path.read_text(encoding="utf-8")
        for action, ref in ACTION_USE.findall(text):
            if not ACTION_SHA.match(ref):
                errors.append(
                    f"unpinned GitHub Action in {path.name}: {action}@{ref}; "
                    "pin to a full commit SHA"
                )


def check_secrets(errors: list[str]) -> None:
    for path in iter_files(set()):
        relative = path.relative_to(ROOT).as_posix()
        if any(relative.startswith(prefix) for prefix in SECRET_SCAN_SKIP):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible committed secret in {relative}")
                break


def check_lab_manual(errors: list[str]) -> None:
    base = ROOT / "docs" / "lab-manual" / "DevOps-and-Automation-Lab-Manual"
    md_path = Path(f"{base}.md")
    pdf_path = Path(f"{base}.pdf")
    docx_path = Path(f"{base}.docx")

    if not md_path.exists():
        return
    md_text = md_path.read_text(encoding="utf-8")
    md_requirements = (
        "**Submitted by:** Arghyadipta Goswami (Roll 2301010192)",
        "**Section:** C | **Year:** 2023-2027",
        "**Subject:** Dev Ops and Automation",
    )
    for detail in md_requirements:
        if detail not in md_text:
            errors.append(f"lab manual Markdown is missing: {detail}")

    document_texts: dict[str, str] = {"Markdown": md_text}
    try:
        with pymupdf.open(pdf_path) as pdf:
            if pdf.page_count < 20:
                errors.append("lab manual PDF has fewer than 20 pages")
            document_texts["PDF"] = "\n".join(page.get_text() for page in pdf)
        if not pdf_path.read_bytes().startswith(b"%PDF-"):
            errors.append("lab manual PDF has an invalid signature")
    except Exception as exc:  # noqa: BLE001 - report unreadable PDF
        errors.append(f"lab manual PDF could not be read: {exc}")

    try:
        document_texts["DOCX"] = "\n".join(
            paragraph.text for paragraph in Document(docx_path).paragraphs
        )
    except Exception as exc:  # noqa: BLE001 - report unreadable DOCX
        errors.append(f"lab manual DOCX could not be read: {exc}")

    for label, text in document_texts.items():
        lowered = text.lower()
        for forbidden in FORBIDDEN_MANUAL_TEXT:
            if forbidden in lowered:
                errors.append(f"lab manual {label} contains forbidden template content: {forbidden}")
        if label != "Markdown":
            for detail in STUDENT_DETAILS:
                if detail not in text:
                    errors.append(f"lab manual {label} is missing student detail: {detail}")


def main() -> int:
    errors: list[str] = []
    check_required(errors)
    check_python(errors)
    check_shell(errors)
    check_yaml(errors)
    check_json(errors)
    check_hcl(errors)
    check_kustomize(errors)
    check_actions(errors)
    check_secrets(errors)
    check_lab_manual(errors)
    if errors:
        print("Repository validation FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    print(
        "Repository validation passed: required files, Python/shell, YAML/JSON/HCL, "
        "Kustomize references, action pins, secrets and lab-manual content."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
