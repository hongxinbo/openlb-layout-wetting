#!/bin/sh
# Diagnostic build of unchanged official source; not an equilibrium benchmark.
set -eu
[ "$#" -eq 1 ] || { echo "usage: $0 NEW_EXTERNAL_OUTPUT_DIRECTORY" >&2; exit 2; }
out=$1
[ ! -e "$out" ] || { echo "refusing overwrite" >&2; exit 2; }
root=${OPENLB_ROOT:-"$HOME/Documents/openlb"}
mkdir -p "$(dirname "$out")"
mkdir "$out"
out=$(cd "$out" && pwd)
python3 - "$root" "$out" <<'PYTHON'
import hashlib,json,pathlib,shlex,subprocess,sys,time
root,out=map(pathlib.Path,sys.argv[1:])
source=root/'examples/multiComponent/contactAngle3d/contactAngle3d.cpp'
commit=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True).strip()
cmd=['mpic++','-O0','-g','-fsanitize=address','-fno-omit-frame-pointer','-std=c++20','-DPARALLEL_MODE_MPI','-DPLATFORM_CPU_SISD','-DOLB_VERSION="'+commit+'"','-I/opt/homebrew/include','-I'+str(root/'src'),str(source),'-L'+str(root/'build/lib'),'-lolbcore','-L/opt/homebrew/lib','-lz','-ltinyxml2','-pthread','-o',str(out/'contactAngle3d_asan')]
m=dict(purpose='memory diagnostic only, no physics substitutions',openlb_commit=commit,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),build_command=shlex.join(cmd))
start=time.monotonic()
with (out/'build.log').open('w') as log:
    built=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
m.update(build_exit_status=built.returncode,build_runtime_s=time.monotonic()-start)
if built.returncode==0:
    cmd=[str(out/'contactAngle3d_asan'),'--MAX_LATTICE_T','0']
    m['run_command']=shlex.join(cmd); start=time.monotonic()
    with (out/'run.log').open('w') as log:
        run=subprocess.run(cmd,cwd=out,stdout=log,stderr=subprocess.STDOUT)
    m.update(run_exit_status=run.returncode,run_runtime_s=time.monotonic()-start)
(out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
sys.exit(built.returncode or m['run_exit_status'])
PYTHON
