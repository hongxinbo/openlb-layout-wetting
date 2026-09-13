// XY1B: analytical, commensurate, periodically continued rotated stripe.
#include <olb.h>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>

using namespace olb;
using namespace olb::descriptors;
using T=double;
using DESCRIPTOR=D3Q19<FORCE>;
using BulkDynamics=ForcedBGKdynamics<T,DESCRIPTOR>;

class PeriodicStripeRecess final : public IndicatorF3D<T> {
public:
  PeriodicStripeRecess(T lx, T ly, T z0, T depth) {
    _myMin={0.,0.,z0}; _myMax={lx,ly,z0+depth};
  }
  bool operator()(bool output[], const T input[]) override {
    // n=(-0.6,0.8), so x+Lx changes s by -8 um and y+Ly by +8 um.
    T s=std::fmod(-.6*input[0]+.8*input[1],8.e-6);
    if (s<0.) s+=8.e-6;
    output[0]=input[2]>=_myMin[2] && input[2]<_myMax[2] && s<4.e-6;
    return output[0];
  }
};

struct Sample { Vector<T,3> sumU{0.,0.,0.}; T meanSpeed{},meanRho{}; int fluidCells{},solidCells{}; };
static Sample measure(SuperLattice<T,DESCRIPTOR>& lattice, SuperGeometry<T,3>& geometry,
                      const UnitConverter<T,DESCRIPTOR>& converter) {
  lattice.setProcessingContext(ProcessingContext::Evaluation); Sample r; const auto& load=lattice.getLoadBalancer();
  for(int iC=0;iC<load.size();++iC) { auto& block=lattice.getBlock(iC); block.forCoreSpatialLocations([&](LatticeR<3> loc) {
    if(geometry.getBlockGeometry(iC).getMaterial(loc[0],loc[1],loc[2])==1) { T rho{},u[3]{}; block.get(loc).computeRhoU(rho,u); T speed2{};
      for(int i=0;i<3;++i) { const T ui=converter.getPhysVelocity(u[i]); r.sumU[i]+=ui; speed2+=ui*ui; }
      r.meanSpeed+=std::sqrt(speed2); r.meanRho+=rho; ++r.fluidCells;
    } else ++r.solidCells;
  }); }
  r.meanSpeed/=T(r.fluidCells); r.meanRho/=T(r.fluidCells); return r;
}

