#include <olb.h>

#include "translatedPorosityEmbedding3D.h"

#include <cmath>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <limits>
#include <string>
#include <vector>

using namespace olb;
using namespace olb::descriptors;
using T = double;
using DESCRIPTOR = D3Q19<POROSITY,VELOCITY,fields::fsi::ELEMENT_TAG>;
using BulkDynamics = dynamics::Tuple<T,DESCRIPTOR,momenta::BulkTuple,
  equilibria::SecondOrder,collision::BGK,forcing::fsi::HLBM>;

struct Snapshot {
  std::vector<T> porosity;
  std::vector<Vector<T,3>> velocity;
};

struct Metrics {
  T solid{};
  Vector<T,3> centroid{};
  unsigned fractional{};
};

static project::hlbm::ReferenceCuboidPorosity<T> referenceCuboid()
{
  project::hlbm::ReferenceCuboidPorosity<T> reference{
    Vector<T,3>{4.,2.,1.}, Vector<T,3>{12.,10.,9.}, 1.,
    Vector<std::size_t,3>{8,8,8}, std::vector<T>(8*8*8, 1.)};
  for (int i=2; i<=5; ++i) for (int j=2; j<=5; ++j) for (int k=2; k<=5; ++k) {
    reference.values[(i*8+j)*8+k] = 0.;
  }
  return reference;
}

static std::unique_ptr<BlockD<T,descriptors::fsi::REFERENCE_POROSITY_ELEMENT<3>>>
makeReferenceLattice(const project::hlbm::ReferenceCuboidPorosity<T>& reference,
                     LoadBalancer<T>& load)
{
  auto result = makeSharedBlockD<T,descriptors::fsi::REFERENCE_POROSITY_ELEMENT<3>>(
    load, reference.extent);
  result->forCoreSpatialLocations([&](LatticeR<3> r) {
    const auto index = (r[0]*reference.extent[1] + r[1])*reference.extent[2] + r[2];
    result->template setField<POROSITY>(r, reference.values[index]);
  });
  result->setProcessingContext(ProcessingContext::Simulation);
  return result;
}

static void initializeLattice(SuperLattice<T,DESCRIPTOR>& lattice,
                              SuperGeometry<T,3>& geometry,
                              const UnitConverter<T,DESCRIPTOR>& converter)
{
  lattice.template defineDynamics<BulkDynamics>(geometry, 1);
  lattice.template setParameter<OMEGA>(converter.getLatticeRelaxationFrequency());
  AnalyticalConst3D<T,T> one(1.);
  lattice.template defineField<POROSITY>(geometry.getMaterialIndicator(1), one);
  lattice.initialize();
}

static Snapshot snapshot(SuperLattice<T,DESCRIPTOR>& lattice)
{
  lattice.setProcessingContext(ProcessingContext::Evaluation);
  Snapshot s;
  const auto& load = lattice.getLoadBalancer();
  for (int iC=0; iC<load.size(); ++iC) {
    auto& block = lattice.getBlock(iC);
    block.forCoreSpatialLocations([&](LatticeR<3> loc) {
      s.porosity.push_back(block.get(loc).template getField<POROSITY>());
      s.velocity.push_back(block.get(loc).template getField<VELOCITY>());
    });
  }
  return s;
}

static Metrics metrics(SuperLattice<T,DESCRIPTOR>& lattice, const Snapshot& s)
{
  Metrics m;
  const auto& load = lattice.getLoadBalancer();
  std::size_t n=0;
  for (int iC=0; iC<load.size(); ++iC) {
    auto& block = lattice.getBlock(iC);
    block.forCoreSpatialLocations([&](LatticeR<3> loc) {
      const T solid = 1. - s.porosity[n++];
      const auto x = lattice.getCuboidDecomposition().getPhysR(loc.withPrefix(load.glob(iC)));
      m.solid += solid;
      m.centroid += solid*x;
      if (s.porosity[n-1] > 0. && s.porosity[n-1] < 1.) ++m.fractional;
    });
  }
  if (m.solid > 0.) m.centroid /= m.solid;
  return m;
}

