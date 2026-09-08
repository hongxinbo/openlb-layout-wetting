# OpenLB Layout Wetting

这是研究14个OAS微/纳米版图中液体浸润与压力挤入过程的长期Git项目。

当前活动门是首周期单液体自由表面/数值空隙与移动上模具的公式 API 审计。上方图案化
模具向下运动、下方为平基底、模具腔向下开口且深度固定为 100 um；本阶段不引入物理
空气、困气、宏观液滴、全尺寸 EC1 或版图比较。旧二维模型只作为
`PRELIMINARY_REDUCED_MODEL` 保留。

## 当前状态

- PR #6 官方 3-D 润湿基准：`CORRECTED_OFFICIAL_CONTACTANGLE3D_PASS`。在不改变
  官方求解器物理的前提下，项目本地修正了诊断缓冲区和顶部坐标；100 度 A0C 于
  24000 步收敛至 99.4454 度，独立圆拟合为 99.447840 度。详见
  `docs/CORRECTED_CONTACTANGLE3D_SOURCE_PARITY.md`、`results/summaries/` 和
  `results/tables/`。历史组件 FAIL 标签保持不变；参数隔离已通过，当前 NEXT 为
  `FIRST_PERIOD_SINGLE_PHASE_MOVING_PUNCH_BASELINE`，须先完成单相自由表面与
  移动固壁 API 审计。
- PR #6 参数隔离：`PROJECT_WETTING_PARAMETER_ISOLATION_PASS`。B1 的 60 度
  科学润湿门通过（其超出原运行预算单列为执行政策偏差）；冻结 phi≈0 液滴转换器后，
  B2 用 `sigma_LB=0.002073733333` 映射 0.0309 N/m，并于 101000 步收敛到
  61.7938 度。宏观周期单元、真实空气和压印案例均未启动。


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
  -> 首周期单液体自由表面/移动冲头公式审计
  -> 固定首周期几何与M0静态身份检查
  -> M1平壁移动与M2图案化首周期液体填充
  -> 空气/困气两相压印模型
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
