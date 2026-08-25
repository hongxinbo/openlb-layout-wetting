# OpenLB Layout Wetting

这是研究14个OAS微/纳米版图中液体浸润与压力挤入过程的长期Git项目。

首个目标是 `SIM-EC1XT240.OAS`：先完成显式狭缝二维验证和排气基线，再做三维代表单元。第二个目标是 `SIM-H.OAS` 回字形结构。模型稳定并通过验证后，再比较不同沟槽尺寸、间距与排列。

## 当前状态

- 项目骨架：已建立。
- 14个OAS输入：已复制并记录SHA-256。
- EC1XT240初步几何审计：已记录。
- OpenFOAM 350参数来源审计：已建立初稿。
- OpenLB求解器：尚未实现。
- 正式物理结果：尚无。

## 先读这些文件

1. `AGENTS.md`：项目约束和科研结论边界。
2. `docs/PROJECT_SCOPE.md`：研究问题与阶段。
3. `docs/GEOMETRY_AUDIT.md`：版图解释。
4. `docs/PHYSICS_SPEC.md`：第一版物理模型。
5. `docs/PARAMETER_PROVENANCE.md`：参数来源和可用性。
6. `docs/VALIDATION_PLAN.md`：进入正式模拟前的验证门。

## 本机依赖

- OpenLB：通过 `OPENLB_ROOT` 指定，默认 `$HOME/Documents/openlb`。
- 当前核对版本：`1.9.0-19-g3dedbdd2`。
- 参考例程：
  - `examples/porousMedia/gasStorage2d/gasStorage2d.cpp`
  - `examples/multiComponent/bubbleChannel2d/bubbleChannel2d.cpp`

不要直接修改OpenLB源码；研究案例留在本仓库。

## 数据位置

大型原始资料和结果放在：

```text
$HOME/ResearchData/openlb-layout-wetting/
```

复制 `config/local_paths.example.yaml` 为 `config/local_paths.yaml` 后填写本机路径。后者被Git忽略。

## 路线

```text
几何与物理冻结
  -> 单相/界面/接触角验证
  -> EC1XT240二维排气基线
  -> 压力和阻力对照
  -> 封闭困气分支
  -> EC1XT240三维代表单元
  -> SIM-H三维
  -> 其他版图参数扫描
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
