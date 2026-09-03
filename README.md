# OpenLB Layout Wetting

这是研究14个OAS微/纳米版图中液体浸润与压力挤入过程的长期Git项目。

首个目标是 `SIM-EC1XT240.OAS` 的真实三维竖直挤压/沟槽灌注：模板沿 -z
下压上方液膜，液体从 z=0 上方进入固定 100 um 沟槽。旧二维横向模型只作为
`PRELIMINARY_REDUCED_MODEL` 保留。

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
  -> 显式双沟槽3-D几何/ParaView
  -> 固定几何自上而下排气基线
  -> 移动模板组件
  -> 最小3-D squeeze filling
  -> EC1XT240真实OAS三维代表单元
  -> SIM-H和其他版图
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
