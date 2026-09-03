#!/bin/zsh
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
run_root="$repo_root/results/vertical_squeeze_3d_runs"
mkdir -p "$run_root"
output_dir="${VERTICAL_SQUEEZE_3D_OUTPUT_DIR:-$(mktemp -d "$run_root/run_XXXXXX")}"
figure_dir="${VERTICAL_SQUEEZE_3D_FIGURE_DIR:-$output_dir/figures}"
pvpython_bin="${PVPYTHON:-}"

if [[ -z "$pvpython_bin" ]]; then
  pvpython_bin="$(command -v pvpython || true)"
fi
if [[ -z "$pvpython_bin" && -x /Applications/ParaView-6.1.1.app/Contents/bin/pvpython ]]; then
  pvpython_bin=/Applications/ParaView-6.1.1.app/Contents/bin/pvpython
fi
if [[ -z "$pvpython_bin" ]]; then
  echo "Set PVPYTHON to ParaView's pvpython executable." >&2
  exit 2
fi

python3 "$repo_root/scripts/generate_vertical_squeeze_3d_geometry.py" \
  --config "$repo_root/config/vertical_squeeze_3d.yaml" \
  --output-dir "$output_dir"
"$pvpython_bin" "$repo_root/scripts/render_vertical_squeeze_3d_geometry.py" \
  --input "$output_dir/vertical_squeeze_3d_geometry.vti" \
  --output-dir "$figure_dir"
