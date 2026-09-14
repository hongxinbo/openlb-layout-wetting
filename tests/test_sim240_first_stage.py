import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_sim240_release_and_geometry():
    s=json.loads((ROOT/'results/summaries/sim240_first_stage.json').read_text())
    assert s['status']=='SIM240_FIRST_STAGE_PASS'
    assert s['next']=='SIM240_INTERPRET_AND_REPORT_RESULTS'
    assert all(v=='PASS' for v in s['case_status'].values())
    assert [r['fluid_cells'] for r in (s['runs']['flat'][0],s['runs']['along'][0],s['runs']['across'][0])]==[48*480*15,480*(48*15+24*20),480*48*15+10*24*48*20]

def test_sim240_quality_and_ratios():
    s=json.loads((ROOT/'results/summaries/sim240_first_stage.json').read_text())
    assert all(f['r2_primary']>=.999 for f in s['fits_primary'].values())
    assert all(f['r2_interior']>=.999 for f in s['fits_interior'].values())
    assert s['flat_profile_normalized_l2']<.03
    assert abs(s['fits_primary']['flat']['R_primary_fitted_pa_s_m3']/s['flat_analytical_R_pa_s_m3']-1)<.03
    assert s['ratios_primary']['R_para_over_R0']<s['ratios_primary']['R_perp_over_R0']<1
    assert s['ratios_interior']['R_para_interior_over_R0_interior']<s['ratios_interior']['R_perp_interior_over_R0_interior']<1
    assert s['ranking_robust'] is True
    for rows in s['runs'].values():
        for r in rows:
            assert r['steady'] and r['max_lattice_mach']<.01
            assert abs(r['mass_drift_fraction'])<1e-5
            for name in ('resistance_qin_pa_s_m3','resistance_qmid_pa_s_m3','resistance_qmean_pa_s_m3','resistance_qout_pa_s_m3'):
                assert r[name]>0
            assert r['legacy_resistance_pa_s_m3']==r['resistance_qmean_pa_s_m3']
