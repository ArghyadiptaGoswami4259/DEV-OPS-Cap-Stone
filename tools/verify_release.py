"""Policy-as-code gate for immutable, signed production releases."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
ZERO_DIGEST = "sha256:" + "0" * 64
STATE_ANNOTATION = "taskflow.devops/state"


def load(relative: str) -> dict:
    return yaml.safe_load((ROOT / relative).read_text(encoding="utf-8"))


def is_ghcr_repository(value: str) -> bool:
    """Validate an OCI repository by parsing its hostname, not by substring matching."""
    candidate = value.strip()
    if not candidate:
        return False
    parsed = urlparse(candidate if "://" in candidate else f"oci://{candidate}")
    return (
        parsed.scheme == "oci"
        and parsed.hostname == "ghcr.io"
        and parsed.port is None
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and bool(parsed.path.strip("/"))
    )


def check(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", choices=["dev", "staging", "prod"], required=True)
    parser.add_argument(
        "--allow-bootstrap",
        action="store_true",
        help=(
            "Validate only the intentionally non-deployable bootstrap scaffold; "
            "never use this flag in a promotion workflow."
        ),
    )
    args = parser.parse_args()

    release_path = f"deploy/gitops/environments/{args.environment}/release.yaml"
    manifest = load(release_path)
    metadata = manifest.get("metadata", {})
    annotations = metadata.get("annotations", {})
    spec = manifest.get("spec", {})
    image = spec.get("image", {})
    deployment = spec.get("deployment", {})
    approval = spec.get("approval", {})
    recovery = spec.get("recovery", {})
    source = spec.get("source", {})
    promotion = spec.get("promotion", {})
    errors: list[str] = []

    check(manifest.get("kind") == "ReleaseManifest", "manifest kind must be ReleaseManifest", errors)
    check(metadata.get("environment") == args.environment, "environment mismatch", errors)
    digest = str(image.get("digest", ""))
    check(bool(DIGEST.match(digest)), "image.digest must be a full sha256 digest", errors)

    state = str(annotations.get(STATE_ANNOTATION, ""))
    if args.allow_bootstrap:
        check(state == "bootstrap", "bootstrap state annotation is missing or invalid", errors)
        check(digest == ZERO_DIGEST, "bootstrap scaffold must use the zero digest", errors)
        check(image.get("signed") is False, "bootstrap scaffold must be unsigned", errors)
        check(image.get("verifiedBy") == "pending", "bootstrap verification must be pending", errors)
        check(source.get("commit") == "bootstrap", "bootstrap source commit must be bootstrap", errors)
        check(approval.get("approvedBy") == "pending", "bootstrap approval must be pending", errors)
        check(promotion.get("timestamp") == "not-promoted", "bootstrap timestamp must be not-promoted", errors)
        check(promotion.get("immutable") is False, "bootstrap scaffold must not be immutable", errors)
    else:
        check(state == "promoted", "release state annotation must be promoted", errors)
        check(digest != ZERO_DIGEST, "bootstrap digest cannot be promoted", errors)
        check(bool(image.get("signed")), "image must be signed with cosign", errors)
        check(
            image.get("verifiedBy") == "cosign-keyless",
            "signature verification evidence is missing",
            errors,
        )
        check(source.get("commit") != "bootstrap", "source commit is missing", errors)
        check(approval.get("approvedBy") != "pending", "production approval is missing", errors)
        check(
            promotion.get("timestamp") not in {"", "not-promoted", None},
            "promotion timestamp is missing",
            errors,
        )
        check(promotion.get("immutable") is True, "promoted release must be immutable", errors)

    check(
        is_ghcr_repository(str(image.get("repository", ""))),
        "image repository must be GHCR",
        errors,
    )
    check(deployment.get("strategy") == "canary", "production strategy must be canary", errors)
    check(bool(deployment.get("canaryAnalysis")), "automated canary analysis must be enabled", errors)
    check(bool(deployment.get("automatedRollback")), "automated rollback must be enabled", errors)
    required_replicas = 3 if args.environment == "prod" else 2
    check(
        int(deployment.get("minReplicas", 0)) >= required_replicas,
        f"{args.environment} needs at least {required_replicas} replicas",
        errors,
    )
    check(bool(approval.get("required")), "production approval must be required", errors)
    check(int(recovery.get("rpoMinutes", 10**9)) <= 60, "RPO must be at most 60 minutes", errors)
    check(int(recovery.get("rtoMinutes", 10**9)) <= 30, "RTO must be at most 30 minutes", errors)

    evidence = (
        "deploy/gitops/apps/taskflow/base/rollout.yaml",
        "deploy/gitops/apps/taskflow/base/analysis-template.yaml",
        "deploy/gitops/apps/taskflow/base/prometheusrule.yaml",
        "deploy/gitops/apps/taskflow/base/networkpolicy.yaml",
        "platform/security/kyverno-policies.yaml",
        "platform/backup/velero-schedule.yaml",
        "docs/slo.md",
        "runbooks/rollback.md",
        "runbooks/dr-restore.md",
    )
    for relative in evidence:
        check((ROOT / relative).exists(), f"missing release evidence: {relative}", errors)

    if errors:
        print(f"Release gate FAILED for {args.environment}:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    if args.allow_bootstrap:
        print(f"Bootstrap scaffold validated for {args.environment}; it is not deployable.")
    else:
        print(f"Release gate passed for {args.environment} ({digest[:19]}...).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
