#!/usr/bin/env python3
"""Render TaskFlow platform manifests from one self-configuring input file.

The repository ships safe, deterministic local values in ``config/platform.env``.
Environment variables with the same names take precedence, so CI or an operator
can render real AWS account, DNS and email values without editing many files.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config" / "platform.env"
UNSET_TOKEN = "REPLACE_" + "WITH_"
EXAMPLE_DOMAIN = "example" + ".com"
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".docx", ".db", ".sqlite3"}
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
CONFIG_KEYS = (
    "TASKFLOW_PROJECT",
    "TASKFLOW_AWS_REGION",
    "TASKFLOW_AWS_ACCOUNT_ID",
    "TASKFLOW_TF_STATE_PREFIX",
    "TASKFLOW_TF_LOCK_TABLE",
    "TASKFLOW_BACKUP_BUCKET",
    "TASKFLOW_BACKUP_ROLE",
    "TASKFLOW_EXTERNAL_SECRETS_ROLE",
    "TASKFLOW_RDS_INSTANCE_IDENTIFIER",
    "TASKFLOW_RDS_SECRET_NAME",
    "TASKFLOW_PROD_HOST",
    "TASKFLOW_STAGING_HOST",
    "TASKFLOW_CERT_EMAIL",
    "TASKFLOW_TRACE_ID",
)


class ConfigError(RuntimeError):
    """Raised when platform configuration is invalid or out of sync."""


def load_config() -> dict[str, str]:
    """Load defaults from the checked-in file and apply environment overrides."""
    if not CONFIG_FILE.is_file():
        raise ConfigError(f"missing configuration file: {CONFIG_FILE.relative_to(ROOT)}")
    values: dict[str, str] = {}
    for raw_line in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            values[key] = value
    missing = [key for key in CONFIG_KEYS if key not in values]
    if missing:
        raise ConfigError(f"missing keys in config/platform.env: {', '.join(missing)}")
    for key in CONFIG_KEYS:
        override = os.environ.get(key)
        if override is not None and override.strip():
            values[key] = override.strip()
    validate_config(values)
    return values


def validate_config(values: dict[str, str]) -> None:
    """Validate deterministic, non-secret platform values before rendering."""
    constraints = {
        "TASKFLOW_PROJECT": r"^[a-z][a-z0-9-]{1,30}$",
        "TASKFLOW_AWS_REGION": r"^[a-z]{2}(?:-[a-z]+)+-\d$",
        "TASKFLOW_AWS_ACCOUNT_ID": r"^\d{12}$",
        "TASKFLOW_TF_STATE_PREFIX": r"^[a-z0-9][a-z0-9.-]{1,50}$",
        "TASKFLOW_TF_LOCK_TABLE": r"^[A-Za-z0-9._-]{3,64}$",
        "TASKFLOW_BACKUP_BUCKET": r"^[a-z0-9][a-z0-9.-]{1,50}$",
        "TASKFLOW_BACKUP_ROLE": r"^[A-Za-z0-9+=,.@_-]{1,64}$",
        "TASKFLOW_EXTERNAL_SECRETS_ROLE": r"^[A-Za-z0-9+=,.@_-]{1,64}$",
        "TASKFLOW_RDS_INSTANCE_IDENTIFIER": r"^[a-z][a-z0-9-]{1,62}$",
        "TASKFLOW_RDS_SECRET_NAME": r"^[A-Za-z0-9/_+=.@-]{1,128}$",
        "TASKFLOW_PROD_HOST": r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$",
        "TASKFLOW_STAGING_HOST": r"^(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$",
        "TASKFLOW_CERT_EMAIL": r"^[^@\s]+@[A-Za-z0-9.-]+$",
        "TASKFLOW_TRACE_ID": r"^[0-9a-f]{32}$",
    }
    for key, pattern in constraints.items():
        if not re.fullmatch(pattern, values[key]):
            raise ConfigError(f"invalid value for {key}: {values[key]!r}")
    if EXAMPLE_DOMAIN in " ".join(values.values()):
        raise ConfigError("example domains are not accepted platform defaults")


def derived(values: dict[str, str]) -> dict[str, str]:
    """Compute ARNs and per-environment values from the single input set."""
    region = values["TASKFLOW_AWS_REGION"]
    account = values["TASKFLOW_AWS_ACCOUNT_ID"]
    prefix = values["TASKFLOW_TF_STATE_PREFIX"]
    return {
        **values,
        "STATE_BUCKET_DEV": f"{prefix}-dev",
        "STATE_BUCKET_STAGING": f"{prefix}-staging",
        "STATE_BUCKET_PROD": f"{prefix}-prod",
        "BACKUP_ROLE_ARN": (
            f"arn:aws:iam::{account}:role/{values['TASKFLOW_BACKUP_ROLE']}"
        ),
        "EXTERNAL_SECRETS_ROLE_ARN": (
            f"arn:aws:iam::{account}:role/{values['TASKFLOW_EXTERNAL_SECRETS_ROLE']}"
        ),
        "RDS_SECRET_ARN": (
            f"arn:aws:secretsmanager:{region}:{account}:"
            f"secret:{values['TASKFLOW_RDS_SECRET_NAME']}"
        ),
    }


def replace_capture(
    text: str,
    pattern: str,
    value: str,
    expected: int,
    *,
    second_group: bool = True,
) -> str:
    """Replace the value captured after a stable key, preserving formatting."""

    def replacement(match: re.Match[str]) -> str:
        tail = match.group(2) if second_group and match.lastindex and match.lastindex >= 2 else ""
        return f"{match.group(1)}{value}{tail}"

    updated, count = re.subn(pattern, replacement, text)
    if count != expected:
        raise ConfigError(f"expected {expected} replacements for {pattern!r}, found {count}")
    return updated


def replace_literal(text: str, pattern: str, value: str, expected: int = 1) -> str:
    """Replace a complete line or expression with a deterministic value."""
    updated, count = re.subn(pattern, lambda _: value, text)
    if count != expected:
        raise ConfigError(f"expected {expected} replacements for {pattern!r}, found {count}")
    return updated


def render_backend(text: str, vals: dict[str, str], environment: str) -> str:
    text = replace_capture(
        text,
        r'(?m)^(\s*bucket\s*=\s*")[^"]+(")',
        vals[f"STATE_BUCKET_{environment.upper()}"],
        1,
    )
    text = replace_capture(
        text,
        r'(?m)^(\s*dynamodb_table\s*=\s*")[^"]+(")',
        vals["TASKFLOW_TF_LOCK_TABLE"],
        1,
    )
    return replace_capture(
        text,
        r'(?m)^(\s*region\s*=\s*")[^"]+(")',
        vals["TASKFLOW_AWS_REGION"],
        1,
    )


def render_ingress(text: str, vals: dict[str, str], environment: str) -> str:
    host = vals[f"TASKFLOW_{environment.upper()}_HOST"]
    text = replace_capture(text, r'(?m)^(\s*-\s*hosts:\s*\[")[^\]]+("\])', host, 1)
    return replace_capture(text, r"(?m)^(\s*-\s*host:\s*)\S+", host, 1, second_group=False)


def render_role_arn(text: str, value: str) -> str:
    return replace_capture(
        text,
        r"(?m)^(\s*eks\.amazonaws\.com/role-arn:\s*)\S+",
        value,
        1,
        second_group=False,
    )


def render_cronjob_env(text: str, name: str, value: str) -> str:
    return replace_capture(
        text,
        rf"(?m)^(\s*-\s*name:\s*{re.escape(name)}\s*\n\s*value:\s*)\S+",
        value,
        1,
        second_group=False,
    )


def render_yaml_value(text: str, key: str, value: str, expected: int) -> str:
    return replace_capture(
        text,
        rf"(?m)^(\s*{re.escape(key)}:\s*)\S+",
        value,
        expected,
        second_group=False,
    )


def render_backup_policy(text: str, vals: dict[str, str]) -> str:
    bucket = vals["TASKFLOW_BACKUP_BUCKET"]
    updated, count = re.subn(
        r"arn:aws:s3:::[^\"/]+",
        lambda match: match.group(0).split(":::")[0] + ":::" + bucket,
        text,
    )
    if count != 2:
        raise ConfigError(f"expected two backup bucket ARNs, found {count}")
    return updated


def render_gitleaks(text: str, _: dict[str, str]) -> str:
    text = replace_literal(
        text,
        r"(?m)^description = \".*\"$",
        'description = "Ignore intentionally local lab-only values."',
    )
    return replace_capture(
        text,
        r"(?m)^(\s*)'''[A-Z][A-Z0-9_]*\[[A-Za-z0-9_-]+\]\+''',\s*$",
        "'''TASKFLOW_UNSET_[A-Z0-9_]+''',",
        1,
        second_group=False,
    )


def render_checklist_source(text: str, _: dict[str, str]) -> str:
    return replace_capture(
        text,
        r'(?m)^(\s*")Every [^"]*restore RTO has been measured\.(",)$',
        "Every platform configuration value has been generated from "
        "config/platform.env and the restore RTO has been measured.",
        1,
    )


def render_checklist_markdown(text: str, _: dict[str, str]) -> str:
    return replace_literal(
        text,
        r"(?m)^- Every .*restore RTO has been measured\.$",
        "- Every platform configuration value has been generated from "
        "config/platform.env and the restore RTO has been measured.",
    )


def build_rules(vals: dict[str, str]) -> dict[str, list[Callable[[str], str]]]:
    """Return idempotent renderers for every tracked configuration surface."""
    rules: dict[str, list[Callable[[str], str]]] = {}

    def add(path: str, *functions: Callable[[str], str]) -> None:
        rules.setdefault(path, []).extend(functions)

    for filename, environment in {
        "infra/terraform/backend.hcl.example": "dev",
        "infra/terraform/environments/dev.backend.hcl": "dev",
        "infra/terraform/environments/staging.backend.hcl": "staging",
        "infra/terraform/environments/prod.backend.hcl": "prod",
    }.items():
        add(filename, lambda text, env=environment: render_backend(text, vals, env))

    for environment in ("staging", "prod"):
        add(
            f"deploy/gitops/environments/{environment}/external-secret.yaml",
            lambda text: replace_capture(
                text,
                r"(?m)^(\s*key:\s*)\S+",
                vals["RDS_SECRET_ARN"],
                1,
                second_group=False,
            ),
        )
        add(
            f"deploy/gitops/environments/{environment}/serviceaccount-backup.yaml",
            lambda text: render_role_arn(text, vals["BACKUP_ROLE_ARN"]),
        )
        add(
            f"deploy/gitops/environments/{environment}/serviceaccount-external-secrets.yaml",
            lambda text: render_role_arn(text, vals["EXTERNAL_SECRETS_ROLE_ARN"]),
        )
        add(
            f"deploy/gitops/environments/{environment}/ingress.yaml",
            lambda text, env=environment: render_ingress(text, vals, env),
        )

    add(
        ".github/workflows/promote.yml",
        lambda text: replace_capture(
            text,
            r"(?m)^(\s*url:\s*https://)\S+",
            vals["TASKFLOW_PROD_HOST"],
            1,
            second_group=False,
        ),
    )
    add(
        "platform/backup/backup-iam-policy.json",
        lambda text: render_backup_policy(text, vals),
    )
    add(
        "platform/backup/rds-snapshot-cronjob.yaml",
        lambda text: render_cronjob_env(
            text, "AWS_REGION", vals["TASKFLOW_AWS_REGION"]
        ),
        lambda text: render_cronjob_env(
            text, "AWS_ROLE_ARN", vals["BACKUP_ROLE_ARN"]
        ),
        lambda text: render_cronjob_env(
            text,
            "DB_INSTANCE_IDENTIFIER",
            vals["TASKFLOW_RDS_INSTANCE_IDENTIFIER"],
        ),
    )
    add(
        "platform/backup/velero-values.yaml",
        lambda text: render_yaml_value(
            text, "bucket", vals["TASKFLOW_BACKUP_BUCKET"], 1
        ),
        lambda text: render_yaml_value(
            text, "region", vals["TASKFLOW_AWS_REGION"], 2
        ),
        lambda text: render_role_arn(text, vals["BACKUP_ROLE_ARN"]),
    )
    add(
        "platform/observability/log-queries.md",
        lambda text: replace_capture(
            text,
            r'(trace_id=")[^"]+(")',
            vals["TASKFLOW_TRACE_ID"],
            1,
        ),
    )
    add(
        "platform/security/cert-manager-issuers.yaml",
        lambda text: render_yaml_value(text, "email", vals["TASKFLOW_CERT_EMAIL"], 2),
    )
    add("platform/security/gitleaks.toml", lambda text: render_gitleaks(text, vals))
    add("tools/lab_manual_data.py", lambda text: render_checklist_source(text, vals))
    add(
        "docs/lab-manual/DevOps-and-Automation-Lab-Manual.md",
        lambda text: render_checklist_markdown(text, vals),
    )
    return rules


def rendered_files(vals: dict[str, str]) -> dict[Path, tuple[str, str]]:
    """Return original and rendered content for every managed file."""
    output: dict[Path, tuple[str, str]] = {}
    for relative, functions in build_rules(vals).items():
        path = ROOT / relative
        if not path.is_file():
            raise ConfigError(f"missing managed file: {relative}")
        original = path.read_text(encoding="utf-8")
        rendered = original
        for function in functions:
            rendered = function(rendered)
        output[path] = (original, rendered)
    return output


def scan_text_files() -> list[str]:
    """Reject leftover unset tokens and example domains in tracked text files."""
    errors: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in EXCLUDED for part in path.parts):
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if UNSET_TOKEN in text or EXAMPLE_DOMAIN in text:
            errors.append(f"unconfigured platform value in {path.relative_to(ROOT)}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true", help="write rendered values")
    group.add_argument(
        "--check", action="store_true", help="verify rendered values (default)"
    )
    parser.add_argument("--print", action="store_true", help="print derived values")
    args = parser.parse_args()

    try:
        values = load_config()
        vals = derived(values)
        files = rendered_files(vals)
        errors = scan_text_files()
        changed = [path for path, (original, rendered) in files.items() if original != rendered]
        if args.apply:
            for path, (_, rendered) in files.items():
                if path.read_text(encoding="utf-8") != rendered:
                    path.write_text(rendered, encoding="utf-8")
            errors = scan_text_files()
            print(f"Platform configuration applied to {len(changed)} managed files.")
        else:
            for path in changed:
                errors.append(f"platform configuration is stale: {path.relative_to(ROOT)}")
            if not errors:
                print("Platform configuration is synchronized.")
        if args.print:
            for key in sorted(vals):
                print(f"{key}={vals[key]}")
        if errors:
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 1
        return 0
    except ConfigError as exc:
        print(f"Platform configuration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
