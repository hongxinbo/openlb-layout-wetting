#include <olb.h>

#include <iostream>
#include <type_traits>

using namespace olb;
using namespace olb::descriptors;

using NS = D3Q19<RHO,NABLARHO,FORCE,EXTERNAL_FORCE,TAU_EFF,SCALAR>;
using PF = D3Q19<CONV_POPS,FORCE,VELOCITY,OLD_PHIU,STATISTIC,PSI,
                 NORMGRADPSI,SCALAR,PSI0,THETA,BOUNDARY>;
using NSDynamics = MultiPhaseIncompressibleInterfaceTRTdynamics<double,NS>;
using PFDynamics = ConservativePhaseFieldBGKdynamics<double,PF>;
using WallProcessor = IsoPhaseFieldCurvedWall3D::Processor<double,PF,1,0,0>;
using WBNS = D3Q19<RHO,NABLARHO,FORCE,EXTERNAL_FORCE,TAU_EFF>;
using WBPF = D3Q19<FORCE,SOURCE,SOURCE_OLD,PHIWETTING,VELOCITY,OLD_PHIU,
                   STATISTIC,CHEM_POTENTIAL,BOUNDARY>;
using WellBalancedPF = WellBalancedCahnHilliardBGKdynamics<double,WBPF>;
using WellBalancedCoupling = WellBalancedCahnHilliardPostProcessor<LinearTauViscosity>;

template <typename T, typename = void>
struct is_complete : std::false_type { };

template <typename T>
struct is_complete<T,std::void_t<decltype(sizeof(T))>> : std::true_type { };

int main(int argc, char* argv[])
{
  initialize(&argc,&argv);
  static_assert(NS::d == 3 && NS::q == 19);
  static_assert(PF::d == 3 && PF::q == 19);
  static_assert(is_complete<NSDynamics>::value);
  static_assert(is_complete<PFDynamics>::value);
  static_assert(is_complete<LiangPostProcessor>::value);
  static_assert(is_complete<WallProcessor>::value);
  static_assert(is_complete<WellBalancedPF>::value);
  static_assert(is_complete<WellBalancedCoupling>::value);
  static_assert(!is_complete<boundary::PhaseFieldCurvedWall<double,PF>>::value,
                "OpenLB checkout unexpectedly gained a direct 3-D PhaseFieldCurvedWall specialization");
  static_assert(!is_complete<boundary::IncompressibleZouHePressure<double,NS>>::value,
                "OpenLB checkout unexpectedly enabled its 3-D multiphase pressure specialization");
  SuperVTMwriter3D<double>* writer = nullptr;
  (void)writer;
  std::cout
    << "OPENLB_3D_COMPILE_AUDIT_PASS\n"
    << "D3Q19_NAVIER_STOKES=available\n"
    << "D3Q19_CONSERVATIVE_PHASE_FIELD=available\n"
    << "LIANG_POST_PROCESSOR=available\n"
    << "ISO_PHASE_FIELD_CURVED_WALL_3D_PROCESSOR=available\n"
    << "WELL_BALANCED_CAHN_HILLIARD_3D=available_closest_official_wetting_candidate\n"
    << "DIRECT_PHASE_FIELD_CURVED_WALL_3D=unavailable\n"
    << "MULTIPHASE_ZOU_HE_PRESSURE_3D=unavailable_commented_source\n"
    << "SUPER_VTM_WRITER_3D=available\n";
}
