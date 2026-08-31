// P0: two-phase depth-integrated kinematic piston ledger.
//
// q_l=h*alpha_l and q_g=h*(1-alpha_l) are transported with the same resolved
// face flux. No phase field is multiplied by h_old/h_new; no clipping or mass
// deletion is used. This is a candidate moving-depth conservation test. The
// 100-to-80 um history is not a confirmed EC1XT240 physical process; if such a
// process is later confirmed, this result is reusable numerical evidence.

#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

namespace {
using T = double;
constexpr int kNx = 160;
constexpr int kNy = 40;
constexpr int kSteps = 30000;
constexpr T kH0 = 100.e-6;
constexpr T kHFinal = 80.e-6;

T smoothstep(T s) { return s*s*s*(10.-15.*s+6.*s*s); }

struct Outcome {
  T liquidResidual{};
  T gasResidual{};
  T closureError{};
  T minAlpha{std::numeric_limits<T>::max()};
  T maxAlpha{-std::numeric_limits<T>::max()};
  T initialRightAlpha{};
  T finalRightAlpha{};
  T initialLiquidCentroidX{};
  T finalLiquidCentroidX{};
  T liquidOut{};
  T gasOut{};
  T maxFaceVelocity{};
  bool finite{true};
};

Outcome run()
{
  const int cells = kNx*kNy;
  std::vector<T> qLiquid(cells), qGas(cells), nextLiquid(cells), nextGas(cells);
  T h = kH0;
  Outcome result;
  T initialLiquid{};
  T initialGas{};
  for (int y=0; y<kNy; ++y) {
    for (int x=0; x<kNx; ++x) {
      const T alpha = T(.5)*(1.-std::tanh((T(x)+T(.5)-T(.30)*kNx)/T(2)));
      const int i=x+kNx*y;
      qLiquid[i]=h*alpha;
      qGas[i]=h*(1.-alpha);
      initialLiquid+=qLiquid[i];
      initialGas+=qGas[i];
      result.initialLiquidCentroidX+=qLiquid[i]*(T(x)+T(.5));
      if (x>=kNx/2) result.initialRightAlpha+=alpha;
    }
  }
  result.initialRightAlpha /= T(kNx/2*kNy);
  result.initialLiquidCentroidX /= initialLiquid;

  for (int step=0; step<kSteps; ++step) {
    const T hNew = kH0+(kHFinal-kH0)*smoothstep(T(step+1)/kSteps);
    const T divergence = 1.-hNew/h;
    result.maxFaceVelocity=std::max(result.maxFaceVelocity,divergence*T(kNx));
    for (int y=0; y<kNy; ++y) {
      std::vector<T> fluxLiquid(kNx+1), fluxGas(kNx+1);
      for (int face=1; face<=kNx; ++face) {
        const T velocity=divergence*T(face);
        const int upwind=(face-1)+kNx*y;
        fluxLiquid[face]=velocity*qLiquid[upwind];
        fluxGas[face]=velocity*qGas[upwind];
      }
      result.liquidOut+=fluxLiquid[kNx];
      result.gasOut+=fluxGas[kNx];
      for (int x=0; x<kNx; ++x) {
        const int i=x+kNx*y;
        nextLiquid[i]=qLiquid[i]-(fluxLiquid[x+1]-fluxLiquid[x]);
        nextGas[i]=qGas[i]-(fluxGas[x+1]-fluxGas[x]);
      }
    }
    qLiquid.swap(nextLiquid);
    qGas.swap(nextGas);
    h=hNew;
  }

  T finalLiquid{};
  T finalGas{};
  for (int y=0; y<kNy; ++y) {
    for (int x=0; x<kNx; ++x) {
      const int i=x+kNx*y;
      const T alpha=qLiquid[i]/h;
      result.finite=result.finite && std::isfinite(qLiquid[i]) && std::isfinite(qGas[i]) && std::isfinite(alpha);
      result.minAlpha=std::min(result.minAlpha,alpha);
      result.maxAlpha=std::max(result.maxAlpha,alpha);
      result.closureError=std::max(result.closureError,std::abs(qLiquid[i]+qGas[i]-h));
      finalLiquid+=qLiquid[i];
      finalGas+=qGas[i];
      result.finalLiquidCentroidX+=qLiquid[i]*(T(x)+T(.5));
      if (x>=kNx/2) result.finalRightAlpha+=alpha;
    }
  }
  result.finalRightAlpha/=T(kNx/2*kNy);
  result.finalLiquidCentroidX/=finalLiquid;
  result.liquidResidual=std::abs(finalLiquid-initialLiquid+result.liquidOut)/initialLiquid;
  result.gasResidual=std::abs(finalGas-initialGas+result.gasOut)/initialGas;
  return result;
}

void writeJson(const std::string& path,const Outcome& r,bool pass)
{
  std::ofstream output(path);
  output<<std::setprecision(17)
    <<"{\n"
    <<"  \"test\": \"P0_two_phase_depth_integrated_piston\",\n"
    <<"  \"status\": \""<<(pass?"P0_PRESSING_PASS":"P0_PRESSING_HOLD")<<"\",\n"
    <<"  \"formulation\": \"finite-volume transport of q_l=h*alpha_l and q_g=h*(1-alpha_l); no post-step alpha rescaling or clipping\",\n"
    <<"  \"geometry\": \"rectangular 160x40 planform with one resolved right outlet\",\n"
    <<"  \"depth_m\": ["<<kH0<<", "<<kHFinal<<"],\n"
    <<"  \"liquid_inventory_boundary_residual\": "<<r.liquidResidual<<",\n"
    <<"  \"gas_inventory_boundary_residual\": "<<r.gasResidual<<",\n"
    <<"  \"phase_closure_max_abs\": "<<r.closureError<<",\n"
    <<"  \"phase_range\": ["<<r.minAlpha<<", "<<r.maxAlpha<<"],\n"
    <<"  \"initial_right_half_liquid_fraction\": "<<r.initialRightAlpha<<",\n"
    <<"  \"final_right_half_liquid_fraction\": "<<r.finalRightAlpha<<",\n"
    <<"  \"right_half_liquid_fraction_change\": "<<r.finalRightAlpha-r.initialRightAlpha<<",\n"
    <<"  \"initial_liquid_centroid_x_cells\": "<<r.initialLiquidCentroidX<<",\n"
    <<"  \"final_liquid_centroid_x_cells\": "<<r.finalLiquidCentroidX<<",\n"
    <<"  \"liquid_centroid_displacement_cells\": "<<r.finalLiquidCentroidX-r.initialLiquidCentroidX<<",\n"
    <<"  \"max_face_velocity_lattice\": "<<r.maxFaceVelocity<<",\n"
    <<"  \"finite\": "<<(r.finite?"true":"false")<<"\n"
    <<"}\n";
}
}

int main(int argc,char* argv[])
{
  const Outcome r=run();
  const bool pass=r.finite && r.liquidResidual<1e-12 && r.gasResidual<1e-12
    && r.closureError<1e-12 && r.minAlpha>=-1e-12 && r.maxAlpha<=1.+1e-12
    && r.finalLiquidCentroidX>r.initialLiquidCentroidX+.1 && r.maxFaceVelocity<.05;
  if (argc==2) writeJson(argv[1],r,pass);
  std::cout<<std::setprecision(17)
    <<(pass?"P0_PRESSING_PASS":"P0_PRESSING_HOLD")
    <<" liquid_residual="<<r.liquidResidual
    <<" gas_residual="<<r.gasResidual
    <<" liquid_centroid_displacement="<<r.finalLiquidCentroidX-r.initialLiquidCentroidX
    <<" phase=["<<r.minAlpha<<','<<r.maxAlpha<<']'
    <<" max_face_u="<<r.maxFaceVelocity<<'\n';
  return pass?EXIT_SUCCESS:EXIT_FAILURE;
}
