// Minimal XY1A aligned-anisotropic periodic transport component.
// Uses the same force route validated by XY0: D3Q19<FORCE>,
// ForcedBGKdynamics, and fields::set<FORCE>.
#include <olb.h>

#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>

using namespace olb;
using namespace olb::descriptors;
using T = double;
using DESCRIPTOR = D3Q19<FORCE>;
using BulkDynamics = ForcedBGKdynamics<T,DESCRIPTOR>;

struct Sample {
  Vector<T,3> sumU{0.,0.,0.};
  T meanSpeed{};
  T meanRho{};
  int fluidCells{};
  int solidCells{};
};

// Frozen XY convention: J=(1/V_REV) integral_fluid u dV.  Each fluid lattice
// node contributes u*dx^3; solids contribute zero.
static Sample measureFlux(SuperLattice<T,DESCRIPTOR>& lattice,
                          SuperGeometry<T,3>& geometry,
                          const UnitConverter<T,DESCRIPTOR>& converter)
{
  lattice.setProcessingContext(ProcessingContext::Evaluation);
  Sample r;
  const auto& load = lattice.getLoadBalancer();
  for (int iC=0; iC<load.size(); ++iC) {
    auto& block = lattice.getBlock(iC);
    block.forCoreSpatialLocations([&](LatticeR<3> loc) {
      const int material = geometry.getBlockGeometry(iC).getMaterial(loc[0],loc[1],loc[2]);
      if (material == 1) {
        T rho{}, u[3]{};
        block.get(loc).computeRhoU(rho,u);
        T speed2{};
        for (int i=0; i<3; ++i) {
          const T ui = converter.getPhysVelocity(u[i]);
          r.sumU[i] += ui;
          speed2 += ui*ui;
        }
        r.meanSpeed += std::sqrt(speed2);
        r.meanRho += rho;
        ++r.fluidCells;
      } else {
        ++r.solidCells;
      }
    });
  }
  r.meanSpeed /= T(r.fluidCells);
  r.meanRho /= T(r.fluidCells);
  return r;
}

