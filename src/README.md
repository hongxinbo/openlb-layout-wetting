# 源代码路线

- `common/`：单位转换、参数检查、公共相场配置和指标输出。
- `ec1xt240_straight2d/`：首个二维显式狭缝验证器。
- `vertical_squeeze_3d/`：当前3-D API编译审计与后续竖直挤压求解器边界。
- `ec1xt240_unit3d/`：通过最小双沟槽3-D流动门之后的EC1XT240代表单元。
- `sim_h_unit3d/`：后续回字形代表单元。

旧二维求解器保留为 `PRELIMINARY_REDUCED_MODEL`。当前3-D几何已实现；流动求解器
因本机OpenLB 1.9的3-D multiphase inlet/outlet实现被注释而处于HOLD。
