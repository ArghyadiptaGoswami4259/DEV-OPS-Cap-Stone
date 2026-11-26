#!/usr/bin/env python3
"""Build a Docker-independent TaskFlow runtime from pinned source archives.

This is intentionally source-based: official release-asset hosts are blocked in
the development sandbox, while codeload.github.com is reachable. Generated
binaries live in ignored ``.tools/`` and are never committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / ".tools"
BIN = TOOLS / "bin"
K8S_BIN = BIN / "k8s"
CONTAINERD_BIN = BIN / "containerd-bin"
CNI_BIN = BIN / "cni"
CACHE = ROOT / ".cache" / "toolchain"
SRC = CACHE / "src"
BUILD = CACHE / "build"
GOROOT = TOOLS / "go" / "go"
GO = GOROOT / "bin" / "go"
GOPATH = TOOLS / "gopath"
GOMODCACHE = GOPATH / "pkg" / "mod"
GOCACHE = TOOLS / "gocache"

SOURCE_URLS = {
    "podman": "https://codeload.github.com/containers/podman/tar.gz/refs/tags/v5.2.5",
    "conmon": "https://codeload.github.com/containers/conmon/tar.gz/refs/tags/v2.1.12",
    "glib": "https://codeload.github.com/GNOME/glib/tar.gz/refs/tags/2.74.6",
    "libseccomp": "https://codeload.github.com/seccomp/libseccomp/tar.gz/refs/tags/v2.5.5",
    "runc": "https://codeload.github.com/opencontainers/runc/tar.gz/refs/tags/v1.1.14",
    "cni": "https://codeload.github.com/containernetworking/plugins/tar.gz/refs/tags/v1.5.1",
    "containerd": "https://codeload.github.com/containerd/containerd/tar.gz/refs/tags/v1.7.20",
    "kubernetes": "https://codeload.github.com/kubernetes/kubernetes/tar.gz/refs/tags/v1.31.0",
    "etcd": "https://codeload.github.com/etcd-io/etcd/tar.gz/refs/tags/v3.5.16",
}

EXTRA_MODULES = {
    "github.com/bgentry/speakeasy": "https://codeload.github.com/bgentry/speakeasy/tar.gz/refs/tags/v0.1.0",
    "github.com/matttproud/golang_protobuf_extensions": "https://codeload.github.com/matttproud/golang_protobuf_extensions/tar.gz/refs/tags/v1.0.1",
    "github.com/olekukonko/tablewriter": "https://codeload.github.com/olekukonko/tablewriter/tar.gz/refs/tags/v0.0.5",
    "go.uber.org/atomic": "https://codeload.github.com/uber-go/atomic/tar.gz/refs/tags/v1.7.0",
    "gopkg.in/cheggaaa/pb.v1": "https://codeload.github.com/cheggaaa/pb/tar.gz/refs/tags/v1.0.28",
    "go.etcd.io/gofail": "https://codeload.github.com/etcd-io/gofail/tar.gz/refs/tags/v0.2.0",
    "golang.org/x/xerrors": "https://codeload.github.com/golang/xerrors/tar.gz/5ec99f83aff1",
    "github.com/munnerz/goautoneg": "",
}

CNI_PLUGINS = (
    "plugins/main/bridge",
    "plugins/main/loopback",
    "plugins/main/ptp",
    "plugins/main/macvlan",
    "plugins/main/ipvlan",
    "plugins/main/vlan",
    "plugins/main/host-device",
    "plugins/main/dummy",
    "plugins/main/tap",
    "plugins/ipam/host-local",
    "plugins/ipam/static",
    "plugins/meta/bandwidth",
    "plugins/meta/firewall",
    "plugins/meta/portmap",
    "plugins/meta/tuning",
    "plugins/meta/sbr",
    "plugins/meta/vrf",
)

K8S_PACKAGES = (
    "./cmd/kube-apiserver",
    "./cmd/kube-controller-manager",
    "./cmd/kube-scheduler",
    "./cmd/kubelet",
    "./cmd/kubeadm",
    "./cmd/kubectl",
    "./cmd/kube-proxy",
)

LIBSECCOMP_SOURCES = (
    "api.c",
    "system.c",
    "helper.c",
    "gen_pfc.c",
    "gen_bpf.c",
    "hash.c",
    "db.c",
    "arch.c",
    "arch-x86.c",
    "arch-x86_64.c",
    "arch-x32.c",
    "arch-arm.c",
    "arch-aarch64.c",
    "arch-mips.c",
    "arch-mips64.c",
    "arch-mips64n32.c",
    "arch-parisc.c",
    "arch-parisc64.c",
    "arch-ppc.c",
    "arch-ppc64.c",
    "arch-riscv64.c",
    "arch-s390.c",
    "arch-s390x.c",
    "syscalls.c",
    "syscalls.perf.c",
)

INTERNAL_ETCD_MODULES = {
    "go.etcd.io/etcd/api/v3": "api",
    "go.etcd.io/etcd/client/pkg/v3": "client/pkg",
    "go.etcd.io/etcd/client/v2": "client/v2",
    "go.etcd.io/etcd/client/v3": "client/v3",
    "go.etcd.io/etcd/etcdctl/v3": "etcdctl",
    "go.etcd.io/etcd/etcdutl/v3": "etcdutl",
    "go.etcd.io/etcd/pkg/v3": "pkg",
    "go.etcd.io/etcd/raft/v3": "raft",
    "go.etcd.io/etcd/server/v3": "server",
    "go.etcd.io/etcd/tests/v3": "tests",
}

GLIB_VALUES = {
    "gint16": "short",
    "gint16_modifier": '"h"',
    "gint16_format": '"hi"',
    "guint16_format": '"hu"',
    "gint32": "int",
    "gint32_modifier": '""',
    "gint32_format": '"i"',
    "guint32_format": '"u"',
    "glib_extension": "",
    "gint64": "long",
    "gint64_constant": "(val##L)",
    "guint64_constant": "(val##UL)",
    "gint64_modifier": '"l"',
    "gint64_format": '"li"',
    "guint64_format": '"lu"',
    "glib_void_p": "8",
    "glib_long": "8",
    "glib_size_t": "8",
    "glib_ssize_t": "8",
    "glib_size_type_define": "long",
    "gsize_modifier": '"l"',
    "gssize_modifier": '"l"',
    "gsize_format": '"lu"',
    "gssize_format": '"li"',
    "glib_msize_type": "LONG",
    "g_pollfd_format": '"%d"',
    "glib_gpi_cast": "(glong)",
    "glib_gpui_cast": "(gulong)",
    "glib_intptr_type_define": "long",
    "gintptr_modifier": '"l"',
    "gintptr_format": '"li"',
    "guintptr_format": '"lu"',
    "GLIB_MAJOR_VERSION": "2",
    "GLIB_MINOR_VERSION": "74",
    "GLIB_MICRO_VERSION": "6",
    "GLIB_VERSION": '"2.74.6"',
    "glib_os": "#define G_OS_UNIX",
    "glib_vacopy": "#define G_VA_COPY va_copy",
    "gintbits": "32",
    "glongbits": "64",
    "gsizebits": "64",
    "gssizebits": "64",
    "g_bs_native": "LE",
    "g_bs_alien": "BE",
    "g_byte_order": "G_LITTLE_ENDIAN",
    "g_pid_type": "int",
    "g_pid_format": '"i"',
    "g_af_unix": "1",
    "g_af_inet": "2",
    "g_af_inet6": "10",
    "g_msg_oob": "1",
    "g_msg_peek": "2",
    "g_msg_dontroute": "4",
    "g_pollin": "1",
    "g_pollout": "4",
    "g_pollpri": "2",
    "g_pollhup": "16",
    "g_pollerr": "8",
    "g_pollnval": "32",
    "g_dir_separator": "/",
    "g_searchpath_separator": ":",
    "g_module_suffix": "so",
    "g_threads_impl_def": "POSIX",
}

MESON_DEFINES = {
    "FFI_STATIC_BUILD": False,
    "GLIB_HAVE_ALLOCA_H": True,
    "GLIB_STATIC_COMPILATION": False,
    "GLIB_USING_SYSTEM_PRINTF": True,
    "GOBJECT_STATIC_COMPILATION": False,
    "G_ATOMIC_LOCK_FREE": True,
    "G_HAVE_GNUC_VISIBILITY": True,
    "G_HAVE_GROWING_STACK": False,
    "G_INTL_STATIC_COMPILATION": False,
}


def run(
    command: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run a command with the repository environment."""
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        command,
        cwd=cwd,
        env=merged,
        text=True,
        capture_output=capture_output,
        check=check,
    )


