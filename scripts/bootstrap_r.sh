#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MAMBA="${MAMBA_EXE:-$HOME/.local/bin/micromamba}"
SPEC="$ROOT/environment.lock.yml"

if [[ ! -x "$MAMBA" ]]; then
  echo "micromamba is missing at $MAMBA" >&2
  echo "Install it from https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html" >&2
  exit 1
fi

if [[ -x "$ROOT/.r-env/bin/Rscript" ]]; then
  "$MAMBA" install --yes --prefix "$ROOT/.r-env" --file "$SPEC"
else
  "$MAMBA" create --yes --prefix "$ROOT/.r-env" --file "$SPEC"
fi
"$ROOT/.r-env/bin/Rscript" -e 'stopifnot(requireNamespace("ggplot2"), requireNamespace("ragg"), requireNamespace("survey"))'
"$ROOT/.r-env/bin/Rscript" "$ROOT/scripts/register_fonts.R"
echo "R visualization and survey environment is ready."
