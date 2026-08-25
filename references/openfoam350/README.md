# OpenFOAM 350参考案例审计入口

大型原始案例不进入Git。实际路径由 `config/local_paths.yaml` 指定。

已确认的原始事实摘要：

- 求解思路：`compressibleVoF`移动压模；
- 旧域平面约 `5250 um x 3000 um`，计算层厚约 `1 um`；
- EC1XT240区使用 `DarcyForchheimer d=(5e16,0,0)`、`f=(0,0,0)`；
- 液体候选标签为 `Immersion Liquid 5095`；
- 候选 `rho_l=1510 kg/m3`、`mu_l=1e-3 Pa s`、`sigma=0.0309 N/m`；
- 液滴半径约 `52 um`；
- EC1XT240顶部位移约 `-0.935 um`，运动时间 `1 s`。

这些是旧案例事实，不等于本项目采用值。详细采用状态见 `docs/PARAMETER_PROVENANCE.md`。
