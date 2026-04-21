# 项目目录重构计划与蓝图

> 适用范围：`new_check-64bit/` 工作区（重点是 `new_python/`）
> 
> 目标：在不破坏现有 CLI/UI 使用方式的前提下，完成目录分层、职责收敛与运行数据隔离。

## 1. 重构目标

1. 保持兼容：保留 `python main.py`、`python main.py --ui`、现有 CLI 参数与配置文件能力。
2. 分层清晰：入口层（CLI/UI）与业务层、基础设施层解耦。
3. 数据隔离：配置、设备源数据、运行输出分离，降低路径耦合。
4. 可扩展：新增厂商适配器、巡检模式、报表方式时只改局部模块。
5. 可回滚：分阶段迁移，任何阶段都可回退到上一稳定点。

## 2. 非目标（本次不做）

1. 不在本轮重构中新增业务功能。
2. 不改变现有厂商巡检命令语义。
3. 不强行替换全部历史文件路径（先兼容，后清理）。

## 3. 现状概览（As-Is）

当前核心目录（简化）：

```text
new_check-64bit/
├─ new_python/
│  ├─ main.py
│  ├─ config/
│  ├─ core/
│  ├─ devices/
│  ├─ output/
│  ├─ scripts/
│  ├─ ui/
│  └─ doc/
├─ others/
└─ output/
```

当前痛点：

1. 入口、业务、基础设施代码在目录层面耦合较重。
2. 运行产物路径分散，`new_python/output` 与根目录 `output` 容易混淆。
3. UI 与业务边界虽有雏形，但目录抽象还不够稳定。

## 4. 目标蓝图（To-Be）

建议采用“入口分离 + 领域分层 + 运行时数据隔离”的结构：

```text
new_check-64bit/
├─ apps/
│  ├─ cli/
│  │  └─ main.py
│  └─ ui/
│     └─ app.py
├─ src/
│  └─ inspection/
│     ├─ domain/
│     │  ├─ models.py
│     │  └─ rules.py
│     ├─ usecases/
│     │  ├─ run_inspection.py
│     │  ├─ run_log_collection.py
│     │  └─ manage_devices.py
│     ├─ infra/
│     │  ├─ adapters/
│     │  │  ├─ huawei.py
│     │  │  ├─ h3c.py
│     │  │  ├─ ruijie.py
│     │  │  ├─ maipu.py
│     │  │  └─ wst.py
│     │  ├─ storage/
│     │  │  ├─ device_repo.py
│     │  │  └─ config_repo.py
│     │  └─ reporting/
│     │     ├─ saver.py
│     │     └─ summary_writer.py
│     └─ shared/
│        ├─ logger.py
│        ├─ exceptions.py
│        └─ validators.py
├─ conf/
│  ├─ config.yaml
│  └─ password.conf
├─ data/
│  └─ devices/
│     └─ devices.xlsx
├─ runtime/
│  ├─ logs/
│  ├─ results/
│  └─ backups/
├─ scripts/
├─ tests/
├─ docs/
└─ legacy/
   └─ new_python/   (过渡期保留的兼容层，可在末期移除)
```

## 5. 文件映射蓝图（旧 -> 新）

### 5.1 入口层

1. `new_python/main.py` -> `apps/cli/main.py`
2. `new_python/ui/app.py` -> `apps/ui/app.py`
3. `new_python/ui/device_manager.py` -> `src/inspection/usecases/manage_devices.py` + `src/inspection/infra/storage/device_repo.py`

### 5.2 核心业务层

1. `new_python/core/engine.py` -> `src/inspection/usecases/run_inspection.py`
2. `new_python/core/adapters.py` -> `src/inspection/infra/adapters/*.py`（按厂商拆分）
3. `new_python/core/validator.py` -> `src/inspection/shared/validators.py`
4. `new_python/core/exceptions.py` -> `src/inspection/shared/exceptions.py`
5. `new_python/core/performance.py` -> `src/inspection/usecases/run_inspection.py` 或 `src/inspection/shared/perf.py`

### 5.3 输出与通知

1. `new_python/core/saver.py` -> `src/inspection/infra/reporting/saver.py`
2. `new_python/core/notifier.py` -> `src/inspection/infra/reporting/notifier.py`
3. `new_python/output/*` -> `runtime/*`

### 5.4 配置与数据

1. `new_python/config/config.yaml` -> `conf/config.yaml`
2. `new_python/config/password.conf` -> `conf/password.conf`
3. `new_python/devices/*` -> `data/devices/*`

