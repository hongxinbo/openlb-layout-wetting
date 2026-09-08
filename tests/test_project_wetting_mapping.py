#!/usr/bin/env python3
"""Regression checks for the frozen phi=0 converter mapping."""

from math import isclose


rho = 1510.0
mu = 1.0e-3
nu_target = mu / rho
dx = 70e-6 / 70
tau_droplet = 0.52
tau_ambient = 1.0
nu_lb_droplet = (tau_droplet - 0.5) / 3
nu_lb_ambient = (tau_ambient - 0.5) / 3
nu_reference = nu_target * nu_lb_ambient / nu_lb_droplet
dt = (tau_ambient - 0.5) * dx**2 / (3 * nu_reference)
nu_unit = dx**2 / dt
sigma_unit = rho * dx**3 / dt**2
sigma_lb = 0.0309 / sigma_unit

assert isclose(nu_lb_ambient / nu_lb_droplet, 25.0)
assert isclose(nu_reference, 1.6556291390728477e-5)
assert isclose(nu_lb_droplet * nu_unit, nu_target)
assert isclose(nu_lb_ambient * nu_unit, nu_reference)
assert isclose(dt, 1.0066666666666666e-8)
assert isclose(sigma_unit, 14.90066225165563)
assert isclose(sigma_lb, 0.002073733333333333)
print("PROJECT_WETTING_MAPPING_EQUATION_PASS")
