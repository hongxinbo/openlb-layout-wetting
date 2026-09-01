// Minimal EC1XT240 plan-view baseline.
//
// This is intentionally not an OpenFOAM350 regression and not a final EC1
// model. It uses a raster directly extracted from SIM-EC1XT240.OAS, a fixed
// declared groove depth of 100 um, a conservative OpenLB phase field, and a
// reduced incompressible gas phase.  Surface tension and a wall contact-angle
// input are enabled for the physical-baseline and component-test modes; their
// validation status is deliberately reported separately from runtime health.
// Darcy, local perfect-gas physics, and an explicitly resolved z-pressing mesh
// are outside this reduced model.

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
struct OPEN_BOUNDARY : public descriptors::FIELD_BASE<1> { };
struct SURFACE_TENSION_N_M : public descriptors::FIELD_BASE<1> { };
struct CONTACT_ANGLE_DEG : public descriptors::FIELD_BASE<1> { };
struct PRESSURE_DRIVE_PA : public descriptors::FIELD_BASE<1> { };
struct CASE_LABEL : public descriptors::TYPED_FIELD_BASE<std::string,1> { };
struct GEOMETRY_SOURCE : public descriptors::TYPED_FIELD_BASE<std::string,1> { };
struct STRAIGHT_CHANNEL : public descriptors::FIELD_BASE<1> { };
struct STRAIGHT_CHANNEL_WIDTH_M : public descriptors::FIELD_BASE<1> { };
struct WETTING_DROPLET : public descriptors::FIELD_BASE<1> { };
struct DROPLET_RADIUS_M : public descriptors::FIELD_BASE<1> { };
// These thresholds classify resolved intrusion in the summary.  They do not
// turn a numerically healthy run into a solver failure; the runtime launcher
// applies the formal-baseline release policy to the emitted metrics.
struct RESOLVED_FRONT_PROGRESS_CELLS : public descriptors::FIELD_BASE<1> { };
struct RESOLVED_UPTAKE_CELL_EQUIVALENTS : public descriptors::FIELD_BASE<1> { };
struct STOP_ON_RESOLVED_INTRUSION : public descriptors::FIELD_BASE<1> { };
}

namespace {
using T = MinimalCase::value_t;
using NSDESCRIPTOR = MinimalCase::descriptor_t_of<NavierStokes>;
using PHIDESCRIPTOR = MinimalCase::descriptor_t_of<Component1>;

constexpr T kDefaultDx = 20.e-9;
constexpr T kDefaultLiquidDensity = 1510.;
constexpr T kDefaultLiquidDynamicViscosity = 1.e-3;
constexpr T kDefaultLiquidNu = kDefaultLiquidDynamicViscosity/kDefaultLiquidDensity;

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

class InitialLiquidDroplet final : public AnalyticalF2D<T,T> {
private:
  T _x;
  T _y;
  T _radius;
  T _width;
public:
  InitialLiquidDroplet(T x, T y, T radius, T width)
    : AnalyticalF2D<T,T>(1), _x(x), _y(y), _radius(radius), _width(width) { }