int main(int argc, char* argv[])
{
  if (argc != 6) {
    std::cerr << "usage: xy1aAlignedSmoke base_gap_cells x|y G_Pa_per_m steps summary.json\\n";
    return 2;
  }
  initialize(&argc,&argv);
  const int nBase = std::stoi(argv[1]);
  const std::string direction = argv[2];
  const T gradient = std::stod(argv[3]);
  const int steps = std::stoi(argv[4]);
  const std::string summaryPath = argv[5];
  if ((nBase != 8 && nBase != 16 && nBase != 24 && nBase != 32) || (direction != "x" && direction != "y") || gradient <= 0 || steps < 1000) return 2;

  // NUMERICAL_COMPONENT_GEOMETRY.  A 4-um base gap spans the full periodic
  // cell.  The 8x4x8-um x-periodic, downward-opening recess adds a
  // low-resistance x corridor while leaving a transverse constriction.
  const T baseGap = 4.e-6, recessDepth = 8.e-6;
  const T dx = baseGap/T(nBase);
  const T lengthX = 8.e-6, lengthY = 8.e-6, fluidHeight = baseGap + recessDepth;
  const T recessX = 8.e-6, recessY = 4.e-6;
  const int nx = 2*nBase, ny = 2*nBase, nzFluid = 3*nBase;
  const T rhoPhys = 1510., mu = 1.e-3, nu = mu/rhoPhys, tau = .8, charU = 3.e-4;
  UnitConverterFromResolutionAndRelaxationTime<T,DESCRIPTOR> converter(
    nBase,tau,baseGap,charU,nu,rhoPhys);
  IndicatorCuboid3D<T> domain(Vector<T,3>{lengthX,lengthY,fluidHeight+dx},Vector<T,3>{0.,0.,0.});
  CuboidDecomposition3D<T> decomposition(domain,converter.getPhysDeltaX(),singleton::mpi().getSize());
  decomposition.setPeriodicity({true,true,false});
  HeuristicLoadBalancer<T> load(decomposition);
  SuperGeometry<T,3> geometry(decomposition,load,1);
  geometry.rename(0,2);
  geometry.rename(2,1,{0,0,1});
  IndicatorCuboid3D<T> upperMold(Vector<T,3>{lengthX,lengthY,recessDepth},Vector<T,3>{0.,0.,baseGap});
  geometry.rename(1,2,upperMold);
  IndicatorCuboid3D<T> recess(Vector<T,3>{recessX,recessY,recessDepth},Vector<T,3>{0.,2.e-6,baseGap});
  geometry.rename(2,1,recess);
  geometry.clean(); geometry.innerClean(); geometry.checkForErrors();

  SuperLattice<T,DESCRIPTOR> lattice(converter,geometry);
  dynamics::set<BulkDynamics>(lattice,geometry.getMaterialIndicator(1));
  boundary::set<boundary::BounceBack>(lattice,geometry,2);
  lattice.setParameter<OMEGA>(converter.getLatticeRelaxationFrequency());
  AnalyticalConst3D<T,T> rho0(1.), u0(0.,0.,0.);
  lattice.iniEquilibrium(geometry,1,rho0,u0);
  const T forceLat=(gradient/rhoPhys)*converter.getConversionFactorMass()/converter.getConversionFactorForce();
  const Vector<T,3> force = direction == "x" ? Vector<T,3>{forceLat,0.,0.} : Vector<T,3>{0.,forceLat,0.};
  fields::set<FORCE>(lattice,geometry.getMaterialIndicator(1),force);
  lattice.initialize();

  const Sample initial=measureFlux(lattice,geometry,converter);
  T previous=0., steady=std::numeric_limits<T>::infinity();
  int stepsToSteady=0, completedSteps=0;
  for (int iT=1; iT<=steps; ++iT) {
    lattice.collideAndStream();
    if (iT%1000==0 || iT==steps) {
      const Sample now=measureFlux(lattice,geometry,converter);
      const T magnitude=std::sqrt(now.sumU[0]*now.sumU[0]+now.sumU[1]*now.sumU[1]+now.sumU[2]*now.sumU[2]);
      steady=std::abs(magnitude-previous)/std::max(magnitude,T(1e-30));
      previous=magnitude;
      if (iT >= 2000 && steady <= 1.e-6) {
        stepsToSteady=iT;
        completedSteps=iT;
        break;
      }
    }
    completedSteps=iT;
  }
  const Sample final=measureFlux(lattice,geometry,converter);
  const T revVolume=lengthX*lengthY*fluidHeight;
  Vector<T,3> J{final.sumU[0]*dx*dx*dx/revVolume,final.sumU[1]*dx*dx*dx/revVolume,final.sumU[2]*dx*dx*dx/revVolume};
  const T maxMach=lattice.getStatistics().getMaxU()*std::sqrt(3.);
  const T re=rhoPhys*final.meanSpeed*baseGap/mu;
  const T massDrift=(final.meanRho-initial.meanRho)/initial.meanRho;
  const T fluidFraction=T(final.fluidCells)/T(final.fluidCells+final.solidCells);

  std::ofstream out(summaryPath);
  out << std::setprecision(17) << "{\n"
      << "  \"component\": \"XY1A_ALIGNED_ANISOTROPIC_PERIODIC_COMPONENT\",\n"
      << "  \"direction\": \"" << direction << "\",\n"
      << "  \"body_force_equivalent_pressure_gradient_pa_per_m\": " << gradient << ",\n"
      << "  \"steps\": " << completedSteps << ",\n"
      << "  \"steps_to_steady\": " << (stepsToSteady ? std::to_string(stepsToSteady) : "null") << ",\n"
      << "  \"reached_steady_state\": " << (stepsToSteady ? "true" : "false") << ",\n"
      << "  \"dx_m\": " << dx << ",\n"
      << "  \"nx\": " << nx << ", \"ny\": " << ny << ", \"nz_fluid\": " << nzFluid << ",\n"
      << "  \"base_gap_m\": " << baseGap << ", \"base_gap_cells\": " << nBase << ",\n"
      << "  \"recess_dimensions_m\": [" << recessX << ", " << recessY << ", " << recessDepth << "],\n"
      << "  \"rev_dimensions_m\": [" << lengthX << ", " << lengthY << ", " << fluidHeight << "],\n"
      << "  \"fluid_cells\": " << final.fluidCells << ", \"solid_cells\": " << final.solidCells << ",\n"
      << "  \"fluid_volume_fraction\": " << fluidFraction << ",\n"
      << "  \"minimum_throat_cells\": " << nBase << ",\n"
      << "  \"periodic_x_y_continuity\": true, \"connected_by_full_base_gap\": true, \"upper_recess_opens_downward\": true,\n"
      << "  \"J_m_per_s\": [" << J[0] << ", " << J[1] << ", " << J[2] << "],\n"
      << "  \"mean_speed_m_per_s\": " << final.meanSpeed << ",\n"
      << "  \"re\": " << re << ", \"max_lattice_mach\": " << maxMach << ",\n"
      << "  \"mass_drift_fraction\": " << massDrift << ",\n"
      << "  \"steady_relative_change_over_1000_steps\": " << steady << "\n}\n";
  std::cout << "XY1A_COMPLETE direction=" << direction << " J=" << J << "\n";
}
