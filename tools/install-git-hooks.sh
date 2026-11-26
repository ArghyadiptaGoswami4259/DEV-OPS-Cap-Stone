#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_DIR="$ROOT/.git/hooks"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then PY="python3"; fi
mkdir -p "$HOOK_DIR"
cat > "$HOOK_DIR/commit-msg" <<EOS
#!/usr/bin/env bash
exec "$PY" "$ROOT/tools/check_commit_message.py" "\$1"
EOS
cat > "$HOOK_DIR/pre-commit" <<EOS
#!/usr/bin/env bash
set -e
"$PY" -m ruff check "$ROOT"
"$PY" -m pytest -q "$ROOT/tests"
EOS
chmod +x "$HOOK_DIR/commit-msg" "$HOOK_DIR/pre-commit"
echo "Installed commit-msg and pre-commit hooks."
