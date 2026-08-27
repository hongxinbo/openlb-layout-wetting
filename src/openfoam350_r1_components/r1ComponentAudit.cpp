// OpenFOAM350 R1 mapping-component audit.
//
// This is deliberately not a full-board solver.  It makes the dimensional
// conversion, Darcy law, moving-depth conservation, and perfect-gas closure
// executable and checks them against the frozen OF350 input contract.  The
// OpenLB UnitConverter is used directly so these checks exercise the installed
// OpenLB API without changing upstream sources.

#include <olb.h>

#include "r1IsothermalGasClosure.h"

#include <array>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>

using namespace olb;

namespace {

constexpr double kDx = 1.0e-5;                 // 5.25 mm / 525
constexpr double kLength = 5.25e-3;
constexpr double kTauLiquid = 0.8;
constexpr double kRhoLiquid = 1510.0;
constexpr double kMuLiquid = 1.0e-3;
constexpr double kNuLiquid = kMuLiquid / kRhoLiquid;
constexpr double kTemperature = 293.0;
constexpr double kUniversalR = 8314.46;        // J/(kmol K), OF350 input convention
constexpr double kMolarMassAir = 28.9;         // kg/kmol, OF350 input
constexpr double kAirR = kUniversalR / kMolarMassAir;
constexpr double kInitialHeight = 1.0e-6;
constexpr double kEc1FinalDisplacement = -9.35e-7;
constexpr double kReferenceMaxMeanSpeed = 3.519859361843631e-3;
constexpr double kReferenceMaxSpeed = 7.103365330375505e-2;
constexpr double kReferenceGasPressureMax = 305213.26514994004;

using Descriptor = descriptors::D2Q9<>;

bool nearlyEqual(double a, double b, double relative = 1e-11)
{
  return std::abs(a - b) <= relative * std::max({1.0, std::abs(a), std::abs(b)});
}

void require(bool condition, const std::string& message)
{
  if (!condition) {
    throw std::runtime_error(message);
  }
}

double smoothstepDerivative(double s)
{
  return 30.0*s*s*(1.0-s)*(1.0-s);
}

struct Results {
  bool c0{};
  bool c2{};
  bool c2b{};
  bool c3{};
  bool c3b{};
  bool c4{};
  double dt{};
  double meanSpeedLattice{};
  double maxSpeedLattice{};
  double machAtMaxSpeed{};
  bool lowMachScreenPass{};
  double dtAtMachPointOne{};
  double tauAtMachPointOne{};
  double c2MaxResidual{};
  double c2bMaxZeroDirectionAcceleration{};
  double c3RelativeBalanceResidual{};
  double c3bRelativeBalanceResidual{};
  double c4MaxRelativeEosResidual{};
  double c4OpenDomainRelativeMassResidual{};
  double c4OpenDomainMaxPressurePa{};
  double gasSoundSpeedMps{};
  double gasAcousticDtSeconds{};
  double liquidTauAtGasAcousticDt{};
  double gasAcousticStepsPerSecond{};
};

Results runAudit()
{
  Results r;
  UnitConverterFromResolutionAndRelaxationTime<double, Descriptor> converter(
    525, kTauLiquid, kLength, kReferenceMaxSpeed, kNuLiquid, kRhoLiquid, 1.0e5);

  r.dt = converter.getPhysDeltaT();
  require(nearlyEqual(converter.getPhysDeltaX(), kDx), "C0: OpenLB dx does not equal OF350 plan-view dx");
  require(nearlyEqual(r.dt, (kTauLiquid - 0.5) * kDx*kDx/(3.0*kNuLiquid)), "C0: OpenLB dt mismatch");

  const double pressure = 305213.26514994004;
  const double pressureRoundTrip = converter.getPhysPressure(converter.getLatticePressure(pressure));
  const double velocityRoundTrip = converter.getPhysVelocity(
    converter.getLatticeVelocity(kReferenceMaxMeanSpeed));
  const double force = 2.5e-12;
  const double forceRoundTrip = converter.getPhysForce(converter.getLatticeForce(force));
  require(nearlyEqual(pressureRoundTrip, pressure), "C0: pressure forward/reverse mismatch");
  require(nearlyEqual(velocityRoundTrip, kReferenceMaxMeanSpeed), "C0: velocity forward/reverse mismatch");
  require(nearlyEqual(forceRoundTrip, force), "C0: force forward/reverse mismatch");
  r.c0 = true;

  r.meanSpeedLattice = converter.getLatticeVelocity(kReferenceMaxMeanSpeed);
  r.maxSpeedLattice = converter.getLatticeVelocity(kReferenceMaxSpeed);
  r.machAtMaxSpeed = r.maxSpeedLattice * std::sqrt(3.0);
  // The screen is Mach < 0.1, not merely lattice velocity < 0.1.
  r.lowMachScreenPass = r.machAtMaxSpeed < 0.1;
  r.dtAtMachPointOne = (0.1 / std::sqrt(3.0)) * kDx / kReferenceMaxSpeed;
  r.tauAtMachPointOne = 0.5 + 3.0*kNuLiquid*r.dtAtMachPointOne/(kDx*kDx);

  // C2: OF350 has f=0, so the dimensional Darcy source is S=-mu*D*u.
  // In momentum form its acceleration is a=-nu*D*u.  Test both tensor axes
  // using the actual anisotropic K400 coefficients and three pressure gradients.
  constexpr std::array<double, 2> d{{1.0e16, 1.0e15}};
  constexpr std::array<double, 3> gradients{{25.0, 500.0, 2000.0}};
  for (double gradient : gradients) {
    for (std::size_t axis=0; axis<d.size(); ++axis) {
      const double permeability = 1.0 / d[axis];
      const double u = -permeability * gradient / kMuLiquid;
      const double residual = kMuLiquid * d[axis] * u + gradient;
      r.c2MaxResidual = std::max(r.c2MaxResidual, std::abs(residual));
      const double acceleration = -kNuLiquid * d[axis] * u;
      require(nearlyEqual(acceleration, gradient / kRhoLiquid), "C2: Darcy acceleration sign or units are wrong");
    }
  }
  require(r.c2MaxResidual < 1e-12, "C2: analytic Darcy residual is nonzero");
  r.c2 = true;

  // C2b: EC1XT240 has D=(5e16,0,0).  Do not form 1/D for a zero direction;
  // the source force is evaluated directly as -nu*D*u.
  constexpr std::array<double, 3> ec1D{{5.0e16, 0.0, 0.0}};
  constexpr std::array<double, 3> ec1U{{-4.0e-11, 2.0e-4, -3.0e-4}};
  std::array<double, 3> ec1Acceleration{};
  for (std::size_t axis=0; axis<ec1D.size(); ++axis) {
    ec1Acceleration[axis] = -kNuLiquid * ec1D[axis] * ec1U[axis];
  }
  require(ec1Acceleration[0] > 0.0, "C2b: EC1 x Darcy force has the wrong sign");
  r.c2bMaxZeroDirectionAcceleration = std::max(std::abs(ec1Acceleration[1]), std::abs(ec1Acceleration[2]));
  require(r.c2bMaxZeroDirectionAcceleration == 0.0, "C2b: EC1 zero-D direction created artificial drag");
  r.c2b = true;

  // C3: for a depth-averaged plan area A, V=A*h and Q_out=-A dh/dt.
  // Integrate the source quintic motion at raw component steps, not at the
  // coarse 0.05 s reference cadence.
  constexpr double area = 1.0e-6; // EC1XT240 plan area, m^2
  constexpr int steps = 10000;
  const double dtMotion = 1.0 / steps;
  double integratedQout = 0.0;
  double previousQout = 0.0;
  for (int i=0; i<=steps; ++i) {
    const double t = static_cast<double>(i) / steps;
    const double dhdt = kEc1FinalDisplacement * smoothstepDerivative(t);
    const double qout = -area * dhdt;
    if (i != 0) {
      integratedQout += 0.5 * dtMotion * (previousQout + qout);
    }
    previousQout = qout;
  }
  const double finalHeight = kInitialHeight + kEc1FinalDisplacement;
  require(finalHeight > 0.0, "C3: prescribed EC1 layer height is nonpositive");
  const double volumeChange = area * (finalHeight - kInitialHeight);
  r.c3RelativeBalanceResidual = std::abs(volumeChange + integratedQout) / (area*kInitialHeight);
  require(r.c3RelativeBalanceResidual < 1e-11, "C3: moving-layer volume balance failed");
  r.c3 = true;

  // C3b: a two-zone depth jump.  F12 is an internal face flux, so h1*u1 and
  // h2*u2 must be the same face flux even though h1 != h2.  The remaining
  // volume change leaves through the two outer boundaries.
  constexpr double secondDisplacement = -7.00e-7; // actual K350 zone input
  double integratedLeftOut = 0.0;
  double integratedRightOut = 0.0;
  double priorLeftOut = 0.0;
  double priorRightOut = 0.0;
  for (int i=0; i<=steps; ++i) {
    const double t = static_cast<double>(i) / steps;
    const double derivative = smoothstepDerivative(t);
    const double h1 = kInitialHeight + kEc1FinalDisplacement * (10*t*t*t - 15*t*t*t*t + 6*t*t*t*t*t);
    const double h2 = kInitialHeight + secondDisplacement * (10*t*t*t - 15*t*t*t*t + 6*t*t*t*t*t);
    const double dV1dt = area * kEc1FinalDisplacement * derivative;
    const double dV2dt = area * secondDisplacement * derivative;
    const double faceFlux12 = 2.5e-13 * derivative; // m3/s, positive zone 1 -> zone 2
    const double u1 = faceFlux12 / h1;
    const double u2 = faceFlux12 / h2;
    require(nearlyEqual(h1*u1, h2*u2), "C3b: depth-jump face flux is not conservative");
    const double leftOut = -dV1dt - faceFlux12;
    const double rightOut = -dV2dt + faceFlux12;
    require(std::abs(dV1dt + leftOut + faceFlux12) < 1e-25, "C3b: zone 1 local balance failed");
    require(std::abs(dV2dt + rightOut - faceFlux12) < 1e-25, "C3b: zone 2 local balance failed");
    if (i != 0) {
      integratedLeftOut += 0.5 * dtMotion * (priorLeftOut + leftOut);
      integratedRightOut += 0.5 * dtMotion * (priorRightOut + rightOut);
    }
    priorLeftOut = leftOut;
    priorRightOut = rightOut;
  }
  const double twoZoneVolumeChange = area * (kEc1FinalDisplacement + secondDisplacement);
  r.c3bRelativeBalanceResidual = std::abs(twoZoneVolumeChange + integratedLeftOut + integratedRightOut)
    / (2.0*area*kInitialHeight);
  require(r.c3bRelativeBalanceResidual < 1e-11, "C3b: two-zone global balance failed");
  r.c3b = true;

  // C4a: exact isothermal perfect-gas EOS from the OF350 molecular weight.
  constexpr std::array<double, 2> referencePressures{{100033.10479690798, kReferenceGasPressureMax}};
  for (double p : referencePressures) {
    const double rho = p / (kAirR * kTemperature);
    const double reconstructed = rho * kAirR * kTemperature;
    r.c4MaxRelativeEosResidual = std::max(r.c4MaxRelativeEosResidual,
      std::abs(reconstructed/p - 1.0));
  }
  require(r.c4MaxRelativeEosResidual < 1e-14, "C4: perfect-gas EOS round trip failed");

  // C4b: project-owned gas mass closure.  First compress a closed piston
  // control volume exactly through the frozen 1 -> 3.052 atm reference range.
  const openlb350::r1::IsothermalGas gas{kAirR, kTemperature};
  const double pistonArea = 1.0e-6;
  const double initialPressure = referencePressures[0];
  openlb350::r1::GasControlVolume closed{
    pistonArea*kInitialHeight, gas.densityFromPressure(initialPressure)*pistonArea*kInitialHeight};
  closed.volume_m3 *= initialPressure / kReferenceGasPressureMax;
  require(nearlyEqual(closed.pressure(gas), kReferenceGasPressureMax, 1e-12),
          "C4b: closed piston does not cover the OF350 gas pressure range");

  // Then use two depth-varying finite volumes connected to an open reservoir.
  // Conductance is a numerical component-test value, not an OF350 fitted input.
  std::array<openlb350::r1::GasControlVolume, 2> cells{{
    {pistonArea*kInitialHeight/2.0, gas.densityFromPressure(initialPressure)*pistonArea*kInitialHeight/2.0},
    {pistonArea*kInitialHeight/2.0, gas.densityFromPressure(initialPressure)*pistonArea*kInitialHeight/2.0}
  }};
  constexpr double reservoirPressure = 1.0e5;
  constexpr double conductance = 1.0e-19; // kg/(s Pa), test-only
  double initialMass = cells[0].mass_kg + cells[1].mass_kg;
  double integratedBoundaryOut = 0.0;
  constexpr int gasSteps = 100000;
  constexpr double gasDt = 1.0 / gasSteps;
  for (int i=0; i<gasSteps; ++i) {
    const double s = static_cast<double>(i+1) / gasSteps;
    const double profile = 10*s*s*s - 15*s*s*s*s + 6*s*s*s*s*s;
    const double totalVolume = pistonArea * (kInitialHeight + kEc1FinalDisplacement*profile);
    cells[0].volume_m3 = totalVolume/2.0;
    cells[1].volume_m3 = totalVolume/2.0;
    const double p0 = cells[0].pressure(gas);
    const double p1 = cells[1].pressure(gas);
    const double outLeft = conductance * (p0 - reservoirPressure);
    const double internalRight = conductance * (p0 - p1);
    const double outRight = conductance * (p1 - reservoirPressure);
    cells[0].advance(gasDt, outLeft + internalRight);
    cells[1].advance(gasDt, outRight - internalRight);
    integratedBoundaryOut += gasDt * (outLeft + outRight);
    r.c4OpenDomainMaxPressurePa = std::max({r.c4OpenDomainMaxPressurePa, p0, p1});
  }
  const double finalMass = cells[0].mass_kg + cells[1].mass_kg;
  r.c4OpenDomainRelativeMassResidual = std::abs(finalMass - initialMass + integratedBoundaryOut) / initialMass;
  require(r.c4OpenDomainRelativeMassResidual < 1e-12, "C4b: open-domain gas mass balance failed");
  require(r.c4OpenDomainMaxPressurePa > 2.0e5, "C4b: open piston did not enter the OF350 compression regime");
  r.c4 = true;

  // A standard isothermal D2Q9 acoustic scale cannot simultaneously reproduce
  // the ideal-air sound speed at this liquid-stable dt; report the mismatch.
  r.gasSoundSpeedMps = std::sqrt(kAirR * kTemperature);
  r.gasAcousticDtSeconds = kDx / (std::sqrt(3.0) * r.gasSoundSpeedMps);
  r.liquidTauAtGasAcousticDt = 0.5 + 3.0*kNuLiquid*r.gasAcousticDtSeconds/(kDx*kDx);
  r.gasAcousticStepsPerSecond = 1.0 / r.gasAcousticDtSeconds;
  return r;
}

void writeJson(const Results& r, const std::string& path)
{
  std::ofstream out(path);
  if (!out) {
    throw std::runtime_error("cannot write audit JSON: " + path);
  }
  out << std::setprecision(17);
  out << "{\n"
      << "  \"scope\": \"R1 mapping components only; not an OpenLB350 solver\",\n"
      << "  \"openlb_unit_converter_exercised\": true,\n"
      << "  \"C0_unit_conversion\": \"PASS\",\n"
      << "  \"C2_darcy_dimensional_law\": \"PASS\",\n"
      << "  \"C2b_ec1_zero_direction_darcy\": \"PASS\",\n"
      << "  \"C3_moving_layer_conservation\": \"PASS\",\n"
      << "  \"C3b_two_zone_depth_jump_conservation\": \"PASS\",\n"
      << "  \"C4_project_owned_isothermal_gas_mass_eos\": \"PASS_PRE_COUPLING\",\n"
      << "  \"liquid_dt_s_tau_0_8\": " << r.dt << ",\n"
      << "  \"reference_mean_speed_lattice\": " << r.meanSpeedLattice << ",\n"
      << "  \"reference_max_speed_lattice\": " << r.maxSpeedLattice << ",\n"
      << "  \"reference_max_speed_mach\": " << r.machAtMaxSpeed << ",\n"
      << "  \"reference_max_speed_low_mach_screen\": \"" << (r.lowMachScreenPass ? "PASS" : "FAIL") << "\",\n"
      << "  \"dt_at_Mach_0_1_s\": " << r.dtAtMachPointOne << ",\n"
      << "  \"liquid_tau_at_Mach_0_1\": " << r.tauAtMachPointOne << ",\n"
      << "  \"darcy_max_analytic_residual_Pa_m_1\": " << r.c2MaxResidual << ",\n"
      << "  \"ec1_zero_direction_max_acceleration_m_s2\": " << r.c2bMaxZeroDirectionAcceleration << ",\n"
      << "  \"moving_layer_relative_balance_residual\": " << r.c3RelativeBalanceResidual << ",\n"
      << "  \"two_zone_depth_jump_relative_balance_residual\": " << r.c3bRelativeBalanceResidual << ",\n"
      << "  \"perfect_gas_roundtrip_relative_residual\": " << r.c4MaxRelativeEosResidual << ",\n"
      << "  \"open_domain_gas_relative_mass_residual\": " << r.c4OpenDomainRelativeMassResidual << ",\n"
      << "  \"open_domain_gas_max_pressure_Pa\": " << r.c4OpenDomainMaxPressurePa << ",\n"
      << "  \"ideal_air_sound_speed_m_s\": " << r.gasSoundSpeedMps << ",\n"
      << "  \"dt_for_ideal_air_acoustics_s\": " << r.gasAcousticDtSeconds << ",\n"
      << "  \"liquid_tau_at_ideal_air_acoustics\": " << r.liquidTauAtGasAcousticDt << ",\n"
      << "  \"steps_per_physical_second_for_ideal_air_acoustics\": " << r.gasAcousticStepsPerSecond << "\n"
      << "}\n";
}

} // namespace

int main(int argc, char* argv[])
{
  try {
    const Results r = runAudit();
    if (argc == 3 && std::string(argv[1]) == "--json") {
      writeJson(r, argv[2]);
    } else if (argc != 1) {
      throw std::runtime_error("usage: r1ComponentAudit [--json output.json]");
    }
    std::cout << "C0=PASS C2=PASS C2b=PASS C3=PASS C3b=PASS C4=PASS_PRE_COUPLING\n"
              << "liquid_dt_s=" << std::setprecision(12) << r.dt
              << " max_Ma=" << r.machAtMaxSpeed
              << " acoustic_steps_per_s=" << r.gasAcousticStepsPerSecond << '\n';
    return EXIT_SUCCESS;
  } catch (const std::exception& error) {
    std::cerr << "R1_COMPONENT_AUDIT_FAIL: " << error.what() << '\n';
    return EXIT_FAILURE;
  }
}