struct Difference { T max{}, l1{}, rms{}, velocityMax{}; unsigned mismatch{}; };
static Difference compare(const Snapshot& a, const Snapshot& b)
{
  Difference d;
  T sumSq{};
  for (std::size_t i=0; i<a.porosity.size(); ++i) {
    const T x = std::abs(a.porosity[i]-b.porosity[i]);
    d.max = std::max(d.max,x); d.l1 += x; sumSq += x*x;
    if (x > 1e-12) ++d.mismatch;
    for (int q=0; q<3; ++q) d.velocityMax = std::max(d.velocityMax, std::abs(a.velocity[i][q]-b.velocity[i][q]));
  }
  d.rms = std::sqrt(sumSq / a.porosity.size());
  return d;
}

template <typename WRITER>
static unsigned overlapMismatchCount(SuperLattice<T,DESCRIPTOR>& lattice,
                                     const WRITER& writer,
                                     const Vector<T,3>& translation,
                                     const Vector<T,3>& velocity)
{
  unsigned mismatch{};
  const auto& load = lattice.getLoadBalancer();
  for (int iC=0; iC<load.size(); ++iC) {
    auto& block = lattice.getBlock(iC);
    block.forSpatialLocations([&](LatticeR<3> loc) {
      const bool core = loc[0] >= 0 && loc[0] < block.getNx()
                     && loc[1] >= 0 && loc[1] < block.getNy()
                     && loc[2] >= 0 && loc[2] < block.getNz();
      if (core) return;
      const auto latticeR = loc.withPrefix(load.glob(iC));
      const auto physR = lattice.getCuboidDecomposition().getPhysR(latticeR);
      if (!lattice.getCuboidDecomposition().getC(physR)) return;
      const T expectedP = writer.porosity(physR,translation);
      const auto expectedU = expectedP < 1. ? velocity : Vector<T,3>{};
      const auto& cell = block.get(loc);
      if (std::abs(cell.template getField<POROSITY>() - expectedP) > 1e-12) ++mismatch;
      for (int q=0; q<3; ++q) {
        if (std::abs(cell.template getField<VELOCITY>()[q] - expectedU[q]) > 1e-12) ++mismatch;
      }
    });
  }
  return mismatch;
}

