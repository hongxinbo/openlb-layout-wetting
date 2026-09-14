# 参数来源与采用状态

状态定义：

- `CONFIRMED`：用户或权威原始资料已确认，可进入基线；
- `OF350_TRANSFER_BASELINE`：成功OF350源例程的已核验转移输入；不是普适实测EC1材料性质；
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
| 液体名称 | Immersion Liquid 5095 | OF350_TRANSFER_BASELINE | OF350源例程；材料等价性可在后续细化 |
| 墙体材料 | null | UNKNOWN | 决定接触角和滑移 |
| 温度 | 293 K | OF350_TRANSFER_BASELINE | `0.org/T` |
| 接触角 | 60 deg, liquid-measured | LITERATURE_ASSUMPTION | 不是本项目实测；30/60/85/120 deg 敏感性 |
| 驱动方式 | top punch downward motion | REFERENCE / transferred schedule evidence | OF350 的 1 um、-0.935 um/1 s quintic 仅作首个数值组件参考，不是最终 EC1 轨迹 |
| 气体出口 | null | DEFERRED | 首周期单液体基线不含物理气体；后续两相阶段另行定义 |
| 理想狭缝渗透率 | 1.2e-15 m2 | DERIVED_START | `b^2/12`, `b=120 nm` |
| 理想逆渗透率 | 8.3e14 m-2 | DERIVED_START | `12/b^2` |
| XY0 狭缝液压间隙 | 10 um | NUMERICAL_COMPONENT_GEOMETRY | 固定几何 Poiseuille 验证；不是 EC1/OAS 尺寸 |
| XY0 密度与动力黏度 | 1510 kg/m3; 1e-3 Pa s | OF350_TRANSFER_BASELINE | 只用于单相数值组件的量纲一致性 |

## OF350转移基线

原始旧案例位于外部数据目录，不复制到Git。逻辑来源路径相对于该案例根目录。

| 参数 | 旧值 | 状态 | 原始文件 |
|---|---:|---|---|
| 液体标签 | Immersion Liquid 5095 | OF350_TRANSFER_BASELINE | `constant/physicalProperties.liquid` |
| 液体密度 | 1510 kg/m3 | OF350_TRANSFER_BASELINE | `constant/physicalProperties.liquid` |
| 液体动力黏度 | 1e-3 Pa s | OF350_TRANSFER_BASELINE | `constant/physicalProperties.liquid` |
| 空气动力黏度 | 1.5e-5 Pa s | OF350_TRANSFER_BASELINE | `constant/physicalProperties.air` |
| 空气状态方程 | perfectGas, molWeight 28.9 | OF350_TRANSFER_BASELINE | `constant/physicalProperties.air`；reduced baseline不严格复现 |
| 表面张力 | 0.0309 N/m | OF350_TRANSFER_BASELINE | `constant/phaseProperties` |
| 接触角 | 未找到 | UNKNOWN | 旧案例中未发现可采用的真实墙面角 |
| EC1XT240 Darcy d | `(5e16,0,0)` | REFERENCE_ONLY | `constant/fvModels` |
| Forchheimer f | `(0,0,0)` | REFERENCE_ONLY | `constant/fvModels` |
| 液滴半径 | 52 um | REFERENCE_ONLY | `system/setFieldsDict` |
| 旧计算层厚度 | 1 um | REFERENCE_ONLY | `system/blockMeshDict` |
| 初始上方液膜 | 1.0 um | OF350_TRANSFER_BASELINE | `system/blockMeshDict`；不是沟槽深度 |
| EC1XT240压板位移 | -0.935 um / 1 s quintic | REFERENCE_ONLY | OF350 转移日程；仅在公式通过后作为命名的数值组件参考，不是最终 EC1 轨迹 |

这些转移值由成功OF350源例程支撑，但仍不能被表述为普适、独立实测的EC1材料性质。旧网格、运动和阻力不能代表当前100 um显式沟槽；100 um沟槽固定，移动的是上方液膜/间隙。

## 接触角文献锚点

| 项目 | 值 | 状态 | 来源/说明 |
|---|---:|---|---|
| J-FIL resist/template | <30 deg | LITERATURE_REFERENCE | Microsystems & Nanoengineering (2017), DOI `10.1038/micronano.2017.75` |
| PAK-01/release-coated HSQ | about 66 deg | LITERATURE_REFERENCE | Microelectronic Engineering 86 (2009), DOI `10.1016/j.mee.2008.12.085` |
| substrate/resist; stamp/resist | 30 deg; 85 deg | LITERATURE_REFERENCE | Micro & Nano Letters (2019), DOI `10.1049/mnl.2018.5324` |
| reduced-baseline angle | 60 deg through liquid | LITERATURE_ASSUMPTION | plausible baseline, explicitly not a project measurement |

## OpenLB例程参数

`gasStorage2d` 和 `bubbleChannel2d` 的密度、黏度、压力、接触角、界面宽度及分辨率均为例程输入，状态统一为 `REFERENCE_ONLY`。它们用于核对API、边界和稳定化路径，不进入 `config/baseline.yaml`。

## 进入求解器前必须补齐

1. 如需将转移值提升为项目实测值，补充液体/温度/墙材的独立证据；
2. reduced vented gas 到 local perfectGas 的映射（本阶段不要求）；
3. 如启用额外Darcy项，提供标定方法和误差；显式OAS墙的本阶段不得叠加OF350 Darcy。