def go_env(*, cgo: bool, mod: str = "vendor", extra: dict[str, str] | None = None) -> dict[str, str]:
    """Return a hermetic Go build environment."""
    env = {
        "GOROOT": str(GOROOT),
        "GOPATH": str(GOPATH),
        "GOMODCACHE": str(GOMODCACHE),
        "GOCACHE": str(GOCACHE),
        "PATH": f"{GOROOT / 'bin'}:{BIN}:{os.environ.get('PATH', '')}",
        "GOTOOLCHAIN": "local",
        "GOFLAGS": f"-mod={mod}",
        "GOPROXY": "off",
        "GOSUMDB": "off",
        "GOPRIVATE": "*",
        "GONOSUMDB": "*",
        "GOWORK": "off",
        "CGO_ENABLED": "1" if cgo else "0",
        "GOOS": "linux",
        "GOARCH": "amd64",
    }
    if extra:
        env.update(extra)
    return env


def ensure_dirs() -> None:
    for path in (
        BIN,
        K8S_BIN,
        CONTAINERD_BIN,
        CNI_BIN,
        SRC,
        BUILD,
        GOPATH,
        GOMODCACHE,
        GOCACHE,
        TOOLS / "include",
        TOOLS / "lib" / "pkgconfig",
        TOOLS / "etc" / "containers",
        TOOLS / "etc" / "cni" / "net.d",
    ):
        path.mkdir(parents=True, exist_ok=True)