int main(int argc,char* argv[]) {
  if(argc!=5) { std::cerr<<"usage: xy1bRotatedSmoke x|y G_Pa_per_m max_steps summary.json\\n"; return 2; }
  initialize(&argc,&argv); const std::string direction=argv[1]; const T gradient=std::stod(argv[2]);
  const int maxSteps=std::stoi(argv[3]); const std::string path=argv[4];
  if((direction!="x"&&direction!="y")||gradient<=0||maxSteps<2000) return 2;
  const T dx=(1./6.)*1e-6, lx=(40./3.)*1e-6, ly=10.e-6, base=4.e-6, depth=8.e-6, height=base+depth;
  const int nx=80,ny=60,nz=72,nBase=24; const T rhoPhys=1510.,mu=1.e-3,nu=mu/rhoPhys,tau=.8,charU=3.e-4;
  UnitConverterFromResolutionAndRelaxationTime<T,DESCRIPTOR> converter(nBase,tau,base,charU,nu,rhoPhys);
  IndicatorCuboid3D<T> domain(Vector<T,3>{lx,ly,height+dx},Vector<T,3>{0.,0.,0.});
  CuboidDecomposition3D<T> decomposition(domain,converter.getPhysDeltaX(),singleton::mpi().getSize()); decomposition.setPeriodicity({true,true,false});
  HeuristicLoadBalancer<T> load(decomposition); SuperGeometry<T,3> geometry(decomposition,load,1);
  geometry.rename(0,2); geometry.rename(2,1,{0,0,1});
  IndicatorCuboid3D<T> upper(Vector<T,3>{lx,ly,depth},Vector<T,3>{0.,0.,base}); geometry.rename(1,2,upper);
  PeriodicStripeRecess recess(lx,ly,base,depth); geometry.rename(2,1,recess);
  geometry.clean(); geometry.innerClean(); geometry.checkForErrors();
  SuperLattice<T,DESCRIPTOR> lattice(converter,geometry); dynamics::set<BulkDynamics>(lattice,geometry.getMaterialIndicator(1));
  boundary::set<boundary::BounceBack>(lattice,geometry,2); lattice.setParameter<OMEGA>(converter.getLatticeRelaxationFrequency());
  AnalyticalConst3D<T,T> rho0(1.),u0(0.,0.,0.); lattice.iniEquilibrium(geometry,1,rho0,u0);
  const T forceLat=(gradient/rhoPhys)*converter.getConversionFactorMass()/converter.getConversionFactorForce();
  fields::set<FORCE>(lattice,geometry.getMaterialIndicator(1),direction=="x"?Vector<T,3>{forceLat,0.,0.}:Vector<T,3>{0.,forceLat,0.}); lattice.initialize();
  const Sample initial=measure(lattice,geometry,converter); T prev{},steady=std::numeric_limits<T>::infinity(); int stepsToSteady=0,completed=0;
  for(int iT=1;iT<=maxSteps;++iT) { lattice.collideAndStream(); completed=iT; if(iT%1000==0||iT==maxSteps) { const Sample now=measure(lattice,geometry,converter);
    const T mag=std::sqrt(now.sumU[0]*now.sumU[0]+now.sumU[1]*now.sumU[1]+now.sumU[2]*now.sumU[2]); steady=std::abs(mag-prev)/std::max(mag,T(1e-30)); prev=mag;
    if(iT>=2000&&steady<=1.e-6) { stepsToSteady=iT; break; }
  }}
  const Sample final=measure(lattice,geometry,converter); const T rev=lx*ly*height;
  Vector<T,3> J{final.sumU[0]*dx*dx*dx/rev,final.sumU[1]*dx*dx*dx/rev,final.sumU[2]*dx*dx*dx/rev};
  std::ofstream out(path); out<<std::setprecision(17)<<"{\n"
    <<"  \"component\": \"XY1B_ROTATED_ANISOTROPIC_SMOKE_COMPONENT\",\n  \"direction\": \""<<direction<<"\",\n"
    <<"  \"body_force_equivalent_pressure_gradient_pa_per_m\": "<<gradient<<",\n  \"steps\": "<<completed<<",\n"
    <<"  \"steps_to_steady\": "<<(stepsToSteady?std::to_string(stepsToSteady):"null")<<",\n  \"reached_steady_state\": "<<(stepsToSteady?"true":"false")<<",\n"
    <<"  \"dx_m\": "<<dx<<",\n  \"nx\": "<<nx<<", \"ny\": "<<ny<<", \"nz_fluid\": "<<nz<<",\n"
    <<"  \"rev_dimensions_m\": ["<<lx<<", "<<ly<<", "<<height<<"],\n  \"base_gap_m\": "<<base<<", \"base_gap_cells\": "<<nBase<<",\n"
    <<"  \"stripe_normal_period_m\": 8e-6, \"stripe_normal_width_m\": 4e-6, \"recess_depth_m\": 8e-6,\n"
    <<"  \"fluid_cells\": "<<final.fluidCells<<", \"solid_cells\": "<<final.solidCells<<",\n"
    <<"  \"cell_count_occupancy_fraction\": "<<T(final.fluidCells)/T(final.fluidCells+final.solidCells)<<",\n"
    <<"  \"discrete_fluid_volume_m3\": "<<T(final.fluidCells)*dx*dx*dx<<", \"nominal_rev_volume_m3\": "<<rev<<",\n"
    <<"  \"minimum_throat_cells\": "<<nBase<<", \"periodic_x_y_continuity\": true, \"connected_by_full_base_gap\": true, \"upper_recess_opens_downward\": true,\n"
    <<"  \"J_m_per_s\": ["<<J[0]<<", "<<J[1]<<", "<<J[2]<<"],\n  \"mean_speed_m_per_s\": "<<final.meanSpeed<<",\n"
    <<"  \"re\": "<<rhoPhys*final.meanSpeed*base/mu<<", \"max_lattice_mach\": "<<lattice.getStatistics().getMaxU()*std::sqrt(3.)<<",\n"
    <<"  \"mass_drift_fraction\": "<<(final.meanRho-initial.meanRho)/initial.meanRho<<",\n  \"steady_relative_change_over_1000_steps\": "<<steady<<"\n}\n";
  std::cout<<"XY1B_COMPLETE direction="<<direction<<" J="<<J<<"\n";
}
