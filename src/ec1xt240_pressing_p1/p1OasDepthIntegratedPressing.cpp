// P1A: real-OAS depth-integrated pressing transport.
//
// This applies the P0 conservative two-phase piston rule to the actual
// SIM-EC1XT240 OAS raster. It is deliberately a finite-volume sidecar test,
// not yet an OpenLB collision/coupling implementation. q_l=h*alpha_l and
// q_g=h*(1-alpha_l) are moved to the real right-edge openings along a
// shortest-path flow tree. No alpha rescaling, clipping, or mass deletion is
// used. It establishes that a candidate moving-depth transport remains bounded
// and conservative in the actual plan-view geometry. The 100-to-80 um history
// is a numerical algorithm test, not a confirmed EC1XT240 physical process.

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <queue>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using T = double;
constexpr int kSteps = 30000;
constexpr T kH0 = 100.e-6;
constexpr T kHFinal = 80.e-6;

T smoothstep(T s) { return s*s*s*(10.-15.*s+6.*s*s); }

std::string nextToken(std::istream& input)
{
  std::string token;
  char c{};
  while (input.get(c)) {
    if (c == '#') {
      input.ignore(std::numeric_limits<std::streamsize>::max(), '\n');
    } else if (!std::isspace(static_cast<unsigned char>(c))) {
      token.push_back(c);
      break;
    }
  }
  while (input.get(c)) {
    if (std::isspace(static_cast<unsigned char>(c))) break;
    token.push_back(c);
  }
  if (token.empty()) throw std::runtime_error("truncated PGM header");
  return token;
}

struct Raster {
  int nx{};
  int ny{};
  std::vector<unsigned char> pixels;

  [[nodiscard]] int index(int x, int y) const { return x+nx*y; }
  [[nodiscard]] bool inside(int x, int y) const
  { return x >= 0 && x < nx && y >= 0 && y < ny; }
  [[nodiscard]] bool fluid(int i) const { return pixels.at(i) == 0; }
};

Raster readPgm(const std::string& path)
{
  std::ifstream input(path,std::ios::binary);
  if (!input) throw std::runtime_error("cannot open OAS mask: "+path);
  if (nextToken(input) != "P5") throw std::runtime_error("expected P5 mask");
  Raster raster;
  raster.nx=std::stoi(nextToken(input));
  raster.ny=std::stoi(nextToken(input));
  const int maximum=std::stoi(nextToken(input));
  if (raster.nx <= 0 || raster.ny <= 0 || maximum != 255) {
    throw std::runtime_error("invalid OAS PGM dimensions or range");
  }
  raster.pixels.resize(static_cast<std::size_t>(raster.nx)*raster.ny);
  input.read(reinterpret_cast<char*>(raster.pixels.data()),
             static_cast<std::streamsize>(raster.pixels.size()));
  if (input.gcount() != static_cast<std::streamsize>(raster.pixels.size())) {
    throw std::runtime_error("truncated OAS PGM pixel payload");
  }
  return raster;
}

struct FlowTree {
  std::vector<int> parent;
  std::vector<std::vector<int>> children;
  std::vector<int> postOrder;
  int fluidCells{};
  int rightOpenings{};
  int unreachableFluid{};
  int maximumDistance{};
};

