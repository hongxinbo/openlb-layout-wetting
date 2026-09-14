// SIM240 first-stage velocity-inlet / pressure-outlet resistance solver.
// Boundary API follows OpenLB 1.9 examples/laminar/poiseuille3d/case.h.
#include <olb.h>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

using namespace olb;
using namespace olb::descriptors;
using T = double;
using DESCRIPTOR = D3Q19<>;

struct Metrics {
  T qIn{}, qMid{}, qOut{}, pIn{}, pOut{}, pInInterior{}, pOutInterior{};
  T rhoMin{std::numeric_limits<T>::max()}, rhoMax{-std::numeric_limits<T>::max()};
  T meanU{}, meanRho{}, maxU{}; long fluidCells{};
};

static Metrics sample(SuperLattice<T,DESCRIPTOR>& lattice, SuperGeometry<T,3>& geometry,
                      const UnitConverter<T,DESCRIPTOR>& converter, int axis,
                      T flowLength, T dx, bool writeField, const std::string& fieldPath)
{
  lattice.setProcessingContext(ProcessingContext::Evaluation);
  Metrics m; T sumU{},sumRho{}; long count{}; std::ofstream f;
  if (writeField) { f.open(fieldPath); f << "x_m,y_m,z_m,material,ux_m_s,uy_m_s,uz_m_s,p_pa,rho\n"; }
  const auto& load = lattice.getLoadBalancer();
  const T inletX = 0., outletX = flowLength-dx;
  long nIn{},nMid{},nOut{},nIntIn{},nIntOut{};
  for (int iC=0; iC<load.size(); ++iC) {
    auto& block=lattice.getBlock(iC); auto& bg=geometry.getBlockGeometry(iC);
    block.forCoreSpatialLocations([&](LatticeR<3> loc) {
      const int mat=bg.getMaterial(loc[0],loc[1],loc[2]);
      if (mat!=1 && mat!=3 && mat!=4) return;
      T rho{},u[3]{}; block.get(loc).computeRhoU(rho,u);
      const auto phys=lattice.getCuboidDecomposition().getPhysR(loc.withPrefix(load.glob(iC)));
      const T un=converter.getPhysVelocity(u[axis]);
      const T p=converter.getPhysPressure((rho-1.)/descriptors::invCs2<T,DESCRIPTOR>());
      m.rhoMin=std::min(m.rhoMin,rho); m.rhoMax=std::max(m.rhoMax,rho);
      m.maxU=std::max(m.maxU,std::sqrt(u[0]*u[0]+u[1]*u[1]+u[2]*u[2]));
      sumU += un; sumRho += rho; ++count;
      const T s=phys[axis];
      if (std::abs(s-inletX)<.51*dx) { m.qIn += un*dx*dx; m.pIn += p; ++nIn; }
      if (std::abs(s-(flowLength/2))<.51*dx) { m.qMid += un*dx*dx; ++nMid; }
      if (std::abs(s-outletX)<.51*dx) { m.qOut += un*dx*dx; m.pOut += p; ++nOut; }
      if (std::abs(s-2.*dx)<.51*dx) {m.pInInterior += p; ++nIntIn;}
      if (std::abs(s-(flowLength-3.*dx))<.51*dx) {m.pOutInterior += p; ++nIntOut;}
      if (writeField && ((axis==1 && std::abs(phys[0]-120e-9)<.51*dx) ||
                         (axis==0 && std::abs(phys[1]-120e-9)<.51*dx)))
        f << std::setprecision(17)<<phys[0]<<','<<phys[1]<<','<<phys[2]<<','<<mat<<','
          <<converter.getPhysVelocity(u[0])<<','<<converter.getPhysVelocity(u[1])<<','
          <<converter.getPhysVelocity(u[2])<<','<<p<<','<<rho<<'\n';
    });
  }
  if(nIn)m.pIn/=nIn; if(nOut)m.pOut/=nOut; if(nIntIn)m.pInInterior/=nIntIn; if(nIntOut)m.pOutInterior/=nIntOut;
  m.meanU=count?sumU/T(count):0; m.meanRho=count?sumRho/T(count):0; m.fluidCells=count;
  return m;
}

