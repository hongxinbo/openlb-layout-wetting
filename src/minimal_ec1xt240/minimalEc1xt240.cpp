// Minimal EC1XT240 plan-view baseline.
//
// This is intentionally not an OpenFOAM350 regression and not a final EC1
// model. It uses a raster directly extracted from SIM-EC1XT240.OAS, a fixed
// declared groove depth of 100 um, a conservative OpenLB phase field, and a
// reduced incompressible gas phase. Darcy, contact-angle calibration, local
// perfect-gas physics, surface tension, and z-pressing are deliberately absent
// from this first stability baseline.

#include <olb.h>

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

using namespace olb;
using namespace olb::descriptors;
using namespace olb::names;

using MinimalCase = Case<
  NavierStokes, Lattice<double, D2Q9<RHO,NABLARHO,FORCE,EXTERNAL_FORCE,TAU_EFF,SCALAR>>,
  Component1, Lattice<double, D2Q9<CONV_POPS,FORCE,VELOCITY,OLD_PHIU,STATISTIC,
                                     PSI,NORMGRADPSI,SCALAR,PSI0,THETA,BOUNDARY>>
>;

using NSDynamics = MultiPhaseIncompressibleInterfaceTRTdynamics<
  MinimalCase::value_t, MinimalCase::descriptor_t_of<NavierStokes>>;
using PhaseDynamics = ConservativePhaseFieldBGKdynamics<
  MinimalCase::value_t, MinimalCase::descriptor_t_of<Component1>>;

namespace olb::parameters {
struct MASK_INPUT : public descriptors::TYPED_FIELD_BASE<std::string,1> { };
struct OUTPUT_DIR : public descriptors::TYPED_FIELD_BASE<std::string,1> { };
struct MAX_STEPS : public descriptors::TYPED_FIELD_BASE<int,1> { };
struct METRIC_INTERVAL : public descriptors::TYPED_FIELD_BASE<int,1> { };
struct VTK_INTERVAL : public descriptors::TYPED_FIELD_BASE<int,1> { };
struct DRIVE_ACCELERATION_LATTICE : public descriptors::FIELD_BASE<1> { };
struct DRIVE_RAMP_STEPS : public descriptors::FIELD_BASE<1> { };
struct GAS_DENSITY_KG_M3 : public descriptors::FIELD_BASE<1> { };
struct GAS_NU_M2_S : public descriptors::FIELD_BASE<1> { };
struct PHASE_TAU : public descriptors::FIELD_BASE<1> { };
struct INITIAL_LIQUID_LENGTH_M : public descriptors::FIELD_BASE<1> { };
struct PHYSICAL_GROOVE_DEPTH_M : public descriptors::FIELD_BASE<1> { };
}

namespace {
using T = MinimalCase::value_t;
using NSDESCRIPTOR = MinimalCase::descriptor_t_of<NavierStokes>;
using PHIDESCRIPTOR = MinimalCase::descriptor_t_of<Component1>;

constexpr T kDx = 20.e-9;
constexpr T kLiquidDensity = 1510.;
constexpr T kLiquidDynamicViscosity = 1.e-3;
constexpr T kLiquidNu = kLiquidDynamicViscosity/kLiquidDensity;
constexpr T kDensityScale = kLiquidDensity;

class InitialLiquidBand final : public AnalyticalF2D<T,T> {
private:
  T _front;
  T _width;
public:
  InitialLiquidBand(T front, T width)
    : AnalyticalF2D<T,T>(1), _front(front), _width(width) { }

