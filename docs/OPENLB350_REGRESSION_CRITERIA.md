# OpenLB350 跨求解器回归准则

## 状态与适用边界

本准则在任何 OpenLB350 结果出现前冻结。比较对象是
`references/openfoam350/reference_stage1_20260827/` 的 OpenFOAM 350 数值回归
参考，不是实验真值。它不要求逐格或逐时间步相同。

尚未证明 OpenLB 的物理时间映射。因此默认共同坐标是实际
`mean_top_displacement_m` 或 `normalized_plate_state`。只有 R1 的单位、移动层
守恒和气体映射均通过后，才可将 `time_s` 升为强比较坐标；在此之前，`t50` 和
`t90` 不得作为 PASS 指标。

## 预冻结 QoI

| QoI | OpenFOAM 350 定义与来源 | OpenLB 对应定义 | 比较 | 容差 | Gate |
| --- | --- | --- | --- | --- | --- |
| 全域液相库存 | `global.liquid_volume_m3 = sum(alpha*V)` | 同一物理体积上的液相库存 | 同一位移状态的绝对值与相对差 | `TOLERANCE_PENDING_JUSTIFICATION` | HARD_GATE |
| 区域填充 | `regions.phase_fraction_volume_weighted = sum(alpha*V)/sum(V)`，16区 | 同一矩形区域、同一体积加权定义 | 每区及汇总误差 | `TOLERANCE_PENDING_JUSTIFICATION` | HARD_GATE |
| EC1XT240 填充 | `region=EC1XT240OASZone` 的体积加权相分数与液相体积 | 相同回归矩形区域；不是 OAS 显式几何 | 位移参数化曲线及末态 | `TOLERANCE_PENDING_JUSTIFICATION` | HARD_GATE |
| 平均压力 | `mean_pressure_Pa`（绝对压力、体积加权） | 相同压力基准与体积加权 | 曲线趋势、绝对值和相对差 | `TOLERANCE_PENDING_JUSTIFICATION` | HARD_GATE |
| 压力范围 | `pressure_min_Pa`、`pressure_max_Pa` | 同一区域/时态的范围 | 只比较范围与趋势 | `TOLERANCE_PENDING_JUSTIFICATION` | SOFT_DIAGNOSTIC |
| 速度 | `mean_speed_m_s` 与 `max_speed_m_s` | 体积加权 `abs(U)` 与单元最大值 | 平均速度为主，最大值诊断 | `TOLERANCE_PENDING_JUSTIFICATION` | HARD_GATE / SOFT_DIAGNOSTIC |
| 压板位移 | `mean_top_displacement_m`，由实际 `cellDisplacement` 重建 | 由 OpenLB 移动层状态重建 | 对齐共同回归状态；不以名义时间替代实际状态 | `TOLERANCE_PENDING_JUSTIFICATION` | HARD_GATE |
| 等效层厚 | `mean_layer_height_m = mean(1 um + 2*cellDisplacement_z)` | 同一深度平均层厚 | 绝对值与相对差 | `TOLERANCE_PENDING_JUSTIFICATION` | HARD_GATE |
| 边界液相通量 | `alphaPhi.liquid`，patch 外向为正 | 相同 patch、外向为正 | 各 patch 与净通量，位移状态对齐 | `TOLERANCE_PENDING_JUSTIFICATION` | HARD_GATE |
| 守恒残差 | 库存变化联合液相边界通量；现有0.05 s梯形积分仅诊断 | 使用 OpenLB 实际步长的库存/边界通量残差 | 分别报告，不能把开放边界库存变化叫质量错误 | `TOLERANCE_PENDING_JUSTIFICATION` | HARD_GATE |
| 气体压缩 | `gas_dominant_*`（`alpha<0.01`，混合rho反演）及EOS残差 | 已定义的气体EOS/储气近似 | 压力-密度响应和对主QoI的影响 | `TOLERANCE_PENDING_JUSTIFICATION` | HARD_GATE |
| 推断气相体积通量 | `phi-alphaPhi.liquid` | 仅在 OpenLB 可定义可比量时 | 定性/趋势检查 | `NOT_A_STANDALONE_TARGET` | INFORMATION_ONLY |

## 为什么暂不指定数值百分比

目前只有一套成功 OpenFOAM 输出，尚无 OpenLB 的网格/时间步收敛结果，也未完成
VOF—OpenLB 界面、`perfectGas` 和移动三维等效层的数学映射。任何现在写入的具体
百分比都会是凭空指定，并可能在看到 OpenLB 结果后被反向调参。因此所有跨求解器
数值容差保持 `TOLERANCE_PENDING_JUSTIFICATION`。

R1 必须先提供：单位转换测试、单相区域阻力压降测试、局部及全域移动层守恒测试、
气体压力—密度响应测试，以及 OpenLB 网格/时间步敏感性证据。随后以独立记录的
数值误差预算一次性冻结容差，不能为了通过某次 OpenLB 结果再改动。

## 参考数据限制

- `p` 是绝对压力；不得与 `p_rgh` 或 gauge pressure 混比。
- `alphaPhi.liquid` 和 `phi` 的正号均按 OpenFOAM patch 外法向；推断气相通量不是
  独立输出的气相质量通量。
- 0.05 s快照的通量积分只能做自洽诊断，不能当作每求解器时间步的严格守恒证明。
- 对 16 个区域，实际 `cellDisplacement` 字段是回归坐标的权威记录；它优先于用
  名义五次函数反算的近似值。
