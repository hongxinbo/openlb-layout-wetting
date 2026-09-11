import json,subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as d:
 subprocess.run(["python3",str(root/"scripts/run_translating_embedding.py"),"--output-dir",d],check=True)
 p0=json.loads((Path(d)/"translating_embedding_P0.json").read_text())
 p1=json.loads((Path(d)/"translating_embedding_P1.json").read_text())
 assert p0["status"]=="TRANSLATING_REEMBEDDING_STATIC_PARITY_HOLD_OFFICIAL_RUNTIME"
 assert p0["max_abs_difference"]==p0["L1_difference"]==0 and p0["mismatched_cells"]==0
 assert p1["status"]=="PRESCRIBED_TRANSLATING_EMBEDDING_FIELD_PASS_ALGORITHMIC_ONLY"
 assert p1["translation_cells"]>1 and p1["communication"]["status"]=="TRANSLATING_REEMBEDDING_COMMUNICATION_HOLD" and p1["communication"]["overlap_mismatches"]==0
 for x in p1["checkpoints"]:
  assert x["position_error"]==x["solid_volume_drift"]==x["wall_velocity_error"]==0
  assert x["stale_old_footprint_cells"]==x["missing_new_footprint_cells"]==0 and x["fields_finite"]
print("TRANSLATING_EMBEDDING_TEST_PASS")