  bool operator()(T output[1], const T input[2]) override
  {
    output[0] = T(.5)*(T(1)-std::tanh((input[0]-_front)/_width));
    return true;
  }
};

struct RasterMask {
  int nx{};
  int ny{};
  std::vector<unsigned char> values;
};

RasterMask readPgm(const std::string& path)
{
  std::ifstream input(path, std::ios::binary);
  if (!input) throw std::runtime_error("cannot open OAS-derived PGM mask: "+path);
  std::string magic;
  int maxValue{};
  RasterMask mask;
  input >> magic >> mask.nx >> mask.ny >> maxValue;
  if (magic != "P5" || mask.nx <= 0 || mask.ny <= 0 || maxValue != 255) {
    throw std::runtime_error("mask must be 8-bit binary PGM (P5): "+path);
  }
  input.get();
  mask.values.resize(static_cast<std::size_t>(mask.nx)*mask.ny);
  input.read(reinterpret_cast<char*>(mask.values.data()),
             static_cast<std::streamsize>(mask.values.size()));
  if (input.gcount() != static_cast<std::streamsize>(mask.values.size())) {
    throw std::runtime_error("truncated OAS-derived PGM mask: "+path);
  }
  return mask;
}

template <typename V>
class RasterSolidIndicator2D final : public IndicatorF2D<V> {
private:
  RasterMask _mask;
  V _dx;
public:
  RasterSolidIndicator2D(const std::string& path, V dx)
    : _mask(readPgm(path)), _dx(dx)
  {
    this->_myMin = {V(),V()};
    this->_myMax = {_mask.nx*_dx,_mask.ny*_dx};
  }

