// OpenFOAM350 R1 mapping-component audit.
//
// This is deliberately not a full-board solver.  It makes the dimensional
// conversion, Darcy law, moving-depth conservation, and perfect-gas closure
// executable and checks them against the frozen OF350 input contract.  The
// OpenLB UnitConverter is used directly so these checks exercise the installed
// OpenLB API without changing upstream sources.

#include <olb.h>

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
  bool c3{};
  bool c4{};
  double dt{};
  double meanSpeedLattice{};
  double maxSpeedLattice{};
  double machAtMaxSpeed{};
  bool lowMachScreenPass{};
  double c2MaxResidual{};
  double c3RelativeBalanceResidual{};
  double c4MaxRelativeEosResidual{};
  double gasSoundSpeedMps{};
  double gasAcousticDtSeconds{};
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
  // A false result is evidence against direct physical-time LBM at this scale;
  // it is not a reason to corrupt the frozen OF350 velocity input.
  r.lowMachScreenPass = r.maxSpeedLattice < 0.1;

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

  // C4: exact isothermal perfect-gas EOS from the OF350 molecular weight.
  constexpr std::array<double, 2> referencePressures{{100033.10479690798, 305213.26514994004}};
  for (double p : referencePressures) {
    const double rho = p / (kAirR * kTemperature);
    const double reconstructed = rho * kAirR * kTemperature;
    r.c4MaxRelativeEosResidual = std::max(r.c4MaxRelativeEosResidual,
      std::abs(reconstructed/p - 1.0));
  }
  require(r.c4MaxRelativeEosResidual < 1e-14, "C4: perfect-gas EOS round trip failed");
  r.c4 = true;

  // A standard isothermal D2Q9 acoustic scale cannot simultaneously reproduce
  // the ideal-air sound speed at this liquid-stable dt; report the mismatch.
  r.gasSoundSpeedMps = std::sqrt(kAirR * kTemperature);
  r.gasAcousticDtSeconds = kDx / (std::sqrt(3.0) * r.gasSoundSpeedMps);
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
      << "  \"C3_moving_layer_conservation\": \"PASS\",\n"
      << "  \"C4_perfect_gas_eos\": \"PASS\",\n"
      << "  \"liquid_dt_s_tau_0_8\": " << r.dt << ",\n"
      << "  \"reference_mean_speed_lattice\": " << r.meanSpeedLattice << ",\n"
      << "  \"reference_max_speed_lattice\": " << r.maxSpeedLattice << ",\n"
      << "  \"reference_max_speed_mach\": " << r.machAtMaxSpeed << ",\n"
      << "  \"reference_max_speed_low_mach_screen\": \"" << (r.lowMachScreenPass ? "PASS" : "FAIL") << "\",\n"
      << "  \"darcy_max_analytic_residual_Pa_m_1\": " << r.c2MaxResidual << ",\n"
      << "  \"moving_layer_relative_balance_residual\": " << r.c3RelativeBalanceResidual << ",\n"
      << "  \"perfect_gas_roundtrip_relative_residual\": " << r.c4MaxRelativeEosResidual << ",\n"
      << "  \"ideal_air_sound_speed_m_s\": " << r.gasSoundSpeedMps << ",\n"
      << "  \"dt_for_ideal_air_acoustics_s\": " << r.gasAcousticDtSeconds << ",\n"
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
    std::cout << "C0=PASS C2=PASS C3=PASS C4=PASS\n"
              << "liquid_dt_s=" << std::setprecision(12) << r.dt
              << " max_Ma=" << r.machAtMaxSpeed
              << " acoustic_steps_per_s=" << r.gasAcousticStepsPerSecond << '\n';
    return EXIT_SUCCESS;
  } catch (const std::exception& error) {
    std::cerr << "R1_COMPONENT_AUDIT_FAIL: " << error.what() << '\n';
    return EXIT_FAILURE;
  }
}
