#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "usage: $0 OUTPUT_DIRECTORY" >&2
    exit 2
fi

output_dir=$1
if [ -e "$output_dir" ]; then
    echo "refusing to overwrite existing output: $output_dir" >&2
    exit 2
fi

openlb_root=${OPENLB_ROOT:-/Users/hongxinbo/Documents/openlb}
example_dir="$openlb_root/examples/multiComponent/contactAngle3d"
executable="$example_dir/contactAngle3d"
if [ ! -x "$executable" ]; then
    echo "missing executable; build the unmodified official example first: $example_dir" >&2
    exit 2
fi

# One targeted refinement of run3. The physical 28 um component droplet is held
# fixed while D increases from 28 to 48 cells, giving dx=28/48 um. Interface
# width increases from 4 to 7 cells to preserve W/D within 2.1%.
domain='[88 66 88]'
diameter=48
interface_width=7
steps=10000
vtk_interval=1000
stat_interval=500
phys_char_length=0.000028
kinematic_viscosity=6.622516556e-7
density_factor=1510
theta=60
surface_tension=0.01

mkdir -p "$output_dir"
manifest="$output_dir/run_manifest.txt"
{
    echo "case=prepress_droplet_component_retry_d48"
    echo "openlb_root=$openlb_root"
    echo "openlb_version=$(git -C "$openlb_root" describe --always --tags)"
    echo "openlb_commit=$(git -C "$openlb_root" rev-parse HEAD)"
    echo "executable=$executable"
    echo "domain_lattice=$domain"
    echo "droplet_diameter_lattice=$diameter"
    echo "interface_width_lattice=$interface_width"
    echo "max_steps=$steps"
    echo "vtk_interval=$vtk_interval"
    echo "theta_deg=$theta"
    echo "phys_char_length_m=$phys_char_length"
    echo "dx_m=5.833333333333333e-7"
    echo "logical_cells=511104"
    echo "population_only_memory_estimate_bytes=155375616"
    echo "working_memory_estimate_bytes_at_400_per_cell=204441600"
    echo "command=$executable --DOMAIN_EXTENT '$domain' --RESOLUTION $diameter --INTERFACE_WIDTH $interface_width --MAX_LATTICE_T $steps --LATTICE_VTK_ITER_T $vtk_interval --LATTICE_STAT_ITER_T $stat_interval --PHYS_CHAR_LENGTH $phys_char_length --NU_LIQUID $kinematic_viscosity --C_RHO $density_factor --THETA $theta --SURFACE_TENSION $surface_tension"
} > "$manifest"

start_epoch=$(date +%s)
set +e
(
    cd "$output_dir"
    "$executable" \
        --DOMAIN_EXTENT "$domain" \
        --RESOLUTION "$diameter" \
        --INTERFACE_WIDTH "$interface_width" \
        --MAX_LATTICE_T "$steps" \
        --LATTICE_VTK_ITER_T "$vtk_interval" \
        --LATTICE_STAT_ITER_T "$stat_interval" \
        --PHYS_CHAR_LENGTH "$phys_char_length" \
        --NU_LIQUID "$kinematic_viscosity" \
        --C_RHO "$density_factor" \
        --THETA "$theta" \
        --SURFACE_TENSION "$surface_tension" \
        > run.log 2>&1
)
exit_code=$?
set -e
end_epoch=$(date +%s)
{
    echo "exit_code=$exit_code"
    echo "wall_time_s=$((end_epoch-start_epoch))"
} >> "$manifest"
exit "$exit_code"
