# 自动化脚本

脚本不得依赖硬编码的个人绝对路径，应读取参数、环境变量或
`config/local_paths.yaml`。

- `generate_vertical_squeeze_3d_geometry.py`：从版本化配置生成显式3-D VTI、
  连通性检查和JSON审计。
- `render_vertical_squeeze_3d_geometry.py`：用安装的ParaView读取VTI并写出三张
  切片及PNG；必须由`pvpython`运行。
- `run_vertical_squeeze_3d_geometry.sh`：依次运行上述生成和ParaView审计；可用
  `PVPYTHON`和两个输出目录环境变量覆盖本机路径。
