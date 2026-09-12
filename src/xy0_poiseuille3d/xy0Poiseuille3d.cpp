// Fixed-geometry, force-driven 3-D slit benchmark for XY0.
// The forcing API is copied from OpenLB 1.9 examples/laminar/poiseuille3d:
// ForcedBGKdynamics plus fields::set<descriptors::FORCE>.
#include <olb.h>

#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <string>
#include <vector>

using namespace olb;
using namespace olb::descriptors;
using T = double;
using DESCRIPTOR = D3Q19<FORCE>;
using BulkDynamics = ForcedBGKdynamics<T,DESCRIPTOR>;

struct Sample {
  T meanU{};
  T maxU{};
  T meanRho{};
  std::map<int,std::pair<T,int>> byZ;
};

static Sample sample(SuperLattice<T,DESCRIPTOR>& lattice,
                     SuperGeometry<T,3>& geometry,
                     const UnitConverter<T,DESCRIPTOR>& converter,
                     T dx)
{
  lattice.setProcessingContext(ProcessingContext::Evaluation);
  Sample result;
  T sumU{};
  int count{};
  const auto& load = lattice.getLoadBalancer();
  for (int iC=0; iC<load.size(); ++iC) {
    auto& block = lattice.getBlock(iC);
    block.forCoreSpatialLocations([&](LatticeR<3> loc) {
      if (geometry.getBlockGeometry(iC).getMaterial(loc[0],loc[1],loc[2]) != 1) return;
      T rho{};
      T u[3]{};
      block.get(loc).computeRhoU(rho,u);
      const T ux = converter.getPhysVelocity(u[0]);
      const auto phys = lattice.getCuboidDecomposition().getPhysR(loc.withPrefix(load.glob(iC)));
      const int row = int(std::llround((phys[2]-dx)/dx));
      result.byZ[row].first += ux;
      result.byZ[row].second += 1;
      sumU += ux;
      result.maxU = std::max(result.maxU,std::abs(ux));
      result.meanRho += rho;
      ++count;
    });
  }
  result.meanU = sumU/T(count);
  result.meanRho /= T(count);
  return result;
}

