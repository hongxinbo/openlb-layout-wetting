# 参数来源与采用状态

状态定义：

- `CONFIRMED`：用户或权威原始资料已确认，可进入基线；
- `CANDIDATE`：旧案例候选，必须确认适用条件；
- `REFERENCE_ONLY`：只用于比较或代码组织；
- `UNKNOWN`：当前缺少依据；
- `DERIVED_START`：由理想理论推导的校准起点，不是最终实测参数。

| 参数 | 当前值 | 状态 | 来源/说明 |
|---|---:|---|---|
| 粉红区域 | 固体墙 | CONFIRMED | 用户确认 |
| 白色区域 | 流体空间 | CONFIRMED | 用户确认 |
| EC1XT240常规白槽宽 | 120 nm | CONFIRMED_ASSUMPTION | OAS图元审计与用户颜色解释 |
| EC1XT240墙宽 | 120 nm | CONFIRMED_ASSUMPTION | OAS图元审计 |
| EC1XT240周期 | 240 nm | CONFIRMED_ASSUMPTION | OAS图元审计 |
| 沟槽深度 | 100 um | CONFIRMED | 用户确认；不是OAS z尺寸 |
| 液体名称 | null | UNKNOWN | 需实验/老师确认 |
| 墙体材料 | null | UNKNOWN | 决定接触角和滑移 |
| 温度 | null | UNKNOWN | 决定物性 |
| 接触角 | null | UNKNOWN | 需真实液体-墙材数据 |
| 驱动方式 | null | UNKNOWN | 压力、液滴或移动压板待确认 |
| 气体出口 | null | UNKNOWN | 排气与封闭必须分支 |
| 理想狭缝渗透率 | 1.2e-15 m2 | DERIVED_START | `b^2/12`, `b=120 nm` |
| 理想逆渗透率 | 8.3e14 m-2 | DERIVED_START | `12/b^2` |

## 旧OpenFOAM 350候选值

原始旧案例位于外部数据目录，不复制到Git。逻辑来源路径相对于该案例根目录。

| 参数 | 旧值 | 状态 | 原始文件 |
|---|---:|---|---|
| 液体标签 | Immersion Liquid 5095 | CANDIDATE | `constant/physicalProperties.liquid` |
| 液体密度 | 1510 kg/m3 | CANDIDATE | `constant/physicalProperties.liquid` |
| 液体动力黏度 | 1e-3 Pa s | CANDIDATE | `constant/physicalProperties.liquid` |
| 空气动力黏度 | 1.5e-5 Pa s | CANDIDATE | `constant/physicalProperties.air` |
| 表面张力 | 0.0309 N/m | CANDIDATE | `constant/phaseProperties` |
| 接触角 | 未找到 | UNKNOWN | 旧案例中未发现可采用的真实墙面角 |
| EC1XT240 Darcy d | `(5e16,0,0)` | REFERENCE_ONLY | `constant/fvModels` |
| Forchheimer f | `(0,0,0)` | REFERENCE_ONLY | `constant/fvModels` |
| 液滴半径 | 52 um | REFERENCE_ONLY | `system/setFieldsDict` |
| 旧计算层厚度 | 1 um | REFERENCE_ONLY | `system/blockMeshDict` |
| EC1XT240压板位移 | -0.935 um / 1 s | REFERENCE_ONLY | `system/topoSetDict` |

这些参数只有在液体、温度、墙材和工艺完全相同时才可能复用。旧网格、运动和阻力不能代表当前100 um显式沟槽。

## OpenLB例程参数

`gasStorage2d` 和 `bubbleChannel2d` 的密度、黏度、压力、接触角、界面宽度及分辨率均为例程输入，状态统一为 `REFERENCE_ONLY`。它们用于核对API、边界和稳定化路径，不进入 `config/baseline.yaml`。

## 进入求解器前必须补齐

1. 液体名称与温度；
2. 液体密度、动力黏度、表面张力；
3. 气体初始绝对压力和物性；
4. 墙体材料及液相内接触角；
5. 驱动方式与时间历史；
6. 气体出口状态；
7. 如启用额外Darcy项，提供标定方法和误差。