int main(int argc,char* argv[]) {
  if(argc!=8){std::cerr<<"usage: sim240Transport3d flat|along|across U_m_s maxSteps checkEvery tolerance summary.json field.csv\n";return 2;}
  initialize(&argc,&argv);
  const std::string kind=argv[1], outPath=argv[6], fieldPath=argv[7];
  const T U=std::stod(argv[2]), tol=std::stod(argv[5]);
  const int maxSteps=std::stoi(argv[3]), checkEvery=std::stoi(argv[4]);
  if(kind!="flat"&&kind!="along"&&kind!="across") return 2;
  constexpr T dx=5e-9,H=75e-9,D=100e-9,P=240e-9,land=60e-9,groove=120e-9,L=2.4e-6;
  constexpr T rhoPhys=1000.,mu=1e-3,tau=.8;
  const int axis=(kind=="across"?0:1); const T transverse=P;
  const Vector<T,3> baseExt = axis==1 ? Vector<T,3>{transverse-dx,L-dx,H-dx} : Vector<T,3>{L-dx,transverse-dx,H-dx};
  const Vector<T,3> zero{0.,0.,0.};
  auto fluid=std::shared_ptr<IndicatorF3D<T>>(new IndicatorCuboid3D<T>(baseExt,zero));
  if(kind=="along") fluid = fluid + std::shared_ptr<IndicatorF3D<T>>(new IndicatorCuboid3D<T>({groove-dx,L-dx,D-dx},{land,0.,H}));
  if(kind=="across") for(int i=0;i<10;++i) fluid = fluid + std::shared_ptr<IndicatorF3D<T>>(new IndicatorCuboid3D<T>({groove-dx,transverse-dx,D-dx},{i*P+land,0.,H}));
  const T zmax=(kind=="flat"?H:H+D);
  const Vector<T,3> boundingExt = axis==1 ? Vector<T,3>{P-dx,L+dx,zmax+dx} : Vector<T,3>{L+dx,P-dx,zmax+dx};
  const Vector<T,3> boundingOrg = axis==1 ? Vector<T,3>{0.,-dx,-dx} : Vector<T,3>{-dx,0.,-dx};
  IndicatorCuboid3D<T> bounding(boundingExt,boundingOrg);
  UnitConverterFromResolutionAndRelaxationTime<T,DESCRIPTOR> converter(15,tau,H,U,mu/rhoPhys,rhoPhys);
  CuboidDecomposition3D<T> decomposition(bounding,dx,singleton::mpi().getSize());
  decomposition.setPeriodicity(axis==1?Vector<bool,3>{true,false,false}:Vector<bool,3>{false,true,false});
  HeuristicLoadBalancer<T> load(decomposition); SuperGeometry<T,3> geometry(decomposition,load,1);
  geometry.rename(0,2); geometry.rename(2,1,*fluid);
  Vector<T,3> inExt=baseExt,outExt=baseExt,inOrg=zero,outOrg=zero;
  if(kind!="flat") { inExt[2]=H+D-dx; outExt[2]=H+D-dx; }
  inExt[axis]=.1*dx; outExt[axis]=.1*dx; outOrg[axis]=L-dx;
  IndicatorCuboid3D<T> inlet(inExt,inOrg),outlet(outExt,outOrg);
  geometry.rename(1,3,inlet); geometry.rename(1,4,outlet); geometry.clean(); geometry.innerClean(); geometry.checkForErrors(); geometry.updateStatistics();
  SuperLattice<T,DESCRIPTOR> lattice(converter,geometry);
  dynamics::set<BGKdynamics>(lattice,geometry.getMaterialIndicator({1,3,4}));
  boundary::set<boundary::BounceBack>(lattice,geometry,2);
  boundary::set<boundary::InterpolatedVelocity>(lattice,geometry,3);
  boundary::set<boundary::InterpolatedPressure>(lattice,geometry,4);
  lattice.setParameter<OMEGA>(converter.getLatticeRelaxationFrequency());
  const T areaIn=(kind=="along"?P*(H+D):P*H);
  const T resistanceGuess=(kind=="flat"?2.844444444444445e20:(kind=="along"?1.17312e20:2.97537e20));
  const T pressureGuess=resistanceGuess*areaIn*U;
  AnalyticalLinear3D<T,T> pressure0(axis==0?-pressureGuess/L:0.,axis==1?-pressureGuess/L:0.,0.,pressureGuess);
  AnalyticalConst3D<T,T> u0(axis==0?U:0.,axis==1?U:0.,0.);
  momenta::setPressureAndVelocity(lattice,geometry.getMaterialIndicator({1,3,4}),pressure0,u0);
  momenta::setVelocity(lattice,geometry.getMaterialIndicator(3),Vector<T,3>{axis==0?U:0.,axis==1?U:0.,0.});
  momenta::setPressure(lattice,geometry.getMaterialIndicator(4),T(0));
  lattice.initialize();
  Metrics initial=sample(lattice,geometry,converter,axis,L,dx,false,fieldPath),current=initial;
  T prevQ=current.qMid,residual=std::numeric_limits<T>::infinity(); int steps=0,steadyHits=0;
  for(int i=1;i<=maxSteps;++i){
    lattice.collideAndStream();
    momenta::setVelocity(lattice,geometry.getMaterialIndicator(3),Vector<T,3>{axis==0?U:0.,axis==1?U:0.,0.});
    momenta::setPressure(lattice,geometry.getMaterialIndicator(4),T(0));
    if(i%checkEvery==0){current=sample(lattice,geometry,converter,axis,L,dx,false,fieldPath);residual=std::abs(current.qMid-prevQ)/std::max(std::abs(current.qMid),T(1e-40));prevQ=current.qMid;steadyHits=residual<tol?steadyHits+1:0;if(steadyHits>=3){steps=i;break;}}
    steps=i;
  }
  current=sample(lattice,geometry,converter,axis,L,dx,true,fieldPath);
  const T dP=current.pIn-current.pOut,q=(current.qIn+current.qMid+current.qOut)/3.;
  const T imb=std::max({std::abs(current.qIn-q),std::abs(current.qMid-q),std::abs(current.qOut-q)})/std::max(std::abs(q),T(1e-40));
  const T re=rhoPhys*std::abs(current.meanU)*H/mu,mach=current.maxU*std::sqrt(3.),massDrift=(current.meanRho-initial.meanRho)/initial.meanRho;
  std::ofstream o(outPath); o<<std::setprecision(17)<<"{\n"
   <<"\"case\":\""<<kind<<"\",\"u_in_m_s\":"<<U<<",\"dx_m\":"<<dx<<",\"flow_length_m\":"<<L<<",\"transverse_width_m\":"<<transverse<<",\"base_gap_m\":"<<H<<",\"groove_depth_m\":"<<(kind=="flat"?0:D)<<",\"nx_nominal\":"<<(axis==0?480:48)<<",\"ny_nominal\":"<<(axis==1?480:48)<<",\"nz_nominal\":"<<(kind=="flat"?15:35)<<",\n"
   <<"\"q_in_m3_s\":"<<current.qIn<<",\"q_mid_m3_s\":"<<current.qMid<<",\"q_out_m3_s\":"<<current.qOut<<",\"q_mean_m3_s\":"<<q<<",\"mean_u_m_s\":"<<current.meanU<<",\"p_in_pa\":"<<current.pIn<<",\"p_out_pa\":"<<current.pOut<<",\"delta_p_pa\":"<<dP<<",\"resistance_pa_s_m3\":"<<dP/q<<",\n"
   <<"\"p_interior_in_pa\":"<<current.pInInterior<<",\"p_interior_out_pa\":"<<current.pOutInterior<<",\"re\":"<<re<<",\"max_lattice_mach\":"<<mach<<",\"rho_min\":"<<current.rhoMin<<",\"rho_max\":"<<current.rhoMax<<",\"mass_drift_fraction\":"<<massDrift<<",\"relative_flow_imbalance\":"<<imb<<",\"steps_to_steady\":"<<steps<<",\"steady_residual\":"<<residual<<",\"steady\":"<<(steadyHits>=3?"true":"false")<<",\"fluid_cells\":"<<current.fluidCells<<"\n}\n";
  std::cout<<"SIM240_CASE_COMPLETE "<<kind<<" U="<<U<<" dP="<<dP<<" Q="<<q<<" steady="<<(steadyHits>=3)<<"\n";
}
