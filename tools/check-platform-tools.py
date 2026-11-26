"""Verify locally installed platform tooling created by install-platform-tools.sh."""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / ".tools" / "bin"
os.environ["PATH"] = f"{BIN}{os.pathsep}{os.environ.get('PATH', '')}"

REQUIRED_BINARIES = ("go", "helm", "kubectl", "kind", "docker", "kustomize", "sigstore")
REQUIRED_PYTHON_MODULES = ("sigstore", "kubernetes", "docker")
COMMANDS = {
    "go": ["go", "version"],
    "helm": ["helm", "version", "--short"],
    "kubectl": ["kubectl", "version", "--client"],
    "kind": ["kind", "version"],
    "docker": ["docker", "--version"],
    "sigstore": ["sigstore", "--version"],
}


def run(command: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        output = (result.stdout + result.stderr).strip()
        return result.returncode, output
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, str(exc)


def main() -> int:
    errors: list[str] = []
    print("Local platform toolchain")
    print("=" * 24)

    for name in REQUIRED_BINARIES:
        path = shutil.which(name)
        if not path:
            errors.append(f"missing local binary: {name}")
            print(f"  {name:<10} MISSING")
            continue
        print(f"  {name:<10} {path}")

    for command in COMMANDS.values():
        code, output = run(command)
        status = "ok" if code == 0 else "FAILED"
        first_line = output.splitlines()[0] if output else "(no output)"
        print(f"  {command[0]:<10} {status:<6} {first_line}")
        if code != 0:
            errors.append(f"{command[0]} command failed: {first_line}")

    code, output = run(["kustomize", "build", "deploy/gitops/environments/dev"])
    if code != 0 or not output:
        errors.append("kustomize build did not render the dev overlay")
        print(f"  kustomize  FAILED  {output.splitlines()[0] if output else 'no output'}")
    else:
        print(f"  kustomize  ok     rendered {len(output)} bytes from dev overlay")

    for module in REQUIRED_PYTHON_MODULES:
        found = importlib.util.find_spec(module) is not None
        print(f"  py:{module:<6} {'ok' if found else 'MISSING'}")
        if not found:
            errors.append(f"missing Python module: {module}")

    code, output = run(["docker", "info"])
    daemon = "available" if code == 0 else "unavailable (expected in this sandbox)"
    print(f"  docker daemon: {daemon}")

    terraform = shutil.which("terraform")
    cosign = shutil.which("cosign")
    print(f"  terraform binary: {terraform or 'blocked by sandbox allowlist'}")
    print(f"  cosign binary:    {cosign or 'blocked by sandbox allowlist'}")

    if errors:
        print("\nLocal toolchain check FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        print("Run 'make tools' to install the local toolchain.", file=sys.stderr)
        return 1
    print("\nLocal toolchain check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