FlowTree buildRightOutletTree(const Raster& raster)
{
  const int cells=raster.nx*raster.ny;
  std::vector<int> distance(cells,-1);
  std::queue<int> frontier;
  FlowTree tree;
  tree.parent.assign(cells,-2);
  for (int y=0; y<raster.ny; ++y) {
    const int outlet=raster.index(raster.nx-1,y);
    if (raster.fluid(outlet)) {
      distance[outlet]=0;
      tree.parent[outlet]=-1;
      frontier.push(outlet);
      ++tree.rightOpenings;
    }
  }
  if (tree.rightOpenings == 0) throw std::runtime_error("OAS crop has no right-edge fluid opening");

  while (!frontier.empty()) {
    const int current=frontier.front();
    frontier.pop();
    const int x=current%raster.nx;
    const int y=current/raster.nx;
    for (const auto [nx,ny] : {std::pair{x-1,y},std::pair{x+1,y},
                                std::pair{x,y-1},std::pair{x,y+1}}) {
      if (!raster.inside(nx,ny)) continue;
      const int neighbour=raster.index(nx,ny);
      if (!raster.fluid(neighbour) || distance[neighbour] >= 0) continue;
      distance[neighbour]=distance[current]+1;
      tree.parent[neighbour]=current;
      tree.maximumDistance=std::max(tree.maximumDistance,distance[neighbour]);
      frontier.push(neighbour);
    }
  }

  tree.children.resize(cells);
  for (int i=0; i<cells; ++i) {
    if (!raster.fluid(i)) continue;
    ++tree.fluidCells;
    if (distance[i] < 0) {
      ++tree.unreachableFluid;
      continue;
    }
    if (tree.parent[i] >= 0) tree.children[tree.parent[i]].push_back(i);
    tree.postOrder.push_back(i);
  }
  std::sort(tree.postOrder.begin(),tree.postOrder.end(),[&](int a,int b) {
    return distance[a] > distance[b];
  });
  return tree;
}

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
  T maxFaceCfl{};
  bool finite{true};
};

Outcome run(const Raster& raster,const FlowTree& tree)
{
  const int cells=raster.nx*raster.ny;
  std::vector<T> qLiquid(cells),qGas(cells),outgoing(cells);
  Outcome result;
  T h=kH0;
  T initialLiquid{};
  T initialGas{};
  int rightSamples{};
  for (int i=0; i<cells; ++i) {
    if (!raster.fluid(i)) continue;
    const int x=i%raster.nx;
    const T alpha=T(.5)*(T(1)-std::tanh((T(x)+T(.5)-T(.30)*raster.nx)/T(2)));
    qLiquid[i]=h*alpha;
    qGas[i]=h*(T(1)-alpha);
    initialLiquid+=qLiquid[i];
    initialGas+=qGas[i];
    result.initialLiquidCentroidX+=qLiquid[i]*(T(x)+T(.5));
    if (x >= raster.nx/2) {
      result.initialRightAlpha+=alpha;
      ++rightSamples;
    }
  }
  result.initialRightAlpha/=rightSamples;
  result.initialLiquidCentroidX/=initialLiquid;

  for (int step=0; step<kSteps; ++step) {
    const T hNew=kH0+(kHFinal-kH0)*smoothstep(T(step+1)/kSteps);
    const T removedPerCell=h-hNew;
    std::fill(outgoing.begin(),outgoing.end(),T{});
    for (const int i : tree.postOrder) {
      outgoing[i]=removedPerCell;
      for (const int child : tree.children[i]) outgoing[i]+=outgoing[child];
      result.maxFaceCfl=std::max(result.maxFaceCfl,outgoing[i]/h);
    }
    // Process leaves to outlets. A cell receives all child flux before its
    // mixture is sent onward, so both phases use exactly the same local face
    // fraction and q_l+q_g becomes hNew without alpha rescaling.
    for (const int i : tree.postOrder) {
      const T total=qLiquid[i]+qGas[i];
      const T liquidFlux=outgoing[i]*qLiquid[i]/total;
      const T gasFlux=outgoing[i]-liquidFlux;
      qLiquid[i]-=liquidFlux;
      qGas[i]-=gasFlux;
      const int parent=tree.parent[i];
      if (parent >= 0) {
        qLiquid[parent]+=liquidFlux;
        qGas[parent]+=gasFlux;
      } else {
        result.liquidOut+=liquidFlux;
        result.gasOut+=gasFlux;
      }
    }
    h=hNew;
  }

  T finalLiquid{};
  T finalGas{};
  for (int i=0; i<cells; ++i) {
    if (!raster.fluid(i)) continue;
    const int x=i%raster.nx;
    const T total=qLiquid[i]+qGas[i];
    const T alpha=qLiquid[i]/total;
    result.finite=result.finite && std::isfinite(qLiquid[i]) && std::isfinite(qGas[i]) && std::isfinite(alpha);
    result.minAlpha=std::min(result.minAlpha,alpha);
    result.maxAlpha=std::max(result.maxAlpha,alpha);
    result.closureError=std::max(result.closureError,std::abs(total-h));
    finalLiquid+=qLiquid[i];
    finalGas+=qGas[i];
    result.finalLiquidCentroidX+=qLiquid[i]*(T(x)+T(.5));
    if (x >= raster.nx/2) result.finalRightAlpha+=alpha;
  }
  result.finalRightAlpha/=rightSamples;
  result.finalLiquidCentroidX/=finalLiquid;
  result.liquidResidual=std::abs(finalLiquid-initialLiquid+result.liquidOut)/initialLiquid;
  result.gasResidual=std::abs(finalGas-initialGas+result.gasOut)/initialGas;
  return result;
}

