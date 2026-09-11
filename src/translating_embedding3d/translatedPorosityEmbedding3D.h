#ifndef PROJECT_TRANSLATED_POROSITY_EMBEDDING_3D_H
#define PROJECT_TRANSLATED_POROSITY_EMBEDDING_3D_H

#include <olb.h>

#include <cmath>
#include <vector>

// Project-local, full-domain re-embedding for a rigid reference porosity
// raster.  It deliberately writes only the two fields read by HLBM; materials
// and populations are not touched.
namespace project::hlbm {

// A dedicated stage avoids SuperLattice::_communicationNeeded, which direct
// BlockLattice field writes do not update.
struct TranslatingEmbeddingCommunication { };

template <typename T>
struct ReferenceCuboidPorosity {
  olb::Vector<T,3> lower;
  olb::Vector<T,3> upper;
  T deltaX;
  olb::Vector<std::size_t,3> extent;
  std::vector<T> values;

  T at(const olb::Vector<int,3>& r) const {
    if (r[0] < 0 || r[1] < 0 || r[2] < 0
        || r[0] >= int(extent[0]) || r[1] >= int(extent[1]) || r[2] >= int(extent[2])) {
      return T{1};
    }
    return values[(r[0]*extent[1] + r[1])*extent[2] + r[2]];
  }
};

template <typename T, typename DESCRIPTOR>
class TranslatingPorosityEmbedding3D {
public:
  TranslatingPorosityEmbedding3D(const ReferenceCuboidPorosity<T>& reference)
    : _reference(reference) { }

  template <typename LATTICE>
  static void configureCommunication(LATTICE& lattice) {
    auto& communicator = lattice.getCommunicator(TranslatingEmbeddingCommunication{});
    communicator.template requestField<olb::descriptors::POROSITY>();
    communicator.template requestField<olb::descriptors::VELOCITY>();
    communicator.requestOverlap(1);
    communicator.exchangeRequests();
  }

  // This is the installed ReferenceLatticePorosityF sampling rule evaluated
  // after x -> x - translation.  Translation changes the footprint; velocity
  // is separately prescribed and is lattice-valued, as required by HLBM.
  T porosity(const olb::Vector<T,3>& physR,
             const olb::Vector<T,3>& translation) const {
    const auto local = physR - translation;
    if (!(_reference.lower + _reference.deltaX < local
          && local < _reference.upper - _reference.deltaX)) {
      return T{1};
    }
    olb::Vector<int,3> discreteR;
    for (int i=0; i<3; ++i) {
      discreteR[i] = int(std::round((local[i] - _reference.lower[i]) / _reference.deltaX));
    }
    T value = _reference.at(discreteR);
    for (int iPop=1; iPop<DESCRIPTOR::q; ++iPop) {
      olb::Vector<int,3> neighbor = discreteR;
      for (int i=0; i<3; ++i) {
        neighbor[i] += olb::descriptors::c<DESCRIPTOR>(iPop)[i];
      }
      value += _reference.at(neighbor);
    }
    return value / T(DESCRIPTOR::q);
  }

  template <typename LATTICE>
  void rewrite(LATTICE& lattice,
               const olb::Vector<T,3>& translation,
               const olb::Vector<T,3>& velocity,
               bool explicitCommunication=true) const {
    const auto& load = lattice.getLoadBalancer();
    for (int iC=0; iC<load.size(); ++iC) {
      auto& block = lattice.getBlock(iC);
      block.forCoreSpatialLocations([&](olb::LatticeR<3> loc) {
        const auto latticeR = loc.withPrefix(load.glob(iC));
        const auto physR = lattice.getCuboidDecomposition().getPhysR(latticeR);
        const T epsilon = porosity(physR, translation);
        block.get(loc).template setField<olb::descriptors::POROSITY>(epsilon);
        block.get(loc).template setField<olb::descriptors::VELOCITY>(
          epsilon < T{1} ? velocity : olb::Vector<T,3>{});
      });
    }
    lattice.template setProcessingContext<olb::Array<olb::descriptors::POROSITY>>(
      olb::ProcessingContext::Simulation);
    lattice.template setProcessingContext<olb::Array<olb::descriptors::VELOCITY>>(
      olb::ProcessingContext::Simulation);
    if (explicitCommunication) {
      lattice.getCommunicator(TranslatingEmbeddingCommunication{}).communicate();
    } else {
      // Diagnostic legacy behavior: guarded by _communicationNeeded.
      lattice.communicate();
    }
  }

private:
  ReferenceCuboidPorosity<T> _reference;
};

} // namespace project::hlbm

#endif