  bool operator()(T output[1], const T input[2]) override
  {
    const T distance = std::hypot(input[0]-_x,input[1]-_y);
    output[0] = T(.5)*(T(1)-std::tanh((distance-_radius)/_width));
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

template <typename V>
class StraightChannelSolidIndicator2D final : public IndicatorF2D<V> {
private:
  V _height;
  V _width;
public:
  StraightChannelSolidIndicator2D(V height, V width)
    : _height(height), _width(width)
  {
    this->_myMin = {V(),V()};
    this->_myMax = {V(),_height};
  }

  bool operator()(bool output[1], const V input[2]) override
  {
    const V half = _width/T(2);
    output[0] = std::abs(input[1]-_height/T(2)) > half;
    return true;
  }
};

T smoothstep(T x)
{
  x = std::clamp(x,T(),T(1));
  return x*x*x*(T(10)+x*(T(-15)+T(6)*x));
}

void trimConvectiveOutletCorners(SuperGeometry<T,2>& geometry)
{
  // OpenLB 1.9's convective phase-field outlet accepts only a flat normal.
  // Keep material 4 only where both transverse neighbours are also outlet
  // cells; reclassify the one-cell stripe endpoints as wall material 5.
  // This is evaluated per local block. The current production launcher is
  // single-rank, while the local-neighbour test remains valid for each block.
  for (int iC=0; iC<geometry.getLoadBalancer().size(); ++iC) {
    auto& block = geometry.getBlockGeometry(iC);
    std::vector<LatticeR<2>> corners;
    block.forCoreSpatialLocations([&](LatticeR<2> r) {
      if (block.getMaterial(r) != 4) return;
      if (block.getMaterial({r[0],r[1]-1}) != 4
          || block.getMaterial({r[0],r[1]+1}) != 4) {
        corners.push_back(r);
      }
    });
    for (const auto& r : corners) block.set(r,5);
  }
  geometry.getStatisticsStatus() = true;
  geometry.updateStatistics(false);
}

Mesh<T,MinimalCase::d> createMesh(MinimalCase::ParametersD& params)
{
  IndicatorCuboid2D<T> domain(params.get<parameters::DOMAIN_EXTENT>(),{0.,0.});
  Mesh<T,MinimalCase::d> mesh(domain,params.get<parameters::PHYS_DELTA_X>(),
                              singleton::mpi().getSize());
  mesh.setOverlap(params.get<parameters::OVERLAP>());
  if (params.get<parameters::OPEN_BOUNDARY>() < T(.5)
      && params.get<parameters::STRAIGHT_CHANNEL>() < T(.5)) {
    mesh.getCuboidDecomposition().setPeriodicity({true,false});
  }
  return mesh;
}

void prepareGeometry(MinimalCase& c)
{
  auto& geometry = c.getGeometry();
  const T dx = c.getParameters().get<parameters::PHYS_DELTA_X>();
  geometry.rename(0,2);
  const bool straight = c.getParameters().get<parameters::STRAIGHT_CHANNEL>() > T(.5);
  if (straight) {
    // Keep a one-cell exterior wall frame, as in OpenLB's channel examples.
    // The component droplet is then a closed, non-periodic wall test rather
    // than a malformed periodic strip with open side voxels.
    geometry.rename(2,1,{1,1});
    const auto extent = c.getParameters().get<parameters::DOMAIN_EXTENT>();
    StraightChannelSolidIndicator2D<T> solid(extent[1],
      c.getParameters().get<parameters::STRAIGHT_CHANNEL_WIDTH_M>());
    geometry.rename(1,5,solid);
  } else {
    geometry.rename(2,1,{1,1});
    RasterSolidIndicator2D<T> solid(c.getParameters().get<parameters::MASK_INPUT>(),dx);
    geometry.rename(1,5,solid);
  }
  if (c.getParameters().get<parameters::OPEN_BOUNDARY>() > T(.5)) {
    const auto extent = c.getParameters().get<parameters::DOMAIN_EXTENT>();
    IndicatorCuboid2D<T> inlet(dx,extent[1]-T(2)*dx,{T(),extent[1]/T(2)});
    IndicatorCuboid2D<T> outlet(dx,extent[1]-T(2)*dx,{extent[0],extent[1]/T(2)});
    geometry.rename(2,3,inlet);
    geometry.rename(2,4,outlet);
  }
  geometry.clean();
  geometry.innerClean();
  if (c.getParameters().get<parameters::OPEN_BOUNDARY>() > T(.5)) {
    // `setConvectivePhaseFieldBoundary` is defined only for a flat discrete
    // normal.  A multi-channel OAS crop can end a fluid stripe against a wall
    // at the artificial x outlet, which leaves a one-cell outlet corner with
    // no flat normal.  Reclassify only those transverse endpoint voxels as
    // wall: the remaining material-4 cells are the open, flat parts of each
    // physical outlet stripe.  The EC1 baseline is re-run after this
    // generalization so its frozen QoI compatibility is checked explicitly.
    trimConvectiveOutletCorners(geometry);
  }
  geometry.checkForErrors();
  if (c.getParameters().get<parameters::OPEN_BOUNDARY>() > T(.5)) {
    geometry.getStatistics().print();
  }
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
  const T dx = c.getParameters().get<parameters::PHYS_DELTA_X>();
  const T tauL = c.getParameters().get<parameters::LATTICE_RELAXATION_TIME>();
  const T rhoL = c.getParameters().get<parameters::RHO_LIQUID>();
  const T nuL = c.getParameters().get<parameters::NU_LIQUID>();
  const T rhoG = c.getParameters().get<parameters::GAS_DENSITY_KG_M3>();
  const T nuG = c.getParameters().get<parameters::GAS_NU_M2_S>();
  const T tauG = nuG/nuL*(tauL-T(.5))+T(.5);
  const T width = c.getParameters().get<parameters::INTERFACE_WIDTH>();

  ns.setUnitConverter<MultiPhaseUnitConverterFromRelaxationTime<T,NSDESCRIPTOR>>(
    static_cast<int>(std::llround(extent[1]/dx)),tauL,T(1),extent[1],nuL,rhoL);
  phase.setUnitConverter(ns.getUnitConverter());

  auto bulk = geometry.getMaterialIndicator(1);
  auto wall = geometry.getMaterialIndicator({2,5});
  auto fluid = geometry.getMaterialIndicator(1);
  auto inlet = geometry.getMaterialIndicator(3);
  auto outlet = geometry.getMaterialIndicator(4);
  auto pressureFluid = geometry.getMaterialIndicator({1,3});

  dynamics::set<NSDynamics>(ns,bulk);
  dynamics::set<PhaseDynamics>(phase,bulk);
  boundary::set<boundary::BounceBackIncompressible>(ns,wall);
  boundary::set<boundary::PhaseFieldCurvedWall>(phase,wall);
  if (c.getParameters().get<parameters::OPEN_BOUNDARY>() > T(.5)) {
    boundary::set<boundary::RegularizedTemperature>(phase,inlet);
    boundary::set<boundary::IncompressibleZouHePressure>(ns,inlet);
    boundary::set<boundary::IncompressibleZouHePressure>(ns,outlet);
    setConvectivePhaseFieldBoundary<T,PHIDESCRIPTOR>(phase,outlet);
    phase.addPostProcessor<stage::InitOutlet>(outlet,meta::id<SetOutletCells2D<1,0>>());
  }
  phase.addPostProcessor<stage::PreCoupling>(pressureFluid,meta::id<RhoStatistics>());
  phase.addPostProcessor<stage::PreCoupling>(meta::id<initialPsi>{});
  phase.addPostProcessor<stage::IterativePostProcess>(bulk,meta::id<normGradPsi>{});
  phase.addPostProcessor<stage::IterativePostProcess>(meta::id<psiEvolve>{});
  phase.setParameter<psiEvolve::DELTAT>(T(.7));
  setSignedDistanceBoundary<T,PHIDESCRIPTOR>(phase,wall);
  if (c.getParameters().get<parameters::OPEN_BOUNDARY>() > T(.5)) {
    setSignedDistanceBoundary<T,PHIDESCRIPTOR>(phase,inlet);
    setSignedDistanceBoundary<T,PHIDESCRIPTOR>(phase,outlet);
  }

  auto& liang = c.setCouplingOperator("Liang",LiangPostProcessor{},
                                       NavierStokes{},ns,Component1{},phase);
  if (c.getParameters().get<parameters::OPEN_BOUNDARY>() > T(.5)) {
    liang.restrictTo(geometry.getMaterialIndicator({1,4}));
  } else {
    liang.restrictTo(fluid);
  }
  liang.setParameter<LiangPostProcessor::SIGMA>(
    c.getParameters().get<parameters::SURFACE_TENSION_N_M>()
      /ns.getUnitConverter().getConversionFactorSurfaceTension());
  liang.setParameter<LiangPostProcessor::W>(width);
  liang.setParameter<LiangPostProcessor::TAUS>({tauG,tauL});
  liang.setParameter<LiangPostProcessor::RHOS>({rhoG/rhoL,T(1)});
  liang.setParameter<LiangPostProcessor::SWITCH>(T(1));
  if (c.getParameters().get<parameters::OPEN_BOUNDARY>() > T(.5)) {
    auto& velocityCoupling = c.setCouplingOperator("InletVelocity",VelocityCoupling{},
      NavierStokes{},ns,Component1{},phase);
    velocityCoupling.restrictTo(inlet);
  }

  ns.setParameter<descriptors::OMEGA>(T(1)/tauL);
  ns.setParameter<collision::ITRT::TAU_MINUS>(T(1.5));
  ns.setParameter<collision::ITRT::MAXNABLARHO>((T(1)-rhoG/rhoL)/width);
  phase.setParameter<descriptors::OMEGA>(T(1)/c.getParameters().get<parameters::PHASE_TAU>());
  // OpenLB 1.9 PhaseFieldCurvedWall uses the lattice parameter in its
  // IsoPhaseFieldCurvedWall2D processor. The wall-cell field is still written
  // below as auditable metadata, but it is not the controlling input here.
  phase.setParameter<descriptors::THETA>(
    c.getParameters().get<parameters::CONTACT_ANGLE_DEG>()*M_PI/T(180));
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
  const T rhoL = c.getParameters().get<parameters::RHO_LIQUID>();
  const T nuL = c.getParameters().get<parameters::NU_LIQUID>();
  const T rhoG = c.getParameters().get<parameters::GAS_DENSITY_KG_M3>();
  const T nuG = c.getParameters().get<parameters::GAS_NU_M2_S>();
  const T tauG = nuG/nuL*(tauL-T(.5))+T(.5);
  const T width = c.getParameters().get<parameters::INTERFACE_WIDTH>();
  const T liquidLength = c.getParameters().get<parameters::INITIAL_LIQUID_LENGTH_M>();
  const auto extent = c.getParameters().get<parameters::DOMAIN_EXTENT>();
  const T dx = c.getParameters().get<parameters::PHYS_DELTA_X>();
  auto all = geometry.getMaterialIndicator({0,1,2,3,4,5});
  auto wall = geometry.getMaterialIndicator({2,5});
  auto fluid = geometry.getMaterialIndicator({1,3,4});

  const bool wettingDroplet = c.getParameters().get<parameters::WETTING_DROPLET>() > T(.5);
  const T channelBottom = (extent[1]-c.getParameters().get<parameters::STRAIGHT_CHANNEL_WIDTH_M>())/T(2);
  InitialLiquidBand liquidBand(liquidLength,width*dx/T(2));
  // The contact-angle component must relax from a target-independent initial
  // shape.  Centre the circular droplet on the lower wall, i.e. an initial
  // 90-degree geometric cap, for every requested wall angle.  This avoids
  // turning the component test into a target-angle preservation check.
  const T dropletRadius = c.getParameters().get<parameters::DROPLET_RADIUS_M>();
  InitialLiquidDroplet liquidDroplet(extent[0]/T(2),channelBottom,
    dropletRadius,width*dx/T(2));
  AnalyticalF2D<T,T>& phi0 = wettingDroplet
    ? static_cast<AnalyticalF2D<T,T>&>(liquidDroplet)
    : static_cast<AnalyticalF2D<T,T>&>(liquidBand);
  AnalyticalConst2D<T,T> rhoGas(rhoG/rhoL);
  AnalyticalConst2D<T,T> rhoLiquid(T(1));
  AnalyticalIdentity2D<T,T> rho0(rhoGas+(rhoLiquid-rhoGas)*phi0);
  AnalyticalConst2D<T,T> tauGas(tauG);
  AnalyticalConst2D<T,T> tauLiquid(tauL);
  AnalyticalIdentity2D<T,T> tau0(tauGas+(tauLiquid-tauGas)*phi0);
  AnalyticalConst2D<T,T> zeroScalar(T{});
  AnalyticalConst2D<T,T> zeroVelocity(T{},T{});
  AnalyticalConst2D<T,T> one(T(1));
  AnalyticalConst2D<T,T> contactAngle(c.getParameters().get<parameters::CONTACT_ANGLE_DEG>()*M_PI/T(180));

  fields::set<SCALAR>(ns,all,one);
  fields::set<RHO>(ns,all,rho0);
  fields::set<TAU_EFF>(ns,all,tau0);
  fields::set<EXTERNAL_FORCE>(ns,all,zeroVelocity);
  fields::set<FORCE>(ns,all,zeroVelocity);
  fields::set<OLD_PHIU>(phase,all,zeroVelocity);
  fields::set<BOUNDARY>(phase,wall,2);
  fields::set<BOUNDARY>(phase,fluid,1);
  fields::set<THETA>(phase,wall,contactAngle);
  momenta::setOrderParameter(phase,all,phi0);
  momenta::setVelocity(phase,all,zeroVelocity);
  phase.iniEquilibrium(all,phi0,zeroVelocity);
  momenta::setIncompressiblePressure(ns,all,zeroScalar);
  momenta::setVelocity(ns,all,zeroVelocity);
  ns.iniEquilibrium(all,zeroScalar,zeroVelocity);
  phase.executePostProcessors(stage::PreCoupling());
  if (c.getParameters().get<parameters::OPEN_BOUNDARY>() > T(.5)) {
    phase.executePostProcessors(stage::InitOutlet());
  }
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
  T sumPhiX{};
  T rightHalfPhi{};
  T maxSpeed{};
  T sumUx{};
  T maxAbsUy{};
  T minPhi{std::numeric_limits<T>::max()};
  T maxPhi{-std::numeric_limits<T>::max()};
  std::size_t cells{};
  std::size_t rightHalfCells{};
  std::size_t nonFiniteCells{};
  T meanPressureLattice{};
  T minPressureLattice{std::numeric_limits<T>::max()};
  T maxPressureLattice{-std::numeric_limits<T>::max()};
  T liquidPressureLattice{};
  T gasPressureLattice{};
  std::size_t liquidPressureCells{};
  std::size_t gasPressureCells{};
  T liquidOutwardVolumeStep{};
  T maxLiquidFrontCell{-std::numeric_limits<T>::infinity()};
  T downstreamPhi{};
};

Snapshot snapshot(MinimalCase& c)
{
  Snapshot result;
  const T dx = c.getParameters().get<parameters::PHYS_DELTA_X>();
  auto& nsBlock = c.getLattice(NavierStokes{}).getBlock(0);
  auto& phaseBlock = c.getLattice(Component1{}).getBlock(0);
  auto& geometry = c.getGeometry().getBlockGeometry(0);
  const int split = geometry.getNx()/2;
  const T initialLiquidLength = c.getParameters().get<parameters::INITIAL_LIQUID_LENGTH_M>();
  nsBlock.forCoreSpatialLocations([&](LatticeR<2> r) {
    const int material = geometry.getMaterial(r);
    if (material != 1 && material != 3 && material != 4) return;
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
    result.sumPhiX += phi*T(r[0]+T(.5));
    if (phi >= T(.5)) {
      result.maxLiquidFrontCell = std::max(result.maxLiquidFrontCell,T(r[0])+T(.5));
    }
    if ((T(r[0])+T(.5))*dx >= initialLiquidLength) {
      result.downstreamPhi += phi;
    }
    result.minPhi = std::min(result.minPhi,phi);
    result.maxPhi = std::max(result.maxPhi,phi);
    result.maxSpeed = std::max(result.maxSpeed,util::norm<2>(u));
    result.sumUx += u[0];
    result.maxAbsUy = std::max(result.maxAbsUy,std::abs(u[1]));
    const T pressure = ns.computeRho();
    result.meanPressureLattice += pressure;
    result.minPressureLattice = std::min(result.minPressureLattice,pressure);
    result.maxPressureLattice = std::max(result.maxPressureLattice,pressure);
    if (phi >= T(.95)) {
      result.liquidPressureLattice += pressure;
      ++result.liquidPressureCells;
    } else if (phi <= T(.05)) {
      result.gasPressureLattice += pressure;
      ++result.gasPressureCells;
    }
    if (material == 3 || material == 4) {
      const T outwardVelocity = material == 3 ? -u[0] : u[0];
      result.liquidOutwardVolumeStep += phi*outwardVelocity*dx*dx
        *c.getParameters().get<parameters::PHYSICAL_GROOVE_DEPTH_M>();
    }
    if (r[0] >= split) {
      result.rightHalfPhi += phi;
      ++result.rightHalfCells;
    }
    ++result.cells;
  });
  return result;
}

T measureContactAngleThroughLiquid(MinimalCase& c)
{
  if (c.getParameters().get<parameters::WETTING_DROPLET>() < T(.5)) {
    return std::numeric_limits<T>::quiet_NaN();
  }
  auto& phase = c.getLattice(Component1{}).getBlock(0);
  auto& geometry = c.getGeometry().getBlockGeometry(0);
  const int nx = geometry.getNx();
  const int ny = geometry.getNy();
  int firstFluidY = -1;
  for (int y=0; y<ny && firstFluidY < 0; ++y) {
    for (int x=0; x<nx; ++x) {
      if (geometry.getMaterial({x,y}) == 1) {
        firstFluidY = y;
        break;
      }
    }
  }
  if (firstFluidY < 0 || firstFluidY+2 >= ny) return std::numeric_limits<T>::quiet_NaN();
  const int yContact = firstFluidY+1;
  const auto phiAt = [&](int x, int y) { return phase.get({x,y}).computeRho(); };
  int left = -1;
  int right = -1;
  for (int x=1; x<nx; ++x) {
    if (geometry.getMaterial({x-1,yContact}) != 1 || geometry.getMaterial({x,yContact}) != 1) continue;
    const T a = phiAt(x-1,yContact);
    const T b = phiAt(x,yContact);
    if ((a-T(.5))*(b-T(.5)) <= T()) {
      if (left < 0) left = x;
      right = x;
    }
  }
  const int xCentre = nx/2;
  int top = -1;
  for (int y=yContact+1; y<ny; ++y) {
    if (geometry.getMaterial({xCentre,y-1}) != 1 || geometry.getMaterial({xCentre,y}) != 1) continue;
    const T a = phiAt(xCentre,y-1);
    const T b = phiAt(xCentre,y);
    if ((a-T(.5))*(b-T(.5)) <= T()) {
      top = y;
    }
  }
  if (left < 0 || right <= left || top < 0) return std::numeric_limits<T>::quiet_NaN();
  const auto interpolate = [&](int x0, int y0, int x1, int y1) {
    const T a = phiAt(x0,y0);
    const T b = phiAt(x1,y1);
    const T f = (T(.5)-a)/(b-a);
    return Vector<T,2>{T(x0)+f*T(x1-x0),T(y0)+f*T(y1-y0)};
  };
  const auto pLeft = interpolate(left-1,yContact,left,yContact);
  const auto pRight = interpolate(right-1,yContact,right,yContact);
  const auto pTop = interpolate(xCentre,top-1,xCentre,top);
  const T xc = (pLeft[0]+pRight[0])/T(2);
  const T denominator = T(2)*(pLeft[1]-pTop[1]);
  if (std::abs(denominator) < T(1e-12)) return std::numeric_limits<T>::quiet_NaN();
  const T yc = ((pLeft[0]-xc)*(pLeft[0]-xc)+pLeft[1]*pLeft[1]-pTop[1]*pTop[1])/denominator;
  const T radius = std::hypot(pTop[0]-xc,pTop[1]-yc);
  const T wallY = T(firstFluidY)-T(.5);
  if (!std::isfinite(radius) || radius <= T()) return std::numeric_limits<T>::quiet_NaN();
  const T cosine = std::clamp((wallY-yc)/radius,T(-1),T(1));
  return std::acos(cosine)*T(180)/M_PI;
}

void setDriveForce(MinimalCase& c, int step)
{
  const T ramp = smoothstep(T(step)/c.getParameters().get<parameters::DRIVE_RAMP_STEPS>());
  if (c.getParameters().get<parameters::OPEN_BOUNDARY>() > T(.5)) {
    auto& ns = c.getLattice(NavierStokes{});
    // momenta::setIncompressiblePressure accepts physical pressure and applies
    // the UnitConverter once internally.  Passing a pre-converted lattice
    // value would incorrectly divide by the pressure factor a second time.
    const T physicalPressure = c.getParameters().get<parameters::PRESSURE_DRIVE_PA>()*ramp;
    AnalyticalConst2D<T,T> inletPressure(physicalPressure);
    momenta::setIncompressiblePressure(ns,c.getGeometry().getMaterialIndicator(3),inletPressure);
    return;
  }
  AnalyticalConst2D<T,T> force(c.getParameters().get<parameters::DRIVE_ACCELERATION_LATTICE>()*ramp,T{});
  auto& ns = c.getLattice(NavierStokes{});
  fields::set<EXTERNAL_FORCE>(ns,c.getGeometry().getMaterialIndicator(1),force);
}

void appendMetrics(MinimalCase& c, int step, const Snapshot& s, T liquidBalanceResidual,
                   T integratedOutwardLiquidVolume)
{
  if (!singleton::mpi().isMainProcessor()) return;
  const auto& converter = c.getLattice(NavierStokes{}).getUnitConverter();
  const T dx = c.getParameters().get<parameters::PHYS_DELTA_X>();
  const auto path = c.getParameters().get<parameters::OUTPUT_DIR>()+"/metrics.csv";
  const bool fresh = !std::filesystem::exists(path);
  std::ofstream stream(path,std::ios::app);
  if (fresh) stream << "step,time_s,drive_acceleration_lattice,filling_fraction,liquid_centroid_x_m,liquid_0p5_front_x_m,post_initial_front_liquid_cell_equivalents,right_half_phi,mean_lattice_u_x,max_abs_lattice_u_y,max_lattice_u,max_mach,mean_pressure_gauge_pa,pressure_min_gauge_pa,pressure_max_gauge_pa,instant_outward_liquid_volume_m3,integrated_outward_liquid_volume_m3,inventory_plus_boundary_flux_residual\n";
  const T meanPhi = s.cells ? s.sumPhi/T(s.cells) : T();
  const T liquidCentroid = s.sumPhi > T() ? s.sumPhiX/s.sumPhi*dx : T();
  const T rightPhi = s.rightHalfCells ? s.rightHalfPhi/T(s.rightHalfCells) : T();
  const T liquidFront = std::isfinite(s.maxLiquidFrontCell) ? s.maxLiquidFrontCell*dx : T();
  const T acceleration = c.getParameters().get<parameters::OPEN_BOUNDARY>() > T(.5) ? T()
    : c.getParameters().get<parameters::DRIVE_ACCELERATION_LATTICE>()
      *smoothstep(T(step)/c.getParameters().get<parameters::DRIVE_RAMP_STEPS>());
  const T pressureFactor = converter.getConversionFactorPressure();
  const T meanPressure = s.cells ? s.meanPressureLattice/T(s.cells)*pressureFactor : T();
  stream << std::setprecision(17) << step << ',' << converter.getPhysTime(step) << ',' << acceleration << ','
         << meanPhi << ',' << liquidCentroid << ',' << liquidFront << ',' << s.downstreamPhi << ',' << rightPhi << ',' << s.sumUx/T(s.cells) << ',' << s.maxAbsUy << ',' << s.maxSpeed << ',' << s.maxSpeed*std::sqrt(T(3)) << ','
         << meanPressure << ',' << s.minPressureLattice*pressureFactor << ',' << s.maxPressureLattice*pressureFactor << ','
         << s.liquidOutwardVolumeStep << ',' << integratedOutwardLiquidVolume << ',' << liquidBalanceResidual << '\n';
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
                  T liquidBalanceResidual, T integratedOutwardLiquidVolume,
                  T measuredContactAngleDeg, bool pass, int completedSteps,
                  bool stoppedAfterResolvedIntrusion)
{
  if (!singleton::mpi().isMainProcessor()) return;
  const auto& converter = c.getLattice(NavierStokes{}).getUnitConverter();
  const int requestedSteps = c.getParameters().get<parameters::MAX_STEPS>();
  const T dx = c.getParameters().get<parameters::PHYS_DELTA_X>();
  const T initialRight = initial.rightHalfPhi/T(initial.rightHalfCells);
  const T finalRight = final.rightHalfPhi/T(final.rightHalfCells);
  const T initialFilling = initial.sumPhi/T(initial.cells);
  const T finalFilling = final.sumPhi/T(final.cells);
  const T initialCentroid = initial.sumPhiX/initial.sumPhi*dx;
  const T finalCentroid = final.sumPhiX/final.sumPhi*dx;
  const T centroidProgressCells = final.sumPhiX/final.sumPhi-initial.sumPhiX/initial.sumPhi;
  const T initialLiquidFront = initial.maxLiquidFrontCell*dx;
  const T finalLiquidFront = final.maxLiquidFrontCell*dx;
  const T resolvedFrontProgressCells = final.maxLiquidFrontCell-initial.maxLiquidFrontCell;
  const T resolvedUptakeCells = final.downstreamPhi-initial.downstreamPhi;
  const T resolvedUptakeVolume = resolvedUptakeCells*dx*dx
    *c.getParameters().get<parameters::PHYSICAL_GROOVE_DEPTH_M>();
  const T resolvedFrontThreshold = c.getParameters().get<parameters::RESOLVED_FRONT_PROGRESS_CELLS>();
  const T resolvedUptakeThreshold = c.getParameters().get<parameters::RESOLVED_UPTAKE_CELL_EQUIVALENTS>();
  const bool resolvedFront = std::isfinite(resolvedFrontProgressCells)
    && resolvedFrontProgressCells >= resolvedFrontThreshold;
  const bool resolvedUptake = std::isfinite(resolvedUptakeCells)
    && resolvedUptakeCells >= resolvedUptakeThreshold;
  const bool intrusionObservable = resolvedFront && resolvedUptake;
  const T liquidMeanPressure = final.liquidPressureCells
    ? final.liquidPressureLattice/T(final.liquidPressureCells)*converter.getConversionFactorPressure() : T();
  const T gasMeanPressure = final.gasPressureCells
    ? final.gasPressureLattice/T(final.gasPressureCells)*converter.getConversionFactorPressure() : T();
  const bool wettingMode = c.getParameters().get<parameters::WETTING_DROPLET>() > T(.5);
  const bool targetIs60 = std::abs(c.getParameters().get<parameters::CONTACT_ANGLE_DEG>()-T(60)) < T(1e-12);
  const char* status = wettingMode
    ? (targetIs60 ? (pass ? "CONTACT_ANGLE_60_PASS" : "CONTACT_ANGLE_60_HOLD")
                  : (pass ? "WETTING_COMPONENT_PASS" : "WETTING_COMPONENT_HOLD"))
    : (pass ? "EC1XT240_REDUCED_RUNTIME_PASS" : "EC1XT240_REDUCED_RUNTIME_HOLD");
  std::ofstream stream(c.getParameters().get<parameters::OUTPUT_DIR>()+"/summary.json");
  stream << std::setprecision(17)
    << "{\n"
    << "  \"case_id\": \"" << c.getParameters().get<parameters::CASE_LABEL>() << "\",\n"
    << "  \"status\": \"" << status << "\",\n"
    << "  \"claim\": \"reduced 2-D OAS wetting/intrusion model driven by an OF350 EC1XT240 zone-mean pressure scale surrogate; source-backed forcing magnitude only, not a claimed lateral pressure drop across the OAS crop; not full 3-D or perfectGas reproduction\",\n"
    << "  \"geometry_source\": \"" << c.getParameters().get<parameters::GEOMETRY_SOURCE>() << "\",\n"
    << "  \"mask_file\": \"" << std::filesystem::path(c.getParameters().get<parameters::MASK_INPUT>()).filename().string() << "\",\n"
    << "  \"planview_dx_m\": " << dx << ",\n"
    << "  \"geometry_depth_m\": " << c.getParameters().get<parameters::PHYSICAL_GROOVE_DEPTH_M>() << ",\n"
    << "  \"phase_model\": \"OpenLB ConservativePhaseField plus Liang coupling and PhaseFieldCurvedWall wetting\",\n"
    << "  \"surface_tension_N_m\": " << c.getParameters().get<parameters::SURFACE_TENSION_N_M>() << ",\n"
    << "  \"contact_angle_deg_through_liquid\": " << c.getParameters().get<parameters::CONTACT_ANGLE_DEG>() << ",\n"
    << "  \"measured_contact_angle_deg_through_liquid\": ";
  if (std::isfinite(measuredContactAngleDeg)) {
    stream << measuredContactAngleDeg;
  } else {
    stream << "null";
  }
  stream << ",\n"
    << "  \"gas_approximation\": \"REDUCED_VENTED_GAS: incompressible reduced-density phase; not perfectGas\",\n"
    << "  \"driving\": \"" << (c.getParameters().get<parameters::OPEN_BOUNDARY>() > T(.5)
      ? "OF350_ZONE_MEAN_PRESSURE_SCALE_SURROGATE through pressure-open inlet/outlet"
      : "zero-drive closed component test") << "\",\n"
    << "  \"pressure_drive_pa\": " << c.getParameters().get<parameters::PRESSURE_DRIVE_PA>() << ",\n"
    << "  \"steps\": " << completedSteps << ",\n"
    << "  \"requested_max_steps\": " << requestedSteps << ",\n"
    << "  \"pressure_ramp_steps\": " << c.getParameters().get<parameters::DRIVE_RAMP_STEPS>() << ",\n"
    << "  \"hold_steps_completed\": " << std::max(0,completedSteps-static_cast<int>(c.getParameters().get<parameters::DRIVE_RAMP_STEPS>())) << ",\n"
    << "  \"stopped_after_resolved_intrusion\": " << (stoppedAfterResolvedIntrusion ? "true" : "false") << ",\n"
    << "  \"physical_time_s\": " << converter.getPhysTime(completedSteps) << ",\n"
    << "  \"phase_range\": [" << final.minPhi << ", " << final.maxPhi << "],\n"
    << "  \"max_lattice_speed\": " << final.maxSpeed << ",\n"
    << "  \"mean_lattice_u_x\": " << final.sumUx/T(final.cells) << ",\n"
    << "  \"max_abs_lattice_u_y\": " << final.maxAbsUy << ",\n"
    << "  \"max_mach\": " << final.maxSpeed*std::sqrt(T(3)) << ",\n"
    << "  \"initial_right_half_liquid_fraction\": " << initialRight << ",\n"
    << "  \"final_right_half_liquid_fraction\": " << finalRight << ",\n"
    << "  \"right_half_liquid_fraction_change\": " << finalRight-initialRight << ",\n"
    << "  \"initial_filling_fraction\": " << initialFilling << ",\n"
    << "  \"filling_fraction\": " << finalFilling << ",\n"
    << "  \"filling_fraction_change\": " << finalFilling-initialFilling << ",\n"
    << "  \"initial_liquid_centroid_x_m\": " << initialCentroid << ",\n"
    << "  \"front_metric_liquid_centroid_x_m\": " << finalCentroid << ",\n"
    << "  \"front_metric_change_m\": " << finalCentroid-initialCentroid << ",\n"
    << "  \"front_progress_cells\": " << centroidProgressCells << ",\n"
    << "  \"liquid_centroid_progress_cells\": " << centroidProgressCells << ",\n"
    << "  \"initial_liquid_0p5_front_x_m\": " << initialLiquidFront << ",\n"
    << "  \"liquid_0p5_front_x_m\": " << finalLiquidFront << ",\n"
    << "  \"resolved_front_progress_cells\": " << resolvedFrontProgressCells << ",\n"
    << "  \"initial_post_initial_front_liquid_cell_equivalents\": " << initial.downstreamPhi << ",\n"
    << "  \"post_initial_front_liquid_cell_equivalents\": " << final.downstreamPhi << ",\n"
    << "  \"resolved_uptake_cell_equivalents\": " << resolvedUptakeCells << ",\n"
    << "  \"resolved_uptake_volume_m3\": " << resolvedUptakeVolume << ",\n"
    << "  \"resolved_front_threshold_cells\": " << resolvedFrontThreshold << ",\n"
    << "  \"resolved_uptake_threshold_cell_equivalents\": " << resolvedUptakeThreshold << ",\n"
    << "  \"resolved_front\": " << (resolvedFront ? "true" : "false") << ",\n"
    << "  \"resolved_uptake\": " << (resolvedUptake ? "true" : "false") << ",\n"
    << "  \"intrusion_observable\": " << (intrusionObservable ? "true" : "false") << ",\n"
    << "  \"liquid_inventory_boundary_residual\": " << liquidBalanceResidual << ",\n"
    << "  \"integrated_outward_liquid_volume_m3\": " << integratedOutwardLiquidVolume << ",\n"
    << "  \"mean_pressure_pa\": " << final.meanPressureLattice/T(final.cells)*converter.getConversionFactorPressure() << ",\n"
    << "  \"pressure_range_pa\": [" << final.minPressureLattice*converter.getConversionFactorPressure() << ", " << final.maxPressureLattice*converter.getConversionFactorPressure() << "],\n"
    << "  \"bulk_liquid_mean_pressure_pa\": " << liquidMeanPressure << ",\n"
    << "  \"bulk_gas_mean_pressure_pa\": " << gasMeanPressure << ",\n"
    << "  \"bulk_liquid_minus_gas_pressure_pa\": " << liquidMeanPressure-gasMeanPressure << "\n"
    << "}\n";
}

bool simulate(MinimalCase& c)
{
  auto& ns = c.getLattice(NavierStokes{});
  auto& phase = c.getLattice(Component1{});
  const int steps = c.getParameters().get<parameters::MAX_STEPS>();
  const int metricInterval = c.getParameters().get<parameters::METRIC_INTERVAL>();
  const T dx = c.getParameters().get<parameters::PHYS_DELTA_X>();
  Snapshot initial = snapshot(c);
  bool stable = true;
  bool stoppedAfterResolvedIntrusion = false;
  int completedSteps = 0;
  T integratedOutwardLiquidVolume{};
  T previousOutwardLiquidVolumeStep = initial.liquidOutwardVolumeStep;

  writeVtk(c,0);
  appendMetrics(c,0,initial,T(),integratedOutwardLiquidVolume);
  for (int step=1; step<=steps; ++step) {
    completedSteps = step;
    setDriveForce(c,step);
    ns.collideAndStream();
    phase.collideAndStream();
    phase.getCommunicator(stage::PreCoupling()).communicate();
    phase.executePostProcessors(stage::PreCoupling());
    // The signed-distance iteration initializes PSI before time stepping.  Do
    // not repeat it as a periodic projection: it changes the order parameter
    // in an otherwise closed wetting test and would turn numerical
    // re-initialization drift into apparent mass loss.
    phase.getCommunicator(stage::PreCoupling()).communicate();
    c.getOperator("Liang").apply();
    if (c.getParameters().get<parameters::OPEN_BOUNDARY>() > T(.5)) {
      c.getOperator("InletVelocity").apply();
    }

    Snapshot current = snapshot(c);
    integratedOutwardLiquidVolume += T(.5)*(previousOutwardLiquidVolumeStep
      + current.liquidOutwardVolumeStep);
    previousOutwardLiquidVolumeStep = current.liquidOutwardVolumeStep;
    const T initialVolume = initial.sumPhi*dx*dx*c.getParameters().get<parameters::PHYSICAL_GROOVE_DEPTH_M>();
    const T currentVolume = current.sumPhi*dx*dx*c.getParameters().get<parameters::PHYSICAL_GROOVE_DEPTH_M>();
    const T residual = std::abs(currentVolume-initialVolume+integratedOutwardLiquidVolume)
      /std::max(T(1e-30),initialVolume);
    const bool bounded = current.minPhi >= T(-.05) && current.maxPhi <= T(1.05);
    const bool lowMach = current.maxSpeed*std::sqrt(T(3)) < T(.1);
    stable = current.nonFiniteCells == 0 && bounded && lowMach;
    const T resolvedFrontProgressCells = current.maxLiquidFrontCell-initial.maxLiquidFrontCell;
    const T resolvedUptakeCells = current.downstreamPhi-initial.downstreamPhi;
    const bool resolvedIntrusion = std::isfinite(resolvedFrontProgressCells)
      && resolvedFrontProgressCells >= c.getParameters().get<parameters::RESOLVED_FRONT_PROGRESS_CELLS>()
      && std::isfinite(resolvedUptakeCells)
      && resolvedUptakeCells >= c.getParameters().get<parameters::RESOLVED_UPTAKE_CELL_EQUIVALENTS>();
    const bool stopAfterResolvedIntrusion = stable
      && c.getParameters().get<parameters::STOP_ON_RESOLVED_INTRUSION>() > T(.5)
      && step >= static_cast<int>(c.getParameters().get<parameters::DRIVE_RAMP_STEPS>())
      && resolvedIntrusion;
    if (step % metricInterval == 0 || !stable || step == steps || stopAfterResolvedIntrusion) {
      appendMetrics(c,step,current,residual,integratedOutwardLiquidVolume);
      writeVtk(c,step);
    }
    if (!stable) {
      std::cerr << "MINIMAL_240_SMOKE_HOLD step=" << step << " phi=[" << current.minPhi << ','
                << current.maxPhi << "] max_Ma=" << current.maxSpeed*std::sqrt(T(3))
                << " non_finite=" << current.nonFiniteCells << '\n';
      break;
    }
    if (stopAfterResolvedIntrusion) {
      stoppedAfterResolvedIntrusion = true;
      break;
    }
  }

  Snapshot final = snapshot(c);
  const T initialVolume = initial.sumPhi*dx*dx*c.getParameters().get<parameters::PHYSICAL_GROOVE_DEPTH_M>();
  const T finalVolume = final.sumPhi*dx*dx*c.getParameters().get<parameters::PHYSICAL_GROOVE_DEPTH_M>();
  const T residual = std::abs(finalVolume-initialVolume+integratedOutwardLiquidVolume)
    /std::max(T(1e-30),initialVolume);
  const T initialRight = initial.rightHalfPhi/T(initial.rightHalfCells);
  const T finalRight = final.rightHalfPhi/T(final.rightHalfCells);
  const T centroidProgressCells = final.sumPhiX/final.sumPhi-initial.sumPhiX/initial.sumPhi;
  const T resolvedFrontProgressCells = final.maxLiquidFrontCell-initial.maxLiquidFrontCell;
  const T resolvedUptakeCells = final.downstreamPhi-initial.downstreamPhi;
  const T measuredContactAngleDeg = measureContactAngleThroughLiquid(c);
  const bool wettingMode = c.getParameters().get<parameters::WETTING_DROPLET>() > T(.5);
  const bool targetIs60 = std::abs(c.getParameters().get<parameters::CONTACT_ANGLE_DEG>()-T(60)) < T(1e-12);
  const bool contactPass = !wettingMode || (std::isfinite(measuredContactAngleDeg)
    && std::abs(measuredContactAngleDeg-c.getParameters().get<parameters::CONTACT_ANGLE_DEG>()) <= T(5));
  const T residualGate = wettingMode ? T(.005) : T(.01);
  const bool smokePass = stable && residual <= residualGate && contactPass;
  writeSummary(c,initial,final,residual,integratedOutwardLiquidVolume,measuredContactAngleDeg,
               smokePass,completedSteps,stoppedAfterResolvedIntrusion);
  std::cout << std::setprecision(17)
            << (wettingMode ? (targetIs60 ? (smokePass ? "CONTACT_ANGLE_60_PASS" : "CONTACT_ANGLE_60_HOLD")
                                           : (smokePass ? "WETTING_COMPONENT_PASS" : "WETTING_COMPONENT_HOLD"))
            : (smokePass ? "EC1XT240_REDUCED_RUNTIME_PASS" : "EC1XT240_REDUCED_RUNTIME_HOLD"))
            << " phi=[" << final.minPhi << ',' << final.maxPhi << ']'
            << " max_Ma=" << final.maxSpeed*std::sqrt(T(3))
            << " right_half_change=" << finalRight-initialRight
            << " centroid_progress_cells=" << centroidProgressCells
            << " resolved_front_progress_cells=" << resolvedFrontProgressCells
            << " resolved_uptake_cell_equivalents=" << resolvedUptakeCells
            << " inventory_residual=" << residual << '\n';
  return smokePass;
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
  params.set<parameters::PHYS_DELTA_X>(kDefaultDx);
  params.set<parameters::DOMAIN_EXTENT>({raster.nx*kDefaultDx,raster.ny*kDefaultDx});
  params.set<parameters::LATTICE_RELAXATION_TIME>(T(.8));
  params.set<parameters::INTERFACE_WIDTH>(T(5));
  params.set<parameters::PHASE_TAU>(T(.8));
  params.set<parameters::RHO_LIQUID>(kDefaultLiquidDensity);
  params.set<parameters::NU_LIQUID>(kDefaultLiquidNu);
  params.set<parameters::GAS_DENSITY_KG_M3>(T(151));
  params.set<parameters::GAS_NU_M2_S>(T(2)*kDefaultLiquidNu);
  params.set<parameters::DRIVE_ACCELERATION_LATTICE>(T(1e-6));
  params.set<parameters::DRIVE_RAMP_STEPS>(T(1000));
  params.set<parameters::INITIAL_LIQUID_LENGTH_M>(T(.45e-6));
  params.set<parameters::PHYSICAL_GROOVE_DEPTH_M>(T(100e-6));
  params.set<parameters::OPEN_BOUNDARY>(T());
  params.set<parameters::SURFACE_TENSION_N_M>(T());
  params.set<parameters::CONTACT_ANGLE_DEG>(T(90));
  params.set<parameters::PRESSURE_DRIVE_PA>(T());
  params.set<parameters::CASE_LABEL>("minimal_ec1xt240_oas_phasefield");
  params.set<parameters::GEOMETRY_SOURCE>("inputs/layouts/SIM-EC1XT240.OAS");
  params.set<parameters::STRAIGHT_CHANNEL>(T());
  params.set<parameters::STRAIGHT_CHANNEL_WIDTH_M>(T(120e-9));
  params.set<parameters::WETTING_DROPLET>(T());
  params.set<parameters::DROPLET_RADIUS_M>(T(200e-9));
  params.set<parameters::RESOLVED_FRONT_PROGRESS_CELLS>(T(1));
  params.set<parameters::RESOLVED_UPTAKE_CELL_EQUIVALENTS>(T(1));
  params.set<parameters::STOP_ON_RESOLVED_INTRUSION>(T());
  params.set<parameters::MAX_STEPS>(5000);
  params.set<parameters::METRIC_INTERVAL>(100);
  params.set<parameters::VTK_INTERVAL>(1000);
  params.fromCLI(argc,argv);
  // The PGM is sampled on the active physical lattice spacing.  The raster
  // dimensions therefore define the plan-view physical extent after CLI
  // overrides are parsed; an arbitrary extent cannot silently distort OAS.
  const T dx = params.get<parameters::PHYS_DELTA_X>();
  params.set<parameters::DOMAIN_EXTENT>({raster.nx*dx,raster.ny*dx});

  Mesh mesh = createMesh(params);
  MinimalCase c(params,mesh);
  prepareGeometry(c);
  prepareLattices(c);
  initializeFields(c);
  return simulate(c) ? EXIT_SUCCESS : EXIT_FAILURE;
}