int main(int argc, char* argv[])
{
  if (argc != 12) {
    std::cerr << "usage: xy0Poiseuille3d N_H G_Pa_per_m steps H_m rho mu charU tau y_cells summary.json profile.csv\n";
    return 2;
  }
  initialize(&argc,&argv);
  const int nH = std::stoi(argv[1]);
  const T gradient = std::stod(argv[2]);
  const int steps = std::stoi(argv[3]);
  const T hydroH = std::stod(argv[4]);
  const T rhoPhys = std::stod(argv[5]);
  const T mu = std::stod(argv[6]);
  const T charU = std::stod(argv[7]);
  const T tau = std::stod(argv[8]);
  const int yCells = std::stoi(argv[9]);
  const std::string summaryPath = argv[10];
  const std::string profilePath = argv[11];
  if (nH < 8 || gradient <= 0 || steps < 1 || hydroH <= 0 || rhoPhys <= 0 || mu <= 0 || charU <= 0 || tau <= .5 || yCells < 2) {
    std::cerr << "invalid XY0 input\n";
    return 2;
  }

  // Half-way bounce-back places the hydrodynamic walls dx/2 inside the two
  // material-2 planes.  nH is therefore the exact hydro-gap resolution.
  const T dx = hydroH/T(nH);
  const T domainH = hydroH + dx;
  const T length = 2.*hydroH;
  const T width = T(yCells)*dx;
  const T nu = mu/rhoPhys;
  UnitConverterFromResolutionAndRelaxationTime<T,DESCRIPTOR> converter(
    nH, tau, hydroH, charU, nu, rhoPhys);

  IndicatorCuboid3D<T> domain(Vector<T,3>{length,width,domainH}, Vector<T,3>{0.,0.,0.});
  CuboidDecomposition3D<T> decomposition(domain, converter.getPhysDeltaX(), singleton::mpi().getSize());
  decomposition.setPeriodicity({true,true,false});
  HeuristicLoadBalancer<T> load(decomposition);
  SuperGeometry<T,3> geometry(decomposition,load,1);
  geometry.rename(0,2);
  geometry.rename(2,1,{0,0,1});
  geometry.clean();
  geometry.innerClean();
  geometry.checkForErrors();

  SuperLattice<T,DESCRIPTOR> lattice(converter,geometry);
  dynamics::set<BulkDynamics>(lattice,geometry.getMaterialIndicator(1));
  boundary::set<boundary::BounceBack>(lattice,geometry,2);
  lattice.setParameter<OMEGA>(converter.getLatticeRelaxationFrequency());
  AnalyticalConst3D<T,T> rho0(1.);
  AnalyticalConst3D<T,T> u0(0.,0.,0.);
  lattice.iniEquilibrium(geometry,1,rho0,u0);
  // Guo's descriptor::FORCE is an acceleration field.  The imposed pressure
  // gradient is first divided by the configured liquid density; the OpenLB
  // poiseuille3d example has rho=1 and therefore does not expose this factor.
  const T forceLattice = (gradient/rhoPhys) * converter.getConversionFactorMass() / converter.getConversionFactorForce();
  fields::set<FORCE>(lattice,geometry.getMaterialIndicator(1),Vector<T,3>{forceLattice,0.,0.});
  lattice.initialize();

  const Sample initial = sample(lattice,geometry,converter,dx);
  T previous = initial.meanU;
  T steadyResidual = std::numeric_limits<T>::infinity();
  for (int iT=1; iT<=steps; ++iT) {
    lattice.collideAndStream();
    if (iT % 1000 == 0 || iT == steps) {
      const Sample current = sample(lattice,geometry,converter,dx);
      steadyResidual = std::abs(current.meanU-previous)/std::max(std::abs(current.meanU),T(1e-30));
      previous = current.meanU;
    }
  }
  const Sample final = sample(lattice,geometry,converter,dx);
  const T area = width*hydroH;
  const T Q = final.meanU*area;
  const T deltaP = gradient*length;
  const T resistance = deltaP/Q;
  const T analyticalJ = gradient*hydroH*hydroH/(12.*mu);
  const T analyticalR = 12.*mu*length/(width*hydroH*hydroH*hydroH);
  const T re = rhoPhys*std::abs(final.meanU)*hydroH/mu;
  const T maxMach = lattice.getStatistics().getMaxU()*std::sqrt(3.);
  const T massDrift = (final.meanRho-initial.meanRho)/initial.meanRho;
  T l2num{},l2den{};
  std::ofstream profile(profilePath);
  profile << "z_m,ux_m_s,ux_analytical_m_s\n";
  for (const auto& [row,data] : final.byZ) {
    const T z = (T(row)+1.)*dx;
    const T zHydro = z - .5*dx;
    const T analytical = gradient*zHydro*(hydroH-zHydro)/(2.*mu);
    const T measured = data.first/T(data.second);
    profile << std::setprecision(17) << z << ',' << measured << ',' << analytical << '\n';
    l2num += (measured-analytical)*(measured-analytical);
    l2den += analytical*analytical;
  }
  const T profileL2 = std::sqrt(l2num/l2den);

  std::ofstream out(summaryPath);
  out << std::setprecision(17) << "{\n"
      << "  \"n_hydraulic_gap\": " << nH << ",\n"
      << "  \"body_force_equivalent_pressure_gradient_pa_per_m\": " << gradient << ",\n"
      << "  \"force_lattice\": " << forceLattice << ",\n"
      << "  \"steps\": " << steps << ",\n"
      << "  \"hydraulic_gap_m\": " << hydroH << ",\n"
      << "  \"dx_m\": " << dx << ",\n"
      << "  \"periodic_width_m\": " << width << ",\n"
      << "  \"rho_kg_m3\": " << rhoPhys << ",\n"
      << "  \"mu_pa_s\": " << mu << ",\n"
      << "  \"tau\": " << tau << ",\n"
      << "  \"delta_p_pa\": " << deltaP << ",\n"
      << "  \"q_m3_s\": " << Q << ",\n"
      << "  \"j_m_s\": " << final.meanU << ",\n"
      << "  \"analytical_j_m_s\": " << analyticalJ << ",\n"
      << "  \"hydraulic_resistance_pa_s_m3\": " << resistance << ",\n"
      << "  \"analytical_hydraulic_resistance_pa_s_m3\": " << analyticalR << ",\n"
      << "  \"mean_flow_relative_error\": " << std::abs(final.meanU-analyticalJ)/analyticalJ << ",\n"
      << "  \"resistance_relative_error\": " << std::abs(resistance-analyticalR)/analyticalR << ",\n"
      << "  \"velocity_profile_normalized_l2_error\": " << profileL2 << ",\n"
      << "  \"re\": " << re << ",\n"
      << "  \"max_lattice_mach\": " << maxMach << ",\n"
      << "  \"mass_drift_fraction\": " << massDrift << ",\n"
      << "  \"steady_relative_change_over_1000_steps\": " << steadyResidual << "\n"
      << "}\n";
  std::cout << "XY0_CASE_COMPLETE nH=" << nH << " G=" << gradient
            << " J=" << final.meanU << " R=" << resistance << '\n';
  return 0;
}
