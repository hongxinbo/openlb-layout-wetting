#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 NEW_EXTERNAL_BUILD_DIRECTORY" >&2
  exit 2
fi

build_dir=$1
[ ! -e "$build_dir" ] || { echo "refusing to overwrite: $build_dir" >&2; exit 2; }
openlb_root=${OPENLB_ROOT:-"$HOME/Documents/openlb"}
official_source="$openlb_root/examples/multiComponent/contactAngle3d/contactAngle3d.cpp"
patch_file="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)/patches/contactAngle3d_diagnostic_fix.patch"

[ -f "$official_source" ] || { echo "missing official source: $official_source" >&2; exit 2; }
[ -f "$patch_file" ] || { echo "missing patch: $patch_file" >&2; exit 2; }
git -C "$openlb_root" diff --exit-code HEAD -- src examples/multiComponent/contactAngle3d

mkdir -p "$(dirname "$build_dir")"
mkdir "$build_dir"
build_dir=$(CDPATH= cd -- "$build_dir" && pwd)
cp "$official_source" "$build_dir/contactAngle3d.cpp"
patch -d "$build_dir" -p0 < "$patch_file"

mpic++ -O3 -Wall -march=native -mtune=native -std=c++20 -I/opt/homebrew/include \
  '-DOLB_VERSION="1.9.0-19-g3dedbdd2"' -pthread -DPARALLEL_MODE_MPI \
  -DPLATFORM_CPU_SISD -I"$openlb_root/src" -c -o "$build_dir/contactAngle3d_corrected.o" \
  "$build_dir/contactAngle3d.cpp"
mpic++ "$build_dir/contactAngle3d_corrected.o" -o "$build_dir/contactAngle3d_corrected" \
  -lolbcore -L/opt/homebrew/lib -lpthread -lz -ltinyxml2 -L"$openlb_root/build/lib"

sha256sum() { shasum -a 256 "$1" | awk '{print $1}'; }
{
  printf 'openlb_commit='; git -C "$openlb_root" rev-parse HEAD
  printf 'official_source_sha256='; sha256sum "$official_source"
  printf 'corrected_source_sha256='; sha256sum "$build_dir/contactAngle3d.cpp"
  printf 'patch_sha256='; sha256sum "$patch_file"
  printf 'core_library_sha256='; sha256sum "$openlb_root/build/lib/libolbcore.a"
  printf 'executable_sha256='; sha256sum "$build_dir/contactAngle3d_corrected"
  printf 'compiler='; mpic++ --version | sed -n '1p'
} > "$build_dir/build_manifest.txt"
diff -u "$official_source" "$build_dir/contactAngle3d.cpp" > "$build_dir/source.diff" || test $? -eq 1
printf '%s\n' "CORRECTED_BENCHMARK_SOURCE_PARITY_PASS"
