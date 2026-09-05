# OpenLB Layout Wetting

这是研究14个OAS微/纳米版图中液体浸润与压力挤入过程的长期Git项目。

当前物理堆叠已更正为：上方图案化模具、空气间隙、平基底上的液滴、下方平基底。
本阶段仅做固定模具预压松弛，x/y 周期，无横向入口、压差或排气口；模具下压和困气
压缩留给后续。旧二维横向模型只作为 `PRELIMINARY_REDUCED_MODEL` 保留。

## 当前状态

- 项目骨架：已建立。
- 14个OAS输入：已复制并记录SHA-256。
- EC1XT240初步几何审计：已记录。
- OpenFOAM 350参数来源审计：已建立初稿。
- 3-D API 审计：`OPENLB_3D_API_AUDIT_HOLD`；D3Q19、保守相场、Liang 和
  3-D wetting kernel 存在，但本机版本的 3-D multiphase inlet/outlet 源码被注释。
- 3-D 双沟槽几何：`3D_GEOMETRY_PASS`；20 nm、30 x 12 x 5050、1,818,000 cells，
  已由 ParaView 6.1.1 读取并生成 x-y/x-z/y-z 切片。
- 固定几何流动：`3D_VERTICAL_INTRUSION_HOLD_NOT_RUN_API_LIMITATION`。
- 移动模板与真实 OAS：HOLD/NOT_RUN；没有用封闭不可压气体、横向入口或删除格子层绕过。
- 旧 2-D baseline 和 production study 全部保留，不能作为最终压印物理结果。
- OF350 液滴审计：对齐阵列为 15 x 9、半径 52 um、节距 350 um；冻结源中未找到
  交错阵列坐标，后者 HOLD。
- 预压多尺度审计：20 nm 统一网格约 1.84e12 cells / 559--735 TB，明确采用宏观液滴
  与微观 OAS 分离。
- 3-D 液滴组件：`PREPRESS_DROPLET_COMPONENT_FAIL`；run3 修正复核和唯一一次
  48格直径、10,000步加密验证均未通过物理流体相场下界，后者也未通过角度/稳态门。
  结果见 `results/summaries/`，物理周期单元未继续运行。
- 上模具 OAS 方向预览：ParaView 读取通过；层极性与真实初始间隙未冻结，保持
  `TOP_MOLD_OAS_GEOMETRY_HOLD`。

## 先读这些文件

1. `AGENTS.md`：项目约束和科研结论边界。
2. `docs/PROJECT_SCOPE.md`：研究问题与阶段。
3. `docs/GEOMETRY_AUDIT.md`：版图解释。
4. `docs/PHYSICS_SPEC.md`：第一版物理模型。
5. `docs/PARAMETER_PROVENANCE.md`：参数来源和可用性。
6. `docs/VALIDATION_PLAN.md`：进入正式模拟前的验证门。
7. `docs/OPENLB_3D_API_AUDIT.md`：本机 1.9 的 3-D API 证据与限制。
8. `docs/3D_GEOMETRY_AUDIT.md`：显式 z 几何、连通性和 ParaView 门。

## 本机依赖

- OpenLB：通过 `OPENLB_ROOT` 指定，默认 `$HOME/Documents/openlb`。
- 当前核对版本：`1.9.0-19-g3dedbdd2`。
- 参考例程：
  - `examples/multiComponent/contactAngle3d/contactAngle3d.cpp`
  - `examples/multiComponent/rayleighTaylor3d/rayleighTaylor3d.cpp`
  - `examples/fsi/taylorCouette3d/taylorCouette3d.cpp`

不要直接修改OpenLB源码；研究案例留在本仓库。

## 数据位置

大型原始资料和结果放在：

```text
$HOME/ResearchData/openlb-layout-wetting/
```

复制 `config/local_paths.example.yaml` 为 `config/local_paths.yaml` 后填写本机路径。后者被Git忽略。

## 路线

```text
OpenLB 3-D API审计
  -> 3-D几何方向审计
  -> x/y周期的3-D静置液滴润湿组件验证
  -> 宏观预压周期液滴模型
  -> 移动图案化上模具与困气模型
  -> 微观OAS挤压/填充模型
  -> 版图比较
```

## Git规则

`main` 只保留通过相应验证门的状态。开发分支按任务命名，例如：

```text
feature/geometry-audit
feature/single-phase-slit
feature/ec1xt240-2d
feature/ec1xt240-3d
```

时间由Git提交记录，不建立日期命名副本。
