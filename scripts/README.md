# 自动化脚本

脚本不得依赖硬编码的个人绝对路径，应读取参数、环境变量或
`config/local_paths.yaml`。

- `generate_vertical_squeeze_3d_geometry.py`：从版本化配置生成显式3-D VTI、
  连通性检查和JSON审计。
- `render_vertical_squeeze_3d_geometry.py`：用安装的ParaView读取VTI并写出三张
  切片及PNG；必须由`pvpython`运行。
- `run_vertical_squeeze_3d_geometry.sh`：依次运行上述生成和ParaView审计；可用
  `PVPYTHON`和两个输出目录环境变量覆盖本机路径。
## XY0 single-phase resistance

`run_xy0_poiseuille_validation.py` builds the project-local 3-D slit solver,
runs the frozen four-force/three-grid matrix into a new output directory, and
writes compact tables plus a JSON gate summary. It follows the installed
OpenLB `poiseuille3d` force path and intentionally does not produce tracked
VTK fields. Use `--finalize-existing` only to summarize an interrupted run
whose seven per-case JSON files already completed.
