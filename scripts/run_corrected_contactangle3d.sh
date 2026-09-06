#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 CORRECTED_EXTERNAL_BUILD_DIRECTORY NEW_EXTERNAL_OUTPUT_DIRECTORY" >&2
  exit 2
fi

build_dir=$1
output_dir=$2
executable="$build_dir/contactAngle3d_corrected"
[ -x "$executable" ] || { echo "missing corrected executable: $executable" >&2; exit 2; }
[ ! -e "$output_dir" ] || { echo "refusing to overwrite: $output_dir" >&2; exit 2; }

mkdir -p "$(dirname "$output_dir")"
mkdir "$output_dir"
output_dir=$(CDPATH= cd -- "$output_dir" && pwd)
cp "$build_dir/build_manifest.txt" "$output_dir/build_manifest.txt"
cp "$build_dir/source.diff" "$output_dir/source.diff"
start_epoch=$(date +%s)
set +e
(cd "$output_dir" && "$executable" > run.log 2>&1)
exit_code=$?
set -e
end_epoch=$(date +%s)
{
  printf 'command=%s\n' "$(printf '%s' "$executable")"
  printf 'explicit_overrides=[]\n'
  printf 'exit_status=%s\n' "$exit_code"
  printf 'wall_runtime_s=%s\n' "$((end_epoch-start_epoch))"
} >> "$output_dir/run_manifest.txt"
exit "$exit_code"