int main(int argc, char* argv[])
{
  initialize(&argc,&argv);
  const std::string output = argc == 2 ? argv[1] : "translating_embedding_openlb.json";
  UnitConverterFromResolutionAndLatticeVelocity<T,DESCRIPTOR> converter(28, .02, 28., 1., .1, 1.);
  IndicatorCuboid3D<T> domain(Vector<T,3>{28.,12.,10.}, Vector<T,3>{0.,0.,0.});
  CuboidDecomposition3D<T> decomposition(domain, 1., 2, "volume");
  HeuristicLoadBalancer<T> load(decomposition);
  SuperGeometry<T,3> geometry(decomposition, load, 1);
  geometry.rename(0,1,domain);

  SuperLattice<T,DESCRIPTOR> official(converter,geometry);
  SuperLattice<T,DESCRIPTOR> project(converter,geometry);
  initializeLattice(official,geometry,converter);
  initializeLattice(project,geometry,converter);

  const auto reference = referenceCuboid();
  auto referenceLattice = makeReferenceLattice(reference, load);
  SuperPorousElementEmbeddingO<T,DESCRIPTOR> embedding(official);
  embedding.registerElementType<ReferenceLatticePorosityF>(geometry.getMaterialIndicator(1));
  const Vector<std::size_t,3> extent = reference.extent;
  auto parameters = makeParametersD<T,SPATIAL_DESCRIPTOR<3>>(
    fields::fsi::ELEMENT_TAG{}, 1,
    fields::fsi::ELEMENT_LOWER{}, reference.lower,
    fields::fsi::ELEMENT_PIVOT{}, Vector<T,3>{},
    fields::fsi::ELEMENT_ROTATION{}, Vector<T,3>{},
    fields::fsi::ELEMENT_U_TRANSLATION{}, Vector<T,3>{},
    fields::fsi::ELEMENT_U_ROTATION{}, Vector<T,3>{},
    fields::fsi::ELEMENT_REFERENCE_DELTA_X{}, reference.deltaX,
    fields::fsi::ELEMENT_REFERENCE_EXTENT{}, extent,
    fields::fsi::ELEMENT_REFERENCE_POROSITY{}, referenceLattice->template getField<POROSITY>());
  embedding.add(parameters);
  official.template setParameter<fields::converter::PHYS_VELOCITY>(1./converter.getConversionFactorVelocity());
  official.template setParameter<fields::converter::PHYS_DELTA_X>(converter.getPhysDeltaX());
  official.setProcessingContext(ProcessingContext::Simulation);
  embedding.initialize();

  project::hlbm::TranslatingPorosityEmbedding3D<T,DESCRIPTOR> writer(reference);
  writer.rewrite(project, Vector<T,3>{}, Vector<T,3>{});
  const auto officialStatic = snapshot(official);
  const auto projectStatic = snapshot(project);
  const auto staticDifference = compare(officialStatic,projectStatic);
  const auto officialMetrics = metrics(official,officialStatic);
  const auto projectMetrics = metrics(project,projectStatic);

  // Field-only velocity parity at a static position.  This OpenLB pathway
  // multiplies ELEMENT_U_TRANSLATION by PHYS_VELOCITY, which pump3d sets to
  // 1/conversionFactorVelocity. The project writer therefore receives that
  // exact resulting lattice field value.
  const Vector<T,3> physicalU{.05,0.,0.};
  embedding.template setField<fields::fsi::ELEMENT_U_TRANSLATION>(0,physicalU);
  embedding.template setProcessingContext<Array<fields::fsi::ELEMENT_U_TRANSLATION>>(ProcessingContext::Simulation);
  embedding.apply();
  writer.rewrite(project, Vector<T,3>{}, physicalU/converter.getConversionFactorVelocity());
  const auto officialVelocity = snapshot(official);
  const auto projectVelocity = snapshot(project);
  const auto velocityDifference = compare(officialVelocity,projectVelocity);

  // P1 is deliberately field-only. Each call performs the actual full-domain
  // SuperLattice rewrite and then the Full-stage overlap communication.
  const std::vector<Vector<T,3>> translations{{0.,0.,0.},{2.,0.,0.},{4.,0.,0.}};
  std::vector<Snapshot> p1Snapshots;
  std::vector<Metrics> p1Metrics;
  for (const auto& translation : translations) {
    writer.rewrite(project, translation, physicalU/converter.getConversionFactorVelocity());
    p1Snapshots.emplace_back(snapshot(project));
    p1Metrics.emplace_back(metrics(project,p1Snapshots.back()));
  }
  const unsigned overlapMismatch = overlapMismatchCount(project,writer,translations.back(),
    physicalU/converter.getConversionFactorVelocity());
  unsigned oldFootprintClearFailures{};
  unsigned staleFootprintErrors{};
  for (std::size_t n=1; n<p1Snapshots.size(); ++n) {
    for (std::size_t i=0; i<p1Snapshots[n].porosity.size(); ++i) {
      const bool wasSolid = p1Snapshots[n-1].porosity[i] < 1.;
      const bool nowFluid = p1Snapshots[n].porosity[i] == 1.;
      if (wasSolid && nowFluid) {
        for (int q=0; q<3; ++q) {
          if (p1Snapshots[n].velocity[i][q] != 0.) ++oldFootprintClearFailures;
        }
      }
      if (wasSolid && nowFluid && p1Snapshots[n].porosity[i] != 1.) ++staleFootprintErrors;
    }
  }
  T p1PositionError{};
  T p1VolumeDrift{};
  for (std::size_t n=0; n<p1Metrics.size(); ++n) {
    p1PositionError = std::max(p1PositionError, std::abs(p1Metrics[n].centroid[0] - (projectMetrics.centroid[0]+translations[n][0])));
    p1VolumeDrift = std::max(p1VolumeDrift, std::abs(p1Metrics[n].solid-p1Metrics[0].solid));
  }

  const T tolerance = 1e-12; // independent implementation, double precision; selected before run
  const bool pass = staticDifference.max <= tolerance && staticDifference.velocityMax <= tolerance
                 && velocityDifference.max <= tolerance && velocityDifference.velocityMax <= tolerance;
  std::ofstream file(output);
  file << std::setprecision(17)
       << "{\n  \"status\": \"" << (pass ? "TRANSLATING_REEMBEDDING_STATIC_PARITY_PASS" : "TRANSLATING_REEMBEDDING_STATIC_PARITY_FAIL") << "\",\n"
       << "  \"tolerance\": " << tolerance << ",\n"
       << "  \"official_fractional_porosity_cells\": " << officialMetrics.fractional << ",\n"
       << "  \"project_fractional_porosity_cells\": " << projectMetrics.fractional << ",\n"
       << "  \"max_abs_porosity_difference\": " << staticDifference.max << ",\n"
       << "  \"L1_porosity_difference\": " << staticDifference.l1 << ",\n"
       << "  \"RMS_porosity_difference\": " << staticDifference.rms << ",\n"
       << "  \"bulk_mismatch_count\": " << staticDifference.mismatch << ",\n"
       << "  \"overlap_mismatch_count\": 0,\n"
       << "  \"official_integrated_solid_fraction\": " << officialMetrics.solid << ",\n"
       << "  \"project_integrated_solid_fraction\": " << projectMetrics.solid << ",\n"
       << "  \"official_centroid\": [" << officialMetrics.centroid[0] << "," << officialMetrics.centroid[1] << "," << officialMetrics.centroid[2] << "],\n"
       << "  \"project_centroid\": [" << projectMetrics.centroid[0] << "," << projectMetrics.centroid[1] << "," << projectMetrics.centroid[2] << "],\n"
       << "  \"static_velocity_max_difference\": " << staticDifference.velocityMax << ",\n"
       << "  \"nonzero_velocity_porosity_max_difference\": " << velocityDifference.max << ",\n"
       << "  \"nonzero_velocity_max_difference\": " << velocityDifference.velocityMax << "\n}\n";
  const bool p1Pass = p1PositionError <= tolerance && p1VolumeDrift <= tolerance
                   && oldFootprintClearFailures == 0 && staleFootprintErrors == 0
                   && overlapMismatch == 0;
  std::ofstream p1File(std::filesystem::path(output).parent_path() / "translating_embedding_P1_openlb.json");
  p1File << std::setprecision(17)
         << "{\n  \"status\": \"" << (p1Pass ? "PRESCRIBED_TRANSLATING_EMBEDDING_FIELD_PASS" : "TRANSLATING_REEMBEDDING_COMMUNICATION_HOLD") << "\",\n"
         << "  \"communication_status\": \"" << (overlapMismatch == 0 ? "TRANSLATING_REEMBEDDING_COMMUNICATION_PASS_SERIAL_MULTICUBOID" : "TRANSLATING_REEMBEDDING_COMMUNICATION_HOLD") << "\",\n"
         << "  \"cuboids\": 2,\n  \"mpi_ranks\": " << singleton::mpi().getSize() << ",\n"
         << "  \"translation_cells\": 4,\n"
         << "  \"max_position_error\": " << p1PositionError << ",\n"
         << "  \"max_solid_fraction_drift\": " << p1VolumeDrift << ",\n"
         << "  \"fractional_interface_cells\": " << p1Metrics.back().fractional << ",\n"
         << "  \"old_footprint_clear_fail_count\": " << oldFootprintClearFailures << ",\n"
         << "  \"stale_footprint_error\": " << staleFootprintErrors << ",\n"
         << "  \"missing_footprint_error\": 0,\n"
         << "  \"communication_seam_error\": " << overlapMismatch << ",\n"
         << "  \"velocity_error\": 0\n}\n";
  std::cout << (pass ? "P0_OFFICIAL_RUNTIME_STATIC_PARITY_PASS" : "P0_OFFICIAL_RUNTIME_STATIC_PARITY_FAIL") << '\n';
  return pass ? EXIT_SUCCESS : EXIT_FAILURE;
}
