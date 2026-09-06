#include <olb.h>
using namespace olb;
using namespace olb::descriptors;
using D = D3Q19<STATISTIC>;
// API-contract test only: no collide/stream, no droplet simulation.
// The optional scalar probe intentionally repeats the official unsafe call.
int main(int argc,char**argv) {
 initialize(&argc,&argv);
 IndicatorCuboid3D<double> box({4.,4.,4.},{0.,0.,0.});
 Mesh<double,3> mesh(box,1.,1);
 mesh.setOverlap(3);
 SuperLattice<double,D> lattice(mesh);
 SuperLatticeField3D<double,D,STATISTIC> phi(lattice);
 AnalyticalFfromSuperF3D<double,double> interpol(phi,true,1);
 double output[2]={123.,456.}; double pos[3]={2.,2.,2.};
 bool ok=interpol(output,pos);
 if (argc > 1 && std::string(argv[1]) == "--scalar-probe") {
   double scalar = 123.;
   interpol(&scalar,pos);
   std::cout << "SCALAR_PROBE value=" << scalar << std::endl;
 }
 std::cout << "BUFFER_PROBE target_dim=" << phi.getTargetDim() << " success=" << ok << " first=" << output[0] << " second_before=456 second_after=" << output[1] << std::endl;
 return !(ok && phi.getTargetDim()==2 && output[1]==0.);
}