def fetch(name: str) -> Path:
    """Fetch a pinned source archive if it is not already cached."""
    archive = SRC / f"{name}.tar.gz"
    if archive.is_file() and archive.stat().st_size > 1024:
        return archive
    partial = archive.with_suffix(".tar.gz.part")
    run(
        [
            "curl",
            "-fsSL",
            "--retry",
            "3",
            "--max-time",
            "900",
            "-o",
            str(partial),
            SOURCE_URLS[name],
        ]
    )
    partial.replace(archive)
    return archive


def extract(name: str) -> Path:
    """Extract a source archive into the ignored build cache."""
    destination = BUILD / name
    marker = destination / ".taskflow-extracted"
    if marker.is_file():
        return destination
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)
    run(["tar", "-xzf", str(fetch(name)), "-C", str(destination), "--strip-components=1"])
    marker.write_text("extracted\n", encoding="utf-8")
    return destination


def binary_ready(path: Path, args: list[str] | None = None, marker: str | None = None) -> bool:
    """Check whether a generated binary exists and reports its expected version."""
    if not path.is_file() or not os.access(path, os.X_OK):
        return False
    if args is None:
        return True
    try:
        result = subprocess.run(
            [str(path), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    output = result.stdout + result.stderr
    return result.returncode == 0 and (marker is None or marker in output)


def write_glib_config(source: Path) -> None:
    """Synthesize the Meson-generated GLib header for the local conmon build."""
    template = source / "glib" / "glibconfig.h.in"
    text = template.read_text(encoding="utf-8")

    def substitute(match: re.Match[str]) -> str:
        return GLIB_VALUES.get(match.group(1), "")

    text = re.sub(r"@([A-Za-z0-9_]+)@", substitute, text)

    def define(match: re.Match[str]) -> str:
        name = match.group(1)
        return f"#define {name} 1" if MESON_DEFINES.get(name, False) else f"/* #undef {name} */"

    text = re.sub(r"^#mesondefine ([A-Za-z0-9_]+)$", define, text, flags=re.MULTILINE)
    (source / "glib" / "glibconfig.h").write_text(text, encoding="utf-8")


def build_podman() -> None:
    output = BIN / "podman"
    if binary_ready(output, ["--version"], "5.2.5"):
        print("  podman 5.2.5 is up to date")
        return
    source = extract("podman")
    tags = " ".join(
        (
            "containers_image_openpgp",
            "exclude_graphdriver_btrfs",
            "btrfs_noversion",
            "exclude_graphdriver_devicemapper",
            "exclude_graphdriver_overlay",
            "cni",
        )
    )
    print("  building podman 5.2.5")
    run(
        [str(GO), "build", "-trimpath", "-tags", tags, "-o", str(output), "./cmd/podman"],
        cwd=source,
        env=go_env(cgo=True),
    )


def build_conmon() -> None:
    output = BIN / "conmon"
    if binary_ready(output, ["--version"], "2.1.12"):
        print("  conmon 2.1.12 is up to date")
        return
    glib = extract("glib")
    source = extract("conmon")
    write_glib_config(glib)
    cflags = [
        "-std=c99",
        "-Os",
        "-Wall",
        "-Wextra",
        f"-I{glib}",
        f"-I{glib / 'glib'}",
        '-DVERSION="2.1.12"',
        '-DGIT_COMMIT="local-source-build"',
    ]
    objects: list[str] = []
    print("  building conmon 2.1.12")
    for c_file in sorted((source / "src").glob("*.c")):
        object_file = c_file.with_suffix(".o")
        run(["gcc", *cflags, "-c", str(c_file), "-o", str(object_file)])
        objects.append(str(object_file))
    run(["gcc", *cflags, "-o", str(output), *objects, "-l:libglib-2.0.so.0"])


def write_libseccomp_syscalls(source: Path) -> None:
    """Generate the gperf-equivalent syscall lookup without external gperf."""
    rows: list[tuple[str, str]] = []
    for line in (source / "src" / "syscalls.csv").read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split(",")
        name = parts[0]
        number = parts[2] if len(parts) > 2 else "PNR"
        rows.append((name, number if number.isdigit() else f"__PNR_{name}"))
    text = """/*
 * Minimal generated syscall lookup for the local seccomp runtime build.
 */
#include <errno.h>
#include <stddef.h>
#include <string.h>
#include <seccomp.h>
#include "syscalls.h"

static const char *const syscall_names[] = {
"""
    for name, _ in rows:
        text += f'\t"{name}",\n'
    text += "};\nstatic const int arch_values[] = {\n"
    for _, number in rows:
        text += f"\t{number},\n"
    text += """};

static int syscall_get_offset_value(const struct arch_syscall_table *s,
                                    int offset)
{
\treturn *(int *)((char *)s + offset);
}

int syscall_resolve_name(const char *name, int offset)
{
\tif (name == NULL)
\t\treturn -EDOM;
\tfor (size_t i = 0; i < sizeof(syscall_names) / sizeof(syscall_names[0]); i++) {
\t\tif (strcmp(name, syscall_names[i]) == 0) {
\t\t\t(void)offset;
\t\t\treturn arch_values[i];
\t\t}
\t}
\treturn -EDOM;
}

const char *syscall_resolve_num(int num, int offset)
{
\tfor (size_t i = 0; i < sizeof(syscall_names) / sizeof(syscall_names[0]); i++) {
\t\tif (arch_values[i] == num)
\t\t\treturn syscall_names[i];
\t}
\t(void)offset;
\treturn NULL;
}

const struct arch_syscall_def *syscall_iterate(unsigned int spot, int offset)
{
\tstatic struct arch_syscall_def arch_def;
\tarch_def.name = NULL;
\tarch_def.num = __NR_SCMP_ERROR;
\tif (spot < sizeof(syscall_names) / sizeof(syscall_names[0])) {
\t\tarch_def.name = syscall_names[spot];
\t\tarch_def.num = arch_values[spot];
\t}
\t(void)offset;
\treturn &arch_def;
}
"""
    (source / "src" / "syscalls.perf.c").write_text(text, encoding="utf-8")


def build_libseccomp() -> None:
    library = TOOLS / "lib" / "libseccomp.a"
    header = TOOLS / "include" / "seccomp.h"
    syscall_header = TOOLS / "include" / "seccomp-syscalls.h"
    pkg_config = BIN / "pkg-config"
    if library.is_file() and header.is_file() and syscall_header.is_file() and pkg_config.is_file():
        print("  libseccomp 2.5.5 is up to date")
        return
    source = extract("libseccomp")
    print("  building libseccomp 2.5.5")
    config = (
        '#define PACKAGE "libseccomp"\n'
        '#define PACKAGE_VERSION "2.5.5"\n'
        '#define VERSION "2.5.5"\n'
        "#define HAVE_LINUX_SECCOMP_H 1\n"
        "#define ENABLE_PYTHON 0\n"
    )
    (source / "configure.h").write_text(config, encoding="utf-8")
    (source / "src" / "configure.h").write_text(config, encoding="utf-8")
    seccomp_header = (
        (source / "include" / "seccomp.h.in")
        .read_text(encoding="utf-8")
        .replace("@VERSION_MAJOR@", "2")
        .replace("@VERSION_MINOR@", "5")
        .replace("@VERSION_MICRO@", "5")
    )
    header.write_text(seccomp_header, encoding="utf-8")
    (source / "include" / "seccomp.h").write_text(seccomp_header, encoding="utf-8")
    shutil.copy2(source / "include" / "seccomp-syscalls.h", syscall_header)
    write_libseccomp_syscalls(source)
    shim = """#!/usr/bin/env bash
ROOT="__ROOT__"
cflags=()
libs=()
for arg in "$@"; do
  case "$arg" in
    --cflags) cflags+=("-I$ROOT/include") ;;
    --libs) libs+=("-L$ROOT/lib" "-lseccomp") ;;
    --modversion|--version) echo "2.5.5"; exit 0 ;;
    --exists) exit 0 ;;
  esac
done
printf '%s\\n' "${cflags[*]} ${libs[*]}"
""".replace("__ROOT__", str(ROOT))
    pkg_config.write_text(shim, encoding="utf-8")
    pkg_config.chmod(0o755)
    cflags = [
        "-O2",
        "-fPIC",
        "-DHAVE_LINUX_SECCOMP_H=1",
        f"-I{source}",
        f"-I{source / 'include'}",
        f"-I{source / 'src'}",
        f"-I{TOOLS / 'include'}",
    ]
    objects: list[str] = []
    for name in LIBSECCOMP_SOURCES:
        object_file = BUILD / "libseccomp" / f"{name}.o"
        object_file.parent.mkdir(parents=True, exist_ok=True)
        run(["gcc", *cflags, "-c", str(source / "src" / name), "-o", str(object_file)])
        objects.append(str(object_file))
    run(["ar", "rcs", str(library), *objects])


def build_runc() -> None:
    output = BIN / "runc"
    if binary_ready(output, ["--version"], "libseccomp: 2.5.5"):
        print("  runc 1.1.14 with libseccomp is up to date")
        return
    build_libseccomp()
    source = extract("runc")
    print("  building runc 1.1.14 with seccomp support")
    extra = {
        "PKG_CONFIG": str(BIN / "pkg-config"),
        "CGO_CFLAGS": f"-I{TOOLS / 'include'}",
        "CGO_LDFLAGS": f"-L{TOOLS / 'lib'} -lseccomp -static-libgcc",
    }
    run(
        [str(GO), "build", "-trimpath", "-tags", "seccomp", "-o", str(output), "."],
        cwd=source,
        env=go_env(cgo=True, extra=extra),
    )


def build_cni() -> None:
    expected = [CNI_BIN / Path(package).name for package in CNI_PLUGINS]
    if all(path.is_file() for path in expected):
        print("  CNI plugins v1.5.1 are up to date")
        return
    source = extract("cni")
    print("  building CNI plugins v1.5.1")
    env = go_env(cgo=False)
    for package in CNI_PLUGINS:
        run(
            [
                str(GO),
                "build",
                "-trimpath",
                "-o",
                str(CNI_BIN / Path(package).name),
                f"./{package}",
            ],
            cwd=source,
            env=env,
        )


def build_containerd() -> None:
    outputs = (
        CONTAINERD_BIN / "containerd",
        CONTAINERD_BIN / "ctr",
        CONTAINERD_BIN / "containerd-shim-runc-v2",
    )
    if all(path.is_file() for path in outputs) and binary_ready(
        outputs[0], ["--version"], "1.7.20"
    ):
        print("  containerd 1.7.20 is up to date")
        return
    source = extract("containerd")
    print("  building containerd 1.7.20")
    tags = "urfave_cli_no_docs osusergo netgo static_build"
    env = go_env(cgo=False)
    for package in ("./cmd/containerd", "./cmd/ctr", "./cmd/containerd-shim-runc-v2"):
        run(
            [
                str(GO),
                "build",
                "-trimpath",
                "-tags",
                tags,
                "-o",
                str(CONTAINERD_BIN / Path(package).name),
                package,
            ],
            cwd=source,
            env=env,
        )


def prepare_kubernetes_modules(source: Path) -> None:
    """Create offline local replacements for Kubernetes' module graph."""
    result = run(
        [str(GO), "mod", "edit", "-json"],
        cwd=source,
        env=go_env(cgo=False, mod="mod"),
        capture_output=True,
    )
    info = json.loads(result.stdout)
    requires = info.get("Require", [])
    version_map = {item["Path"]: item["Version"] for item in requires}
    modules_txt = source / "vendor" / "modules.txt"
    if modules_txt.is_file():
        for line in modules_txt.read_text(encoding="utf-8").splitlines():
            match = re.match(r"^# (\S+) (\S+)(?: => .*)?$", line)
            if match:
                version_map.setdefault(match.group(1), match.group(2))
    all_paths = set(version_map)
    nested: dict[str, list[str]] = {
        path: [
            other[len(path) + 1 :]
            for other in all_paths
            if other.startswith(path + "/")
        ]
        for path in all_paths
    }
    localmods = BUILD / "kubernetes-localmods"
    shutil.rmtree(localmods, ignore_errors=True)
    localmods.mkdir(parents=True, exist_ok=True)
    module_dirs: dict[str, Path] = {}
    for path in sorted(all_paths):
        staging = source / "staging" / "src" / path
        if staging.is_dir():
            module_dirs[path] = staging
            continue
        destination = localmods / hashlib.sha1(path.encode()).hexdigest()[:16]
        vendor = source / "vendor" / path
        if vendor.is_dir():
            shutil.copytree(
                vendor,
                destination,
                ignore=shutil.ignore_patterns("go.mod", "go.sum"),
            )
            for relative in sorted(nested[path], key=len, reverse=True):
                candidate = destination / relative
                if candidate.exists():
                    shutil.rmtree(candidate, ignore_errors=True)
        else:
            destination.mkdir(parents=True, exist_ok=True)
        (destination / "go.mod").write_text(
            f"module {path}\n\ngo 1.22\n", encoding="utf-8"
        )
        module_dirs[path] = destination
    remove_replace_directives(source / "go.mod")
    command = [str(GO), "mod", "edit", "-toolchain=none"]
    for path in sorted(all_paths):
        command.extend(
            (
                f"-require={path}@{version_map.get(path, 'v0.0.0')}",
                f"-replace={path}={module_dirs[path]}",
            )
        )
    command.append(str(source / "go.mod"))
    run(command, cwd=source, env=go_env(cgo=False, mod="mod"))


def build_kubernetes() -> None:
    expected = [K8S_BIN / Path(package).name for package in K8S_PACKAGES]
    if all(path.is_file() for path in expected):
        print("  Kubernetes 1.31.0 binaries are up to date")
        return
    source = extract("kubernetes")
    (source / "go.work").unlink(missing_ok=True)
    (source / "go.work.sum").unlink(missing_ok=True)
    prepare_kubernetes_modules(source)
    print("  building Kubernetes 1.31.0 control-plane binaries")
    run(
        [
            str(GO),
            "build",
            "-mod=mod",
            "-trimpath",
            "-o",
            f"{K8S_BIN}/",
            *K8S_PACKAGES,
        ],
        cwd=source,
        env=go_env(cgo=False, mod="mod"),
    )


def safe_module_name(path: str) -> str:
    return hashlib.sha1(path.encode()).hexdigest()[:16]


def fetch_extra_module(path: str, url: str) -> Path:
    destination = BUILD / "extra" / safe_module_name(path)
    marker = destination / ".taskflow-extracted"
    if marker.is_file():
        return destination
    archive = SRC / "extra" / f"{safe_module_name(path)}.tar.gz"
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.is_file() or archive.stat().st_size <= 1024:
        partial = archive.with_suffix(".tar.gz.part")
        run(
            [
                "curl",
                "-fsSL",
                "--retry",
                "3",
                "--max-time",
                "300",
                "-o",
                str(partial),
                url,
            ]
        )
        partial.replace(archive)
    shutil.rmtree(destination, ignore_errors=True)
    destination.mkdir(parents=True, exist_ok=True)
    run(["tar", "-xzf", str(archive), "-C", str(destination), "--strip-components=1"])
    marker.write_text("extracted\n", encoding="utf-8")
    return destination


def vendor_module_paths(roots: list[Path]) -> set[str]:
    paths: set[str] = set()
    for root in roots:
        modules = root / "modules.txt"
        if not modules.is_file():
            continue
        for line in modules.read_text(encoding="utf-8").splitlines():
            if line.startswith("# "):
                paths.add(line[2:].split()[0])
    return paths


def remove_replace_directives(path: Path) -> None:
    output: list[str] = []
    in_block = False
    for line in path.read_text(encoding="utf-8").splitlines(keepends=True):
        stripped = line.strip()
        if in_block:
            if stripped == ")":
                in_block = False
            continue
        if stripped.startswith("replace ("):
            in_block = True
            continue
        if stripped.startswith("replace "):
            continue
        output.append(line)
    path.write_text("".join(output), encoding="utf-8")


def version_for(path: str) -> str:
    major = re.search(r"/v(\d+)$", path)
    if major:
        return f"v{major.group(1)}.0.0"
    dotted = re.search(r"\.v(\d+)$", path)
    if dotted:
        return f"v{dotted.group(1)}.0.0"
    return "v0.0.0"


def prepare_etcd_modules(etcd_source: Path) -> None:
    """Create local Go replacements so etcd builds without a module proxy."""
    for name in ("kubernetes", "podman", "runc", "cni", "containerd"):
        extract(name)
    roots = [BUILD / name / "vendor" for name in ("kubernetes", "podman", "runc", "cni", "containerd")]
    module_paths = vendor_module_paths(roots)
    module_paths.update(EXTRA_MODULES)
    for go_mod in etcd_source.rglob("go.mod"):
        for line in go_mod.read_text(encoding="utf-8").splitlines():
            match = re.match(r"\s*([A-Za-z0-9._~/\-]+)\s+(v[^\s]+)", line)
            if match and not match.group(1).startswith("go.etcd.io/etcd/"):
                module_paths.add(match.group(1))
    all_paths = sorted(module_paths)
    prefixes: dict[str, set[str]] = {path: set() for path in all_paths}
    for path in all_paths:
        for nested in all_paths:
            if nested.startswith(path + "/"):
                prefixes[path].add(nested[len(path) + 1 :])
    localmods = BUILD / "etcd-localmods"
    shutil.rmtree(localmods, ignore_errors=True)
    localmods.mkdir(parents=True, exist_ok=True)
    extra_dirs = {
        path: fetch_extra_module(path, url) for path, url in EXTRA_MODULES.items() if url
    }
    print(f"  preparing {len(all_paths)} local Go module replacements for etcd")
    for path in all_paths:
        source = None
        for root in roots:
            candidate = root / path
            if candidate.is_dir():
                source = candidate
                break
        if source is None:
            source = extra_dirs.get(path)
        destination = localmods / safe_module_name(path)
        if source is not None and source.is_dir():
            shutil.copytree(
                source,
                destination,
                ignore=shutil.ignore_patterns("go.mod", "go.sum"),
            )
        else:
            destination.mkdir(parents=True, exist_ok=True)
        for relative in sorted(prefixes[path], key=len, reverse=True):
            nested = destination / relative
            if nested.exists():
                shutil.rmtree(nested, ignore_errors=True)
        (destination / "go.mod").write_text(f"module {path}\n\ngo 1.22\n", encoding="utf-8")
    for go_mod in etcd_source.rglob("go.mod"):
        remove_replace_directives(go_mod)
        command = [str(GO), "mod", "edit", "-toolchain=none"]
        for path in all_paths:
            directory = localmods / safe_module_name(path)
            command.extend(
                (
                    f"-require={path}@{version_for(path)}",
                    f"-replace={path}={directory}",
                )
            )
        for path, relative in INTERNAL_ETCD_MODULES.items():
            version = "v2.305.16" if path.endswith("client/v2") else "v3.5.16"
            command.extend(
                (
                    f"-require={path}@{version}",
                    f"-replace={path}={etcd_source / relative}",
                )
            )
        command.append(str(go_mod))
        run(command, env=go_env(cgo=False, mod="mod"))


def build_etcd() -> None:
    output = BIN / "etcd"
    if binary_ready(output, ["--version"], "3.5.16"):
        print("  etcd 3.5.16 is up to date")
        return
    source = extract("etcd")
    prepare_etcd_modules(source)
    print("  building etcd 3.5.16")
    for go_sum in source.rglob("go.sum"):
        go_sum.unlink()
    (source / "go.work").unlink(missing_ok=True)
    (source / "go.work.sum").unlink(missing_ok=True)
    run(
        [str(GO), "build", "-trimpath", "-o", str(output), "."],
        cwd=source / "server",
        env=go_env(cgo=False, mod="mod"),
    )


def build_all() -> None:
    ensure_dirs()
    if not GO.is_file():
        raise SystemExit("Run 'make tools' first: the local Go toolchain is missing.")
    print("Building Docker-independent local runtime")
    build_podman()
    build_conmon()
    build_libseccomp()
    build_runc()
    build_cni()
    build_containerd()
    build_kubernetes()
    build_etcd()
    print("Local runtime build complete; run 'make local-runtime-check'.")


def print_plan() -> None:
    print("Pinned local runtime sources")
    print("=" * 30)
    for name, url in SOURCE_URLS.items():
        print(f"{name:<12} {url}")
    print("\nGenerated outputs")
    for path in (BIN, K8S_BIN, CONTAINERD_BIN, CNI_BIN, TOOLS / "lib", TOOLS / "include"):
        print(f"  {path.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="build missing runtime binaries")
    parser.add_argument("--plan", action="store_true", help="print pinned sources and outputs")
    args = parser.parse_args()
    if args.plan:
        print_plan()
    else:
        build_all()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
