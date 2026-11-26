#!/usr/bin/env bash
# Build the Docker-independent TaskFlow local runtime into ignored .tools/.
# All source archives come from allowlisted codeload.github.com URLs.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
GO="$ROOT/.tools/go/go/bin/go"

if [[ ! -x "$PY" ]]; then
  echo "Run 'make install' first: $PY is missing." >&2
  exit 1
fi
if [[ ! -x "$GO" ]]; then
  echo "Run 'make tools' first: $GO is missing." >&2
  exit 1
fi
for command_name in gcc ar curl tar sudo ip; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Required local build command is missing: $command_name" >&2
    exit 1
  fi
done

exec "$PY" "$ROOT/tools/build_local_runtime.py" --build