  bool operator()(bool output[1], const V input[2]) override
  {
    if (input[0] < V() || input[1] < V() ||
        input[0] > this->_myMax[0] || input[1] > this->_myMax[1]) {
      output[0] = false;
      return true;
    }
    const int ix = std::clamp(static_cast<int>(std::floor(input[0]/_dx)),0,_mask.nx-1);
    const int iy = std::clamp(static_cast<int>(std::floor(input[1]/_dx)),0,_mask.ny-1);
    const int rowFromTop = _mask.ny-1-iy;
    output[0] = _mask.values[static_cast<std::size_t>(rowFromTop)*_mask.nx+ix] > 127;
    return true;
  }
};

T smoothstep(T x)
{
  x = std::clamp(x,T(),T(1));
  return x*x*x*(T(10)+x*(T(-15)+T(6)*x));
}

Mesh<T,MinimalCase::d> createMesh(MinimalCase::ParametersD& params)
{
  IndicatorCuboid2D<T> domain(params.get<parameters::DOMAIN_EXTENT>(),{0.,0.});
  Mesh<T,MinimalCase::d> mesh(domain,params.get<parameters::PHYS_DELTA_X>(),
                              singleton::mpi().getSize());
  mesh.setOverlap(params.get<parameters::OVERLAP>());
  mesh.getCuboidDecomposition().setPeriodicity({true,false});
  return mesh;
}

void prepareGeometry(MinimalCase& c)
{
  auto& geometry = c.getGeometry();
  geometry.rename(0,2);
  geometry.rename(2,1,{1,1});
  RasterSolidIndicator2D<T> solid(c.getParameters().get<parameters::MASK_INPUT>(),kDx);
  geometry.rename(1,5,solid);
  geometry.clean();
  geometry.innerClean();
  geometry.checkForErrors();
}

template <typename STAGE>
void signedDistance(MinimalCase& c)
{
  auto& phase = c.getLattice(Component1{});
  const T width = c.getParameters().get<parameters::INTERFACE_WIDTH>();
  T maximum = 1.;
  int iterations = 0;
  while (maximum <= T(1.5)*width && iterations < 100) {
    phase.getCommunicator(STAGE{}).communicate();
    phase.executePostProcessors(STAGE{});
    SuperLatticeField2D<T,PHIDESCRIPTOR,PSI> psi(phase);
    SuperMax2D<T,T> maxPsi(psi,c.getGeometry().getMaterialIndicator(1));
    int input[1] {};
    maxPsi(&maximum,input);
    ++iterations;
  }
  if (iterations == 100) throw std::runtime_error("signed-distance initialization did not converge");
}

void prepareLattices(MinimalCase& c)
{
  auto& geometry = c.getGeometry();
  auto& ns = c.getLattice(NavierStokes{});
  auto& phase = c.getLattice(Component1{});
  const auto extent = c.getParameters().get<parameters::DOMAIN_EXTENT>();
  const T tauL = c.getParameters().get<parameters::LATTICE_RELAXATION_TIME>();
  const T rhoG = c.getParameters().get<parameters::GAS_DENSITY_KG_M3>();
  const T nuG = c.getParameters().get<parameters::GAS_NU_M2_S>();
  const T tauG = nuG/kLiquidNu*(tauL-T(.5))+T(.5);
  const T width = c.getParameters().get<parameters::INTERFACE_WIDTH>();

  ns.setUnitConverter<MultiPhaseUnitConverterFromRelaxationTime<T,NSDESCRIPTOR>>(
    static_cast<int>(std::llround(extent[1]/kDx)),tauL,T(1),extent[1],kLiquidNu,kLiquidDensity);
  phase.setUnitConverter(ns.getUnitConverter());

  auto bulk = geometry.getMaterialIndicator(1);
  auto wall = geometry.getMaterialIndicator({2,5});
  auto fluid = geometry.getMaterialIndicator(1);

  dynamics::set<NSDynamics>(ns,bulk);
  dynamics::set<PhaseDynamics>(phase,bulk);
  boundary::set<boundary::BounceBackIncompressible>(ns,wall);
  boundary::set<boundary::PhaseFieldCurvedWall>(phase,wall);
  phase.addPostProcessor<stage::PreCoupling>(fluid,meta::id<RhoStatistics>());
  phase.addPostProcessor<stage::PreCoupling>(meta::id<initialPsi>{});
  phase.addPostProcessor<stage::IterativePostProcess>(bulk,meta::id<normGradPsi>{});
  phase.addPostProcessor<stage::IterativePostProcess>(meta::id<psiEvolve>{});
  phase.setParameter<psiEvolve::DELTAT>(T(.7));
  setSignedDistanceBoundary<T,PHIDESCRIPTOR>(phase,wall);

  auto& liang = c.setCouplingOperator("Liang",LiangPostProcessor{},
                                       NavierStokes{},ns,Component1{},phase);
  liang.restrictTo(fluid);
  liang.setParameter<LiangPostProcessor::SIGMA>(T()); // P2 adds reference sigma.
  liang.setParameter<LiangPostProcessor::W>(width);
  liang.setParameter<LiangPostProcessor::TAUS>({tauG,tauL});
  liang.setParameter<LiangPostProcessor::RHOS>({rhoG/kDensityScale,T(1)});
  liang.setParameter<LiangPostProcessor::SWITCH>(T(1));

  ns.setParameter<descriptors::OMEGA>(T(1)/tauL);
  ns.setParameter<collision::ITRT::TAU_MINUS>(T(1.5));
  ns.setParameter<collision::ITRT::MAXNABLARHO>((T(1)-rhoG/kDensityScale)/width);
  phase.setParameter<descriptors::OMEGA>(T(1)/c.getParameters().get<parameters::PHASE_TAU>());
  phase.setParameter<descriptors::EPSILON>(T(1.5)*width);
  phase.setParameter<descriptors::INTERFACE_WIDTH>(width);
  phase.setParameter<descriptors::MAX_VELOCITY>(T(.02));

  auto& preCoupling = phase.getCommunicator(stage::PreCoupling());
  preCoupling.requestOverlap(1);
  preCoupling.requestField<STATISTIC>();
  preCoupling.requestField<PSI>();
  preCoupling.exchangeRequests();
  auto& iterative = phase.getCommunicator(stage::IterativePostProcess());
  iterative.requestOverlap(1);
  iterative.requestField<PSI>();
  iterative.exchangeRequests();
}

void initializeFields(MinimalCase& c)
{
  auto& geometry = c.getGeometry();
  auto& ns = c.getLattice(NavierStokes{});
  auto& phase = c.getLattice(Component1{});
  const T tauL = c.getParameters().get<parameters::LATTICE_RELAXATION_TIME>();
  const T rhoG = c.getParameters().get<parameters::GAS_DENSITY_KG_M3>();
  const T nuG = c.getParameters().get<parameters::GAS_NU_M2_S>();
  const T tauG = nuG/kLiquidNu*(tauL-T(.5))+T(.5);
  const T width = c.getParameters().get<parameters::INTERFACE_WIDTH>();
  const T liquidLength = c.getParameters().get<parameters::INITIAL_LIQUID_LENGTH_M>();
  auto all = geometry.getMaterialIndicator({0,1,2,5});
  auto wall = geometry.getMaterialIndicator({2,5});
  auto fluid = geometry.getMaterialIndicator(1);

  InitialLiquidBand phi0(liquidLength,width*kDx/T(2));
  AnalyticalConst2D<T,T> rhoGas(rhoG/kDensityScale);
  AnalyticalConst2D<T,T> rhoLiquid(T(1));
  AnalyticalIdentity2D<T,T> rho0(rhoGas+(rhoLiquid-rhoGas)*phi0);
  AnalyticalConst2D<T,T> tauGas(tauG);
  AnalyticalConst2D<T,T> tauLiquid(tauL);
  AnalyticalIdentity2D<T,T> tau0(tauGas+(tauLiquid-tauGas)*phi0);
  AnalyticalConst2D<T,T> zeroScalar(T{});
  AnalyticalConst2D<T,T> zeroVelocity(T{},T{});
  AnalyticalConst2D<T,T> one(T(1));
  AnalyticalConst2D<T,T> neutralTheta(M_PI/T(2));

  fields::set<SCALAR>(ns,all,one);
  fields::set<RHO>(ns,all,rho0);
  fields::set<TAU_EFF>(ns,all,tau0);
  fields::set<EXTERNAL_FORCE>(ns,all,zeroVelocity);
  fields::set<FORCE>(ns,all,zeroVelocity);
  fields::set<OLD_PHIU>(phase,all,zeroVelocity);
  fields::set<BOUNDARY>(phase,wall,2);
  fields::set<BOUNDARY>(phase,fluid,1);
  fields::set<THETA>(phase,wall,neutralTheta);
  momenta::setOrderParameter(phase,all,phi0);
  momenta::setVelocity(phase,all,zeroVelocity);
  phase.iniEquilibrium(all,phi0,zeroVelocity);
  momenta::setIncompressiblePressure(ns,all,zeroScalar);
  momenta::setVelocity(ns,all,zeroVelocity);
  ns.iniEquilibrium(all,zeroScalar,zeroVelocity);
  phase.executePostProcessors(stage::PreCoupling());
  signedDistance<stage::IterativePostProcess>(c);
  ns.initialize();
  phase.initialize();
  phase.iniEquilibrium(all,phi0,zeroVelocity);
  ns.iniEquilibrium(all,zeroScalar,zeroVelocity);
  ns.setProcessingContext(ProcessingContext::Simulation);
  phase.setProcessingContext(ProcessingContext::Simulation);
  phase.getCommunicator(stage::PreCoupling()).communicate();
  phase.executePostProcessors(stage::PreCoupling());
  phase.getCommunicator(stage::PreCoupling()).communicate();
}

struct Snapshot {
  T sumPhi{};
  T rightHalfPhi{};
  T maxSpeed{};
  T minPhi{std::numeric_limits<T>::max()};
  T maxPhi{-std::numeric_limits<T>::max()};
  std::size_t cells{};
  std::size_t rightHalfCells{};
  std::size_t nonFiniteCells{};
};

Snapshot snapshot(MinimalCase& c)
{
  Snapshot result;
  auto& nsBlock = c.getLattice(NavierStokes{}).getBlock(0);
  auto& phaseBlock = c.getLattice(Component1{}).getBlock(0);
  auto& geometry = c.getGeometry().getBlockGeometry(0);
  const int split = geometry.getNx()/2;
  nsBlock.forCoreSpatialLocations([&](LatticeR<2> r) {
    const int material = geometry.getMaterial(r);
    if (material != 1) return;
    auto ns = nsBlock.get(r);
    auto phase = phaseBlock.get(r);
    const T phi = phase.computeRho();
    Vector<T,2> j{};
    lbm<NSDESCRIPTOR>::computeJ(ns,j);
    const T rho = ns.getField<RHO>();
    const Vector<T,2> u = j/rho;
    if (!std::isfinite(phi) || !std::isfinite(rho) || !std::isfinite(u[0]) || !std::isfinite(u[1])) {
      ++result.nonFiniteCells;
      return;
    }
    result.sumPhi += phi;
    result.minPhi = std::min(result.minPhi,phi);
    result.maxPhi = std::max(result.maxPhi,phi);
    result.maxSpeed = std::max(result.maxSpeed,util::norm<2>(u));
    if (r[0] >= split) {
      result.rightHalfPhi += phi;
      ++result.rightHalfCells;
    }
    ++result.cells;
  });
  return result;
}

void setDriveForce(MinimalCase& c, int step)
{
  const T ramp = smoothstep(T(step)/c.getParameters().get<parameters::DRIVE_RAMP_STEPS>());
  AnalyticalConst2D<T,T> force(c.getParameters().get<parameters::DRIVE_ACCELERATION_LATTICE>()*ramp,T{});
  auto& ns = c.getLattice(NavierStokes{});
  fields::set<EXTERNAL_FORCE>(ns,c.getGeometry().getMaterialIndicator(1),force);
}

void appendMetrics(MinimalCase& c, int step, const Snapshot& s, T liquidBalanceResidual)
{
  if (!singleton::mpi().isMainProcessor()) return;
  const auto& converter = c.getLattice(NavierStokes{}).getUnitConverter();
  const auto path = c.getParameters().get<parameters::OUTPUT_DIR>()+"/metrics.csv";
  const bool fresh = !std::filesystem::exists(path);
  std::ofstream stream(path,std::ios::app);
  if (fresh) stream << "step,time_s,drive_acceleration_lattice,mean_phi,right_half_phi,max_lattice_u,max_mach,liquid_balance_residual\n";
  const T meanPhi = s.cells ? s.sumPhi/T(s.cells) : T();
  const T rightPhi = s.rightHalfCells ? s.rightHalfPhi/T(s.rightHalfCells) : T();
  const T acceleration = c.getParameters().get<parameters::DRIVE_ACCELERATION_LATTICE>()
    *smoothstep(T(step)/c.getParameters().get<parameters::DRIVE_RAMP_STEPS>());
  stream << std::setprecision(17) << step << ',' << converter.getPhysTime(step) << ',' << acceleration << ','
         << meanPhi << ',' << rightPhi << ',' << s.maxSpeed << ',' << s.maxSpeed*std::sqrt(T(3)) << ','
         << liquidBalanceResidual << '\n';
}

void writeVtk(MinimalCase& c, int step)
{
  if (step % c.getParameters().get<parameters::VTK_INTERVAL>() != 0) return;
  auto& ns = c.getLattice(NavierStokes{});
  auto& phase = c.getLattice(Component1{});
  const auto& converter = ns.getUnitConverter();
  if (step == 0) {
    SuperVTMwriter2D<T> setup("minimalEc1xt240");
    SuperGeometryF<T,MinimalCase::d> geometry(c.getGeometry());
    geometry.getName() = "oas_material";
    setup.write(geometry);
    SuperLatticeCuboid2D<T,NSDESCRIPTOR> cuboid(ns);
    setup.write(cuboid);
    setup.createMasterFile();
  }
  ns.setProcessingContext(ProcessingContext::Evaluation);
  phase.setProcessingContext(ProcessingContext::Evaluation);
  SuperVTMwriter2D<T> writer("minimalEc1xt240");
  SuperLatticePhysIncPressure2D<T,NSDESCRIPTOR> pressure(ns,converter);
  pressure.getName() = "pressure_pa";
  SuperLatticePhysVelocity2D<T,NSDESCRIPTOR> velocity(ns,converter);
  velocity.getName() = "velocity_m_s";
  SuperLatticeDensity2D<T,PHIDESCRIPTOR> phi(phase);
  phi.getName() = "liquid_phase";
  writer.addFunctor(pressure);
  writer.addFunctor(velocity);
  writer.addFunctor(phi);
  writer.write(step);
  ns.setProcessingContext(ProcessingContext::Simulation);
  phase.setProcessingContext(ProcessingContext::Simulation);
}

void writeSummary(MinimalCase& c, const Snapshot& initial, const Snapshot& final,
                  T liquidBalanceResidual, bool pass)
{
  if (!singleton::mpi().isMainProcessor()) return;
  const auto& converter = c.getLattice(NavierStokes{}).getUnitConverter();
  const int steps = c.getParameters().get<parameters::MAX_STEPS>();
  const T initialRight = initial.rightHalfPhi/T(initial.rightHalfCells);
  const T finalRight = final.rightHalfPhi/T(final.rightHalfCells);
  std::ofstream stream(c.getParameters().get<parameters::OUTPUT_DIR>()+"/summary.json");
  stream << std::setprecision(17)
    << "{\n"
    << "  \"case_id\": \"minimal_ec1xt240_oas_phasefield\",\n"
    << "  \"status\": \"" << (pass ? "MINIMAL_240_RUN_PASS" : "MINIMAL_240_RUN_HOLD") << "\",\n"
    << "  \"geometry_source\": \"inputs/layouts/SIM-EC1XT240.OAS\",\n"
    << "  \"mask\": \"geometry/ec1xt240/minimal_ec1xt240_20nm.pgm\",\n"
    << "  \"geometry_depth_m\": " << c.getParameters().get<parameters::PHYSICAL_GROOVE_DEPTH_M>() << ",\n"
    << "  \"phase_model\": \"OpenLB ConservativePhaseField plus Liang coupling; sigma=0 in this minimal baseline\",\n"
    << "  \"gas_approximation\": \"reduced incompressible phase, rho_g=151 kg/m3; not perfectGas\",\n"
    << "  \"driving\": \"periodic-x representative crop with ramped uniform x acceleration\",\n"
    << "  \"steps\": " << steps << ",\n"
    << "  \"physical_time_s\": " << converter.getPhysTime(steps) << ",\n"
    << "  \"phase_range\": [" << final.minPhi << ", " << final.maxPhi << "],\n"
    << "  \"max_lattice_speed\": " << final.maxSpeed << ",\n"
    << "  \"max_mach\": " << final.maxSpeed*std::sqrt(T(3)) << ",\n"
    << "  \"initial_right_half_liquid_fraction\": " << initialRight << ",\n"
    << "  \"final_right_half_liquid_fraction\": " << finalRight << ",\n"
    << "  \"right_half_liquid_fraction_change\": " << finalRight-initialRight << ",\n"
    << "  \"liquid_inventory_boundary_residual\": " << liquidBalanceResidual << ",\n"
    << "  \"integrated_outward_liquid_volume_m3\": 0.0\n"
    << "}\n";
}

bool simulate(MinimalCase& c)
{
  auto& ns = c.getLattice(NavierStokes{});
  auto& phase = c.getLattice(Component1{});
  const int steps = c.getParameters().get<parameters::MAX_STEPS>();
  const int metricInterval = c.getParameters().get<parameters::METRIC_INTERVAL>();
  Snapshot initial = snapshot(c);
  bool stable = true;

  writeVtk(c,0);
  appendMetrics(c,0,initial,T());
  for (int step=1; step<=steps; ++step) {
    setDriveForce(c,step);
    ns.collideAndStream();
    phase.collideAndStream();
    phase.getCommunicator(stage::PreCoupling()).communicate();
    phase.executePostProcessors(stage::PreCoupling());
    if (step % 100 == 0) signedDistance<stage::IterativePostProcess>(c);
    phase.getCommunicator(stage::PreCoupling()).communicate();
    c.getOperator("Liang").apply();

    Snapshot current = snapshot(c);
    const T residual = std::abs(current.sumPhi-initial.sumPhi)
      /std::max(T(1e-30),initial.sumPhi);
    const bool bounded = current.minPhi >= T(-.05) && current.maxPhi <= T(1.05);
    const bool lowMach = current.maxSpeed*std::sqrt(T(3)) < T(.1);
    stable = current.nonFiniteCells == 0 && bounded && lowMach;
    if (step % metricInterval == 0 || !stable || step == steps) {
      appendMetrics(c,step,current,residual);
      writeVtk(c,step);
    }
    if (!stable) {
      std::cerr << "MINIMAL_240_FAIL step=" << step << " phi=[" << current.minPhi << ','
                << current.maxPhi << "] max_Ma=" << current.maxSpeed*std::sqrt(T(3))
                << " non_finite=" << current.nonFiniteCells << '\n';
      break;
    }
  }

  Snapshot final = snapshot(c);
  const T residual = std::abs(final.sumPhi-initial.sumPhi)
    /std::max(T(1e-30),initial.sumPhi);
  const T initialRight = initial.rightHalfPhi/T(initial.rightHalfCells);
  const T finalRight = final.rightHalfPhi/T(final.rightHalfCells);
  const bool moved = finalRight > initialRight+T(1e-4);
  const bool pass = stable && moved;
  writeSummary(c,initial,final,residual,pass);
  std::cout << std::setprecision(17)
            << (pass ? "MINIMAL_240_RUN_PASS" : "MINIMAL_240_RUN_HOLD")
            << " phi=[" << final.minPhi << ',' << final.maxPhi << ']'
            << " max_Ma=" << final.maxSpeed*std::sqrt(T(3))
            << " right_half_change=" << finalRight-initialRight
            << " inventory_residual=" << residual << '\n';
  return pass;
}

std::string environmentOr(const char* name, const std::string& fallback)
{
  const char* value = std::getenv(name);
  return value && *value ? std::string(value) : fallback;
}
}