### 5.5 文档

1. `new_python/doc/*` -> `docs/*`
2. `new_python/README.md` 中运行说明同步迁移到根级 `README.md`

## 6. 兼容策略（必须执行）

1. CLI 兼容：旧命令保持不变。
2. 参数兼容：已有参数名和默认行为不变。
3. 配置兼容：先读取新路径；不存在时回落读取旧路径。
4. 输出兼容：文件命名规则和主要字段保持一致。
5. 过渡入口：保留 `new_python/main.py`，仅做转发到 `apps/cli/main.py`。

建议路径解析顺序：

```text
config: conf/config.yaml -> new_python/config/config.yaml
password: conf/password.conf -> new_python/config/password.conf
devices: data/devices/devices.xlsx -> new_python/devices/devices.xlsx
runtime: runtime/* -> new_python/output/*
```

## 7. 分阶段迁移计划

## Phase 0: 基线冻结（0.5 天）

1. 产出当前功能基线：
   - `python main.py --help`
   - `python main.py --list-vendors`
   - `python main.py --dry-run`
   - `python main.py --ui`
2. 记录输出样例与失败设备文件样例。
3. 建立回滚标签（版本快照）。

交付物：`docs/restructure/baseline-checklist.md`

## Phase 1: 骨架落地（1 天）

1. 创建 `apps/`、`src/`、`conf/`、`data/`、`runtime/`、`docs/`、`tests/`。
2. 暂不迁移业务，仅创建兼容转发层。
3. `apps/cli/main.py` 可调用旧 `new_python/main.py`。

验收：所有旧命令可运行。

## Phase 2: 核心模块迁移（2~3 天）

1. 先迁移 `engine`、`adapters`、`validator`、`exceptions`。
2. 将厂商逻辑拆分至 `infra/adapters/*.py`。
3. 引入统一接口：`Adapter` 抽象 + 注册表。

验收：

1. `--list-vendors` 输出一致。
2. 至少 1 个厂商全流程通过（建议 Huawei）。

## Phase 3: 数据与输出迁移（1~2 天）

1. 配置与设备源数据迁移到 `conf/` 与 `data/`。
2. 报告与日志写入迁移到 `runtime/`。
3. 保留旧路径兜底读取 + 目录自动创建。

验收：

1. 新路径可生成完整结果。
2. 旧路径仍可被读取（兼容成功）。

## Phase 4: UI 融合与文档更新（1 天）

1. `apps/ui/app.py` 仅调用 usecases。
2. 数据读写落到 `device_repo.py`。
3. 更新 `README`、`QUICKSTART`、`ARCHITECTURE`。

验收：`python main.py --ui` 与新入口都可启动。

## Phase 5: 收口与清理（0.5~1 天）

1. 删除重复实现与无用兼容代码。
2. 将 `new_python/` 迁入 `legacy/` 或最终移除。
3. 完成变更日志与迁移说明。

验收：所有回归项通过，目录无重复职责模块。

## 8. 风险与应对

1. 风险：路径迁移导致找不到配置或设备文件。
   - 应对：路径回落策略 + 启动时打印最终解析路径。
2. 风险：厂商适配拆分后行为回归。
   - 应对：按厂商逐一回归，优先高频厂商。
3. 风险：UI 直接依赖旧模块导致耦合残留。
   - 应对：强制 UI 只依赖 usecases 与 repo 接口。
4. 风险：并发与超时参数在重构中丢失。
   - 应对：配置项迁移映射表 + 启动时配置校验。

## 9. 验收清单（DoD）

1. 兼容命令全部通过：
   - `python main.py`
   - `python main.py --vendor huawei`
   - `python main.py --ip <ip>`
   - `python main.py --logmode`
   - `python main.py --ui`
2. 新路径下可独立运行，不依赖旧目录。
3. 输出结构固定在 `runtime/logs` 与 `runtime/results`。
4. 文档已更新且路径说明一致。
5. 至少覆盖 1 次失败设备输出场景验证。

## 10. 建议的第一批落地动作（最小风险）

1. 先只做目录骨架和入口转发，不改业务逻辑。
2. 再做 `adapters.py` 拆分（每次只拆一个厂商）。
3. 最后做配置与输出路径迁移（保留回落）。

---

如果要开始实施，建议从 Phase 1 开始提交第一批改动，目标是“目录先到位，功能零回归”。