void writeJson(const std::string& path,const std::string& mask,const Raster& raster,
               const FlowTree& tree,const Outcome& r,bool pass)
{
  std::ofstream output(path);
  if (!output) throw std::runtime_error("cannot write result: "+path);
  output<<std::setprecision(17)
    <<"{\n"
    <<"  \"test\": \"P1A_real_OAS_depth_integrated_transport\",\n"
    <<"  \"status\": \""<<(pass?"P1_OAS_DEPTH_TRANSPORT_PASS":"P1_OAS_DEPTH_TRANSPORT_HOLD")<<"\",\n"
    <<"  \"source_mask\": \""<<mask<<"\",\n"
    <<"  \"formulation\": \"finite-volume q_l=h*alpha_l and q_g=h*(1-alpha_l) routed through a real-OAS right-outlet flow tree; no alpha rescaling or clipping\",\n"
    <<"  \"scope\": \"P1A geometry and conservative transport evidence; not an OpenLB collision/coupling result\",\n"
    <<"  \"grid\": ["<<raster.nx<<", "<<raster.ny<<"],\n"
    <<"  \"fluid_cells\": "<<tree.fluidCells<<",\n"
    <<"  \"right_edge_openings\": "<<tree.rightOpenings<<",\n"
    <<"  \"unreachable_fluid_cells\": "<<tree.unreachableFluid<<",\n"
    <<"  \"maximum_outlet_path_cells\": "<<tree.maximumDistance<<",\n"
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
    <<"  \"max_face_cfl\": "<<r.maxFaceCfl<<",\n"
    <<"  \"finite\": "<<(r.finite?"true":"false")<<"\n"
    <<"}\n";
}
}

int main(int argc,char* argv[])
{
  if (argc != 3) {
    std::cerr<<"usage: "<<argv[0]<<" OAS_MASK.pgm OUTPUT.json\n";
    return EXIT_FAILURE;
  }
  try {
    const Raster raster=readPgm(argv[1]);
    const FlowTree tree=buildRightOutletTree(raster);
    const Outcome r=run(raster,tree);
    const bool pass=tree.unreachableFluid == 0 && r.finite
      && r.liquidResidual < 1e-12 && r.gasResidual < 1e-12 && r.closureError < 1e-12
      && r.minAlpha >= -1e-12 && r.maxAlpha <= 1.+1e-12
      && r.finalLiquidCentroidX > r.initialLiquidCentroidX+.1 && r.maxFaceCfl < .05;
    writeJson(argv[2],argv[1],raster,tree,r,pass);
    std::cout<<std::setprecision(17)
      <<(pass?"P1_OAS_DEPTH_TRANSPORT_PASS":"P1_OAS_DEPTH_TRANSPORT_HOLD")
      <<" liquid_residual="<<r.liquidResidual
      <<" gas_residual="<<r.gasResidual
      <<" liquid_centroid_displacement="<<r.finalLiquidCentroidX-r.initialLiquidCentroidX
      <<" phase=["<<r.minAlpha<<','<<r.maxAlpha<<']'
      <<" max_face_cfl="<<r.maxFaceCfl
      <<" unreachable_fluid="<<tree.unreachableFluid<<'\n';
    return pass?EXIT_SUCCESS:EXIT_FAILURE;
  } catch (const std::exception& error) {
    std::cerr<<"P1_OAS_DEPTH_TRANSPORT_HOLD: "<<error.what()<<'\n';
    return EXIT_FAILURE;
  }
}
