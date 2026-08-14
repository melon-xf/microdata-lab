#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export MICRODATA_ROOT="${MICRODATA_ROOT:-${XDG_DATA_HOME:-$HOME/.local/share}/microdata-lab}"
cd "$ROOT"
exec uv run python scripts/scheduled_sync.py
