#!/usr/bin/env bash
set -euo pipefail
ENVIRONMENT="${1:-dev}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../terraform" && pwd)"
BACKEND="$ROOT/environments/$ENVIRONMENT.backend.hcl"
if grep -q 'REPLACE_WITH' "$BACKEND"; then
  echo "First replace placeholders in $BACKEND with bootstrap outputs." >&2
  exit 1
fi
terraform -chdir="$ROOT" init -backend-config="$BACKEND" -upgrade=false -input=false
terraform -chdir="$ROOT" validate
echo "Terraform initialized for $ENVIRONMENT. Review with:"
echo "  terraform -chdir=$ROOT plan -var-file=environments/$ENVIRONMENT.tfvars"
