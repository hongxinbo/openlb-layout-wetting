#!/usr/bin/env bash
# Run the conservative real-OAS pressing sidecar. This is P1A evidence, not a
# claim that the depth operator has already been coupled to OpenLB collision.
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
mask="$repo_root/geometry/ec1xt240/minimal_ec1xt240_20nm.pgm"
result_dir=$(mktemp -d "$repo_root/results/minimal_ec1xt240_runs/p1a_XXXXXX")

make -C "$repo_root/src/ec1xt240_pressing_p1" -j2
"$repo_root/src/ec1xt240_pressing_p1/p1OasDepthIntegratedPressing" \
  "$mask" "$result_dir/p1a_summary.json"
printf 'Result: %s\n' "$result_dir"
