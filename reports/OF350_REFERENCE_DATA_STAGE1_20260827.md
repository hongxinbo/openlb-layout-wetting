# OF350 numerical regression reference — Stage 1 report

## Status

`OF350_REFERENCE_DATA_PASS`

这是成功 OpenFOAM 350 的**数值回归参考数据**构建成功，不是实验物理验证，也不放行
OpenLB350 或 EC1XT240 三维显式模型。下一门仍为
`OF350_TO_OPENLB_MODEL_MAPPING_REVIEW`。

## Actual work completed

- 用 YAML 驱动的只读源核验器重新检查 OF350，27/27 项通过，并记录输入源文件
  SHA-256；
- 从真实 `0.05` 至 `1.00 s` 的20个结果目录读取八个字段：`alpha.liquid`、`p`、
  `U`、`rho`、`T`、`cellDisplacement`、`alphaPhi.liquid` 和 `phi`；
- 冻结20条全域、320条区域（16区×20）与120条边界（6 patch×20）宏观 QoI；
- 写入每个输入场、源配置、提取器和派生输出的 SHA-256，并将同一提取重跑到临时
  新目录；6个输出哈希完全一致；
- 在任何 OpenLB 输出出现前冻结跨求解器 QoI 定义与容差治理规则。

## Extracted reference summary

| Item | Result |
| --- | --- |
| Time states | 20, 0.05–1.00 s (0.05 s spacing) |
| Cells / regions / patches | 157500 / 16 / 6 |
| Global liquid volume | 8.93594e-13 to 1.19196e-12 m3 |
| Global mean pressure | 100072.97 to 454217.96 Pa absolute |
| Gas-dominant mean pressure | 100033.10 to 305213.27 Pa |
| Gas-dominant mean density | 1.18671 to 3.61893 kg/m3 |
| EC1XT240 final filling | 0.689823 volume-weighted liquid fraction |
| EC1XT240 final mean pressure / speed | 328477.12 Pa / 3.76396e-4 m/s |
| EC1XT240 final equivalent layer | 6.50135e-8 m |

## OF350 self-consistency audit

- 所有20个时刻的八个所需字段可读；无缺失或解析损坏状态。
- 16个 source cellZone 互不重叠并精确覆盖157500个单元；EC1XT240 以
  `EC1XT240OASZone` 单独输出。
- 由混合密度反演的气相对 `p/(rho_g R T)-1` 的最大 RMS 为 `4.12662e-6`。气体
  压力与密度均有显著变化，所以 `perfectGas` 不能被静默替换为定密度气体。
- 20个快照上液相库存与六边界 `alphaPhi.liquid` 的梯形积分最大相对残差为1.52389%。
  这是时间采样不足下的诊断值，**不是**把开放边界库存变化称作质量守恒错误。
- 全域平均压力和速度相邻快照各出现1次趋势反转；20个输出点不足以归因于数值振荡，
  因此该项保留为诊断而非 PASS/FAIL。
- 从实际 `cellDisplacement` 重建的 EC1XT240 位移与名义五次曲线最大差为
  `1.38106e-11 m`；全部区域最大差是 K350 的 `1.69923e-9 m`。后续回归必须以
  冻结的实际位移字段为坐标，不能用名义函数抹平这个源模型差异。

## Frozen bundle and definitions

- `references/openfoam350/reference_stage1_20260827_v2/of350_reference_global.csv`
- `references/openfoam350/reference_stage1_20260827_v2/of350_reference_regions.csv`
- `references/openfoam350/reference_stage1_20260827_v2/of350_reference_boundaries.csv`
- `references/openfoam350/reference_stage1_20260827_v2/of350_reference_metadata.json`
- `references/openfoam350/reference_stage1_20260827_v2/of350_reference_summary.json`
- `references/openfoam350/reference_stage1_20260827_v2/of350_reference_input_sha256.json`
- `references/openfoam350/reference_stage1_20260827_v2/manifest.json`

`of350_reference_metadata.json` 明确记录了 SI 单位、体积/液相/气相加权规则、绝对
压力基准、速度定义、区域面积、通量符号，以及“推断气相体积通量”不是独立气相质量
通量的限制。

## Remaining UNKNOWNs

- OpenLB 是否有与 OF350 `perfectGas` 可接受的等价 EOS 或经验证储气近似；
- 三维移动等效层到 OpenLB 深度平均守恒方程的可验证映射；
- VOF 到 OpenLB 两相界面的映射与所需新增数值参数；
- OpenLB 真实时间映射、成本和收敛性；
- 所有跨求解器数值容差；它们均为 `TOLERANCE_PENDING_JUSTIFICATION`，尚未也不会
  依据任何 OpenLB 结果回调。

## Next action

只进行 `OF350 → OpenLB350` 模型映射矩阵审查和 R1 组件测试设计；不开始 EC1XT240
3D 显式几何、不扫描其他13个版图、不修改 OpenLB 源码。