int main(int argc, char* argv[])
{
  initialize(&argc,&argv);
  const std::string mask = environmentOr("MINIMAL_240_MASK",
    "../../geometry/ec1xt240/minimal_ec1xt240_20nm.pgm");
  const std::string output = environmentOr("MINIMAL_240_OUTPUT_DIR","./minimal_ec1xt240_output");
  const RasterMask raster = readPgm(mask);
  std::filesystem::create_directories(output);
  singleton::directories().setOutputDir(output+"/");

  MinimalCase::ParametersD params;
  params.set<parameters::MASK_INPUT>(mask);
  params.set<parameters::OUTPUT_DIR>(output);
  params.set<parameters::DOMAIN_EXTENT>({raster.nx*kDx,raster.ny*kDx});
  params.set<parameters::PHYS_DELTA_X>(kDx);
  params.set<parameters::LATTICE_RELAXATION_TIME>(T(.8));
  params.set<parameters::INTERFACE_WIDTH>(T(5));
  params.set<parameters::PHASE_TAU>(T(.8));
  params.set<parameters::RHO_LIQUID>(kLiquidDensity);
  params.set<parameters::NU_LIQUID>(kLiquidNu);
  params.set<parameters::GAS_DENSITY_KG_M3>(T(151));
  params.set<parameters::GAS_NU_M2_S>(T(2)*kLiquidNu);
  params.set<parameters::DRIVE_ACCELERATION_LATTICE>(T(1e-6));
  params.set<parameters::DRIVE_RAMP_STEPS>(T(1000));
  params.set<parameters::INITIAL_LIQUID_LENGTH_M>(T(.45e-6));
  params.set<parameters::PHYSICAL_GROOVE_DEPTH_M>(T(100e-6));
  params.set<parameters::MAX_STEPS>(5000);
  params.set<parameters::METRIC_INTERVAL>(100);
  params.set<parameters::VTK_INTERVAL>(1000);
  params.fromCLI(argc,argv);

  Mesh mesh = createMesh(params);
  MinimalCase c(params,mesh);
  prepareGeometry(c);
  prepareLattices(c);
  initializeFields(c);
  return simulate(c) ? EXIT_SUCCESS : EXIT_FAILURE;
}
