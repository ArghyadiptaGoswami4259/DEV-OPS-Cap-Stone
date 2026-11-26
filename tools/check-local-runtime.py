#!/usr/bin/env python3
"""Verify the source-built local runtime and optional live control plane."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / ".tools" / "bin"
K8S_BIN = BIN / "k8s"
CONTAINERD_BIN = BIN / "containerd-bin"
CNI_BIN = BIN / "cni"
CLUSTER = ROOT / ".cache" / "taskflow-local-cluster"
KUBECONFIG = CLUSTER / "kubeconfig" / "admin.conf"

BINARIES = (
    ("podman", BIN / "podman", ["--version"], "5.2.5"),
    ("conmon", BIN / "conmon", ["--version"], "2.1.12"),
    ("runc", BIN / "runc", ["--version"], "libseccomp: 2.5.5"),
    ("containerd", CONTAINERD_BIN / "containerd", ["--version"], "1.7.20"),
    ("ctr", CONTAINERD_BIN / "ctr", ["--version"], "1.7.20"),
    ("shim", CONTAINERD_BIN / "containerd-shim-runc-v2", None, None),
    ("etcd", BIN / "etcd", ["--version"], "3.5.16"),
    ("kube-apiserver", K8S_BIN / "kube-apiserver", ["--version"], "Kubernetes"),
    ("controller-manager", K8S_BIN / "kube-controller-manager", ["--version"], "Kubernetes"),
    ("scheduler", K8S_BIN / "kube-scheduler", ["--version"], "Kubernetes"),
    ("kubelet", K8S_BIN / "kubelet", ["--version"], "Kubernetes"),
    ("kubeadm", K8S_BIN / "kubeadm", ["version", "-o", "short"], None),
    ("kubectl", K8S_BIN / "kubectl", ["version", "--client", "-o", "yaml"], None),
)

REQUIRED_CNI = ("bridge", "host-local", "loopback", "portmap", "ptp")
REQUIRED_LIBS = (
    ROOT / ".tools" / "lib" / "libseccomp.a",
    ROOT / ".tools" / "include" / "seccomp.h",
    ROOT / ".tools" / "include" / "seccomp-syscalls.h",
    BIN / "pkg-config",
)


def kubectl(*args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Run the locally built kubectl against the local kubeconfig."""
    return subprocess.run(
        [str(K8S_BIN / "kubectl"), f"--kubeconfig={KUBECONFIG}", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def offline_check() -> list[str]:
    errors: list[str] = []
    print("Local runtime binaries")
    print("=" * 21)
    for label, path, args, marker in BINARIES:
        if not path.is_file() or not os.access(path, os.X_OK):
            errors.append(f"{label}: missing executable at {path.relative_to(ROOT)}")
            print(f"  {label:<20} MISSING")
            continue
        output = ""
        if args:
            try:
                result = subprocess.run(
                    [str(path), *args],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                output = (result.stdout + result.stderr).strip()
                if result.returncode != 0 or (marker and marker not in output):
                    errors.append(f"{label}: version output did not contain {marker!r}")
            except (OSError, subprocess.TimeoutExpired) as exc:
                errors.append(f"{label}: version check failed: {exc}")
        first_line = output.splitlines()[0] if output else "installed"
        print(f"  {label:<20} {first_line}")
    print("\nSupporting artifacts")
    for name in REQUIRED_CNI:
        path = CNI_BIN / name
        present = path.is_file() and os.access(path, os.X_OK)
        print(f"  CNI {name:<16} {'ok' if present else 'MISSING'}")
        if not present:
            errors.append(f"missing CNI plugin: {name}")
    for path in REQUIRED_LIBS:
        present = path.is_file()
        print(f"  {str(path.relative_to(ROOT)):<35} {'ok' if present else 'MISSING'}")
        if not present:
            errors.append(f"missing runtime artifact: {path.relative_to(ROOT)}")
    return errors


def cluster_check() -> list[str]:
    errors: list[str] = offline_check()
    print("\nLive local cluster")
    print("=" * 18)
    if not KUBECONFIG.is_file():
        errors.append("local cluster kubeconfig is missing; run 'make local-cluster-up'")
        print("  kubeconfig          MISSING")
        return errors
    ready = ""
    for attempt in range(1, 31):
        try:
            result = kubectl(
                "--request-timeout=2s", "get", "--raw=/readyz", timeout=5
            )
            if result.returncode == 0 and result.stdout.strip() == "ok":
                ready = "ok"
                break
        except subprocess.TimeoutExpired:
            # Retry until the API server is ready or the attempt budget is exhausted.
            continue
        if attempt < 30:
            time.sleep(1)
    print(f"  /readyz             {ready or 'unreachable'}")
    if ready != "ok":
        errors.append("local API server did not report /readyz=ok")
        return errors

    checks = (
        (
            "nodes",
            ["get", "nodes", "-o", "json"],
            lambda output: _check_nodes(output, errors),
        ),
        (
            "components",
            ["get", "componentstatuses", "-o", "json"],
            lambda output: _check_components(output, errors),
        ),
        (
            "pod",
            ["get", "pod", "taskflow-runtime-probe", "-o", "json"],
            lambda output: _check_probe(output, errors),
        ),
        (
            "logs",
            ["logs", "taskflow-runtime-probe"],
            lambda output: _check_logs(output, errors),
        ),
    )
    for label, args, verifier in checks:
        try:
            result = kubectl(*args)
        except subprocess.TimeoutExpired:
            errors.append(f"{label}: kubectl timed out")
            print(f"  {label:<20} timed out")
            continue
        output = result.stdout.strip()
        if result.returncode != 0:
            detail = (result.stderr or output).splitlines()
            errors.append(f"{label}: kubectl failed: {detail[-1] if detail else 'unknown'}")
            print(f"  {label:<20} FAILED")
            continue
        verifier(output)
    return errors


def _check_nodes(output: str, errors: list[str]) -> None:
    items = json.loads(output).get("items", [])
    ready = [
        item
        for item in items
        if any(
            condition.get("type") == "Ready" and condition.get("status") == "True"
            for condition in item.get("status", {}).get("conditions", [])
        )
    ]
    runtime = ""
    if items:
        runtime = items[0].get("status", {}).get("nodeInfo", {}).get("containerRuntimeVersion", "")
    print(f"  Ready nodes         {len(ready)} / {len(items)} ({runtime})")
    if not ready or "containerd://" not in runtime:
        errors.append("expected one Ready node using the local containerd runtime")


def _check_components(output: str, errors: list[str]) -> None:
    items = json.loads(output).get("items", [])
    healthy = [
        item
        for item in items
        if any(
            condition.get("type") == "Healthy" and condition.get("status") == "True"
            for condition in item.get("conditions", [])
        )
    ]
    names = ", ".join(item["metadata"]["name"] for item in items)
    print(f"  Healthy components  {len(healthy)} / {len(items)} ({names})")
    if len(items) < 3 or len(healthy) != len(items):
        errors.append("expected etcd, controller-manager and scheduler to be Healthy")


def _check_probe(output: str, errors: list[str]) -> None:
    pod = json.loads(output)
    phase = pod.get("status", {}).get("phase", "")
    pod_ip = pod.get("status", {}).get("podIP", "")
    print(f"  Runtime probe       {phase} (IP {pod_ip or 'none'})")
    if phase != "Succeeded" or not pod_ip:
        errors.append("expected taskflow-runtime-probe to complete with an assigned pod IP")


def _check_logs(output: str, errors: list[str]) -> None:
    print(f"  Probe logs          {output!r}")
    if "hello from rootful podman" not in output:
        errors.append("expected probe logs to contain 'hello from rootful podman'")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--offline", action="store_true", help="check generated binaries only")
    group.add_argument("--cluster", action="store_true", help="also check a live local cluster")
    args = parser.parse_args()
    errors = cluster_check() if args.cluster else offline_check()
    if errors:
        print("\nLocal runtime validation FAILED:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1
    title = "Local cluster validation passed" if args.cluster else "Offline runtime validation passed"
    print(f"\n{title}: pinned binaries, supporting artifacts"
          + (" and live Kubernetes readiness." if args.cluster else "."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
