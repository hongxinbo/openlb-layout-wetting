"""Analytic caps test observable geometry independently of a solver run."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import numpy as np
from analyze_official_contactangle3d import official
from analyze_prepress_component import measure_interface

for theta in (60.,100.):
    domain=[120,75,120]; extent=(0,120,0,75,0,120)
    z,y,x=np.mgrid[0:121,0:76,0:121]
    radius=30.; yc=.5-radius*np.cos(np.deg2rad(theta))
    distance=np.sqrt((x-60)**2+(y-yc)**2+(z-60)**2)-radius
    phi=.5*(1+np.tanh(distance/2))
    fit=measure_interface(phi,extent,domain,.5,1e-6)
    three=official(phi,extent,domain,True)
    assert abs(fit['contact_angle_primary_deg']-theta)<.2,fit
    assert abs(three['angle_deg']-theta)<.2,three
    if theta>90:
        assert fit['contact_angle_tangent_diagnostic_deg']<=90
print('PASS: independent 60/100-degree cap circle and corrected three-point; legacy tangent cannot represent obtuse angles')
