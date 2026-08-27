#!/usr/bin/env bash
# Run only the R1 mapping-component contract tests.  This is not a full-board
# OpenLB350 run and does not write to the external OpenLB checkout.
set -euo pipefail

if [[ -z "${OPENLB_ROOT:-}" || -z "${OF350_CASE_ROOT:-}" ]]; then
  echo "Set OPENLB_ROOT and OF350_CASE_ROOT before running this audit." >&2
  exit 2
fi

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
component_dir="$repo_root/src/openfoam350_r1_components"
summary="$repo_root/results/summaries/openfoam350_r1_component_audit_20260827.json"

python3 "$repo_root/scripts/verify_openfoam350_baseline.py" "$OF350_CASE_ROOT"
python3 -m py_compile "$repo_root/scripts/verify_openfoam350_baseline.py" \
  "$repo_root/scripts/extract_openfoam350_reference.py"
make -C "$component_dir" OPENLB_ROOT="$OPENLB_ROOT" -j2
"$component_dir/r1ComponentAudit" --json "$summary"
python3 -m json.tool "$summary" >/dev/null
