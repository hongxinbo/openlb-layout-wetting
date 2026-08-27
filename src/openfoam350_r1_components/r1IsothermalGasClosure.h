#pragma once

#include <cmath>
#include <stdexcept>

// Project-owned isothermal gas mass/EOS primitive.  It is intentionally
// independent of a particular LBM collision model so that its conservation
// convention can be tested before phase-field coupling is attempted.
namespace openlb350::r1 {

struct IsothermalGas {
  double gasConstant_J_kg_K;
  double temperature_K;

  double densityFromPressure(double pressure_Pa) const
  {
    return pressure_Pa / (gasConstant_J_kg_K * temperature_K);
  }

  double pressureFromDensity(double density_kg_m3) const
  {
    return density_kg_m3 * gasConstant_J_kg_K * temperature_K;
  }
};

struct GasControlVolume {
  double volume_m3;
  double mass_kg;

  double density() const
  {
    if (!(volume_m3 > 0.0) || !(mass_kg > 0.0)) {
      throw std::runtime_error("gas control volume must retain positive volume and mass");
    }
    return mass_kg / volume_m3;
  }

  double pressure(const IsothermalGas& gas) const
  {
    return gas.pressureFromDensity(density());
  }

  // Positive flux is outward. This is the finite-volume convention used by
  // the component tests: m_new = m_old - dt * sum(F_out).
  void advance(double dt_s, double outwardMassFlux_kg_s)
  {
    mass_kg -= dt_s * outwardMassFlux_kg_s;
    if (!(mass_kg > 0.0)) {
      throw std::runtime_error("gas update depleted the control volume");
    }
  }
};

} // namespace openlb350::r1
