"""Update an environment's immutable image digest and release evidence."""

from __future__ import annotations

import argparse
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
IMAGE_NAME = "ghcr.io/arghyadiptagoswami4259/dev-ops-cap-stone/taskflow"


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", choices=["staging", "prod"], required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--approved-by", default="github-environment-protection")
    args = parser.parse_args()
    if not DIGEST.match(args.digest):
        raise SystemExit("digest must match sha256:<64 lowercase hex characters>")

    env_dir = ROOT / "deploy" / "gitops" / "environments" / args.environment
    release_path = env_dir / "release.yaml"
    kustomization_path = env_dir / "kustomization.yaml"

    release = yaml.safe_load(release_path.read_text(encoding="utf-8"))
    metadata = release.setdefault("metadata", {})
    annotations = metadata.setdefault("annotations", {})
    annotations["taskflow.devops/state"] = "promoted"
    spec = release["spec"]
    spec["image"]["repository"] = IMAGE_NAME
    spec["image"]["digest"] = args.digest
    spec["image"]["signed"] = True
    spec["image"]["verifiedBy"] = "cosign-keyless"
    spec["source"]["commit"] = args.commit
    spec["source"]["workflow"] = "ci"
    spec["approval"]["approvedBy"] = args.approved_by
    spec["promotion"]["timestamp"] = datetime.now(UTC).isoformat()
    spec["promotion"]["immutable"] = True
    write_yaml(release_path, release)

    configmap_path = env_dir / "configmap.yaml"
    configmap = yaml.safe_load(configmap_path.read_text(encoding="utf-8"))
    configmap.setdefault("data", {})["APP_VERSION"] = "1.0.0"
    configmap["data"]["APP_GIT_SHA"] = args.commit[:12]
    write_yaml(configmap_path, configmap)

    kustomization = yaml.safe_load(kustomization_path.read_text(encoding="utf-8"))
    images = kustomization.setdefault("images", [])
    for item in images:
        if item.get("name") == IMAGE_NAME:
            item.pop("newTag", None)
            item["newName"] = IMAGE_NAME
            item["digest"] = args.digest
            break
    else:
        images.append({"name": IMAGE_NAME, "newName": IMAGE_NAME, "digest": args.digest})
    write_yaml(kustomization_path, kustomization)
    print(f"Updated {args.environment}: {IMAGE_NAME}@{args.digest}")


if __name__ == "__main__":
    main()
