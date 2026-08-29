#!/bin/zsh
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
openlb_root="${OPENLB_ROOT:-$HOME/Documents/openlb}"
mask="$repo_root/geometry/ec1xt240/minimal_ec1xt240_20nm.pgm"
source_dir="$repo_root/src/minimal_ec1xt240"

if [[ ! -f "$mask" ]]; then
  echo "Missing OAS-derived mask: $mask" >&2
  exit 2
fi
if [[ ! -d "$openlb_root" ]]; then
  echo "OpenLB root does not exist: $openlb_root" >&2
  exit 2
fi

mkdir -p "$repo_root/results/minimal_ec1xt240_runs"
run_dir="$(mktemp -d "$repo_root/results/minimal_ec1xt240_runs/run_XXXXXX")"
OPENLB_ROOT="$openlb_root" make -C "$source_dir" -j2
MINIMAL_240_MASK="$mask" MINIMAL_240_OUTPUT_DIR="$run_dir" \
  "$source_dir/minimalEc1xt240"
echo "Result: $run_dir"
