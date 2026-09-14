#!/bin/sh
set -eu
if [ "$#" -lt 1 ]; then
  echo "usage: $0 NEW_EXTERNAL_OUTPUT_DIRECTORY [official CLI overrides...]" >&2
  exit 2
fi
out=$1
shift
[ ! -e "$out" ] || { echo "refusing overwrite: $out" >&2; exit 2; }
root=${OPENLB_ROOT:-"$HOME/Documents/openlb"}
exe="$root/examples/multiComponent/contactAngle3d/contactAngle3d"
[ -x "$exe" ] || exit 2
mkdir -p "$(dirname "$out")"
mkdir "$out"
out=$(cd "$out" && pwd)
python3 - "$root" "$exe" "$out" "$@" <<'PYTHON'
import hashlib,json,os,pathlib,shlex,subprocess,sys,time
root,exe,out,*overrides=sys.argv[1:]
p=pathlib.Path(out)
def sha(f): return hashlib.sha256(pathlib.Path(f).read_bytes()).hexdigest()
m=dict(openlb_commit=subprocess.check_output(['git','-C',root,'rev-parse','HEAD'],text=True).strip(),executable=exe,executable_sha256=sha(exe),source_sha256=sha(exe+'.cpp'),explicit_overrides=overrides,command=shlex.join([exe,*overrides]),cwd=out)
m['compiler']=subprocess.check_output(['mpic++','--version'],text=True).splitlines()[0]
m['build_config_sha256']=sha(str(pathlib.Path(root)/'config.mk'))
m['core_library_sha256']=sha(str(pathlib.Path(root)/'build/lib/libolbcore.a'))
m['tracked_dependency_diff']=subprocess.check_output(['git','-C',root,'diff','HEAD','--', 'src','examples/multiComponent/contactAngle3d'],text=True)
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
if m['tracked_dependency_diff']:
 raise SystemExit('refusing official benchmark with modified tracked dependency source')
t=time.monotonic()
with (p/'run.log').open('w') as log:
 r=subprocess.run([exe,*overrides],cwd=out,stdout=log,stderr=subprocess.STDOUT)
m.update(exit_status=r.returncode,runtime_s=time.monotonic()-t)
(p/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
sys.exit(r.returncode)
PYTHON
