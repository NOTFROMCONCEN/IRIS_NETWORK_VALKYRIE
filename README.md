# IRIS Network Valkyrie

网络设备自动巡检工具（v3.0.0）—— 支持 **7 大厂商**网络设备的自动巡检、日志收集、设备自发现和 Web 设备管理。

## 目录

- [功能概览](#功能概览)
- [项目结构](#项目结构)
- [部署指南](#部署指南)
  - [一、在线部署（有外网环境）](#一在线部署有外网环境)
  - [二、离线部署（内网环境）](#二离线部署内网环境)
- [配置说明](#配置说明)
  - [密码配置](#1-密码配置passwordconf)
  - [设备清单配置](#2-设备清单配置devicesxlsx)
  - [主配置文件](#3-主配置文件configyaml)
  - [命令配置文件](#4-命令配置文件commandsyaml)
  - [跳板机配置](#5-跳板机配置)
- [功能使用教程](#功能使用教程)
  - [标准巡检](#1-标准巡检)
  - [日志收集模式](#2-日志收集模式)
  - [设备过滤](#3-设备过滤)
  - [连通性测试](#4-连通性测试)
  - [设备自发现](#5-设备自发现)
  - [Web 管理界面](#6-web-管理界面)
  - [定时巡检](#7-定时巡检)
- [帮助参数速查](#帮助参数速查)
- [输出文件说明](#输出文件说明)
- [返回码说明](#返回码说明)
- [常见问题](#常见问题)
- [文档导航](#文档导航)

---

## 功能概览

| 功能             | 说明                                                              |
| ---------------- | ----------------------------------------------------------------- |
| **多厂商巡检**   | 支持华为、H3C、思科、锐捷、迈普、龙马防火墙（WST）共 7 大厂商     |
| **标准巡检**     | SSH 自动连接设备，执行预定义巡检命令，结果保存到日志文件          |
| **日志收集**     | 专门收集设备运行日志（如 logbuffer、logfile 等）                  |
| **设备自发现**   | LLDP/CDP 邻居递归发现 + 子网扫描，发现结果预览后手动导入          |
| **Web 管理界面** | 基于 Streamlit 的可视化界面，支持设备增删改查、巡检控制、统计分析 |
| **跳板机支持**   | 支持通过 SSH 跳板机连接内网设备，可全局或按设备单独配置           |
| **密码加密**     | 支持密码文件加密存储（`ENC:` 前缀格式），避免明文泄露             |
| **离线部署**     | 提供一键离线打包脚本，适用于无外网的内网运维环境                  |

## 项目结构

```text
Iris_Network_Valkyrie/
├── main.py                              # 仓库根目录入口（推荐）
├── README.md
├── .gitignore
│
├── CoreBase/                            # 核心程序目录
│   ├── main.py                          # CLI 主入口
│   ├── requirements.txt                 # Python 依赖
│   ├── SETUP.md                         # 快速配置指南
│   │
│   ├── config/                          # 配置文件目录
│   │   ├── config.yaml                  # 主配置文件
│   │   ├── commands.yaml                # 巡检命令定义
│   │   ├── password.conf                # 密码凭证（需自行创建）
│   │   └── password_example.conf        # 密码凭证示例
│   │
│   ├── core/                            # 核心代码
│   │   ├── engine.py                    # 设备巡检引擎
│   │   ├── adapters.py                  # 多厂商适配器（7 大厂商）
│   │   ├── device_inventory.py          # 设备清单读写
│   │   ├── utils.py                     # 工具函数
│   │   ├── crypto.py                    # 密码加密/解密
│   │   ├── saver.py                     # 结果保存
│   │   ├── notifier.py                  # 桌面通知
│   │   ├── lock.py                      # 进程锁（防重入）
│   │   ├── paths.py                     # 路径管理
│   │   ├── validator.py                 # 数据验证
│   │   ├── performance.py              # 性能监控
│   │   └── discovery/                   # 设备自发现模块
│   │       ├── __init__.py
│   │       ├── discovery_models.py      # 数据模型
│   │       ├── vendor_identifier.py     # 厂商识别引擎
│   │       ├── device_prober.py         # 设备探测器
│   │       ├── lldp_discovery.py        # LLDP/CDP 邻居发现
│   │       ├── subnet_scanner.py        # 子网扫描器
│   │       ├── merger.py                # 结果去重合并
│   │       └── manager.py              # 发现管理器
│   │
│   ├── devices/                         # 设备清单目录
│   │   └── devices.xlsx                 # 设备清单（需自行创建）
│   │
│   ├── output/                          # 输出目录（自动创建）
│   │   ├── logs/                        # 运行日志
│   │   └── results/                     # 巡检结果
│   │
│   ├── scripts/                         # 工具脚本
│   │   ├── check_env.py                # 环境检查
│   │   ├── create_example_devices.py    # 创建示例设备表
│   │   └── encrypt_password.py         # 密码加密工具
│   │
│   ├── ui/                              # Web UI
│   │   ├── app.py                       # Streamlit 应用
│   │   └── device_manager.py            # 设备 CRUD 管理
│   │
│   └── doc/                             # 文档目录
│       ├── QUICKSTART.md                # 快速入门
│       ├── ARCHITECTURE.md              # 架构说明
│       └── MIGRATION_GUIDE.md           # 迁移指南
│
├── deploy/                              # 部署工具目录
│   ├── offline_build.ps1                # 离线打包脚本
│   ├── run_cli.bat                      # CLI 快捷启动
│   ├── run_ui.bat                       # UI 快捷启动
│   └── OFFLINE_DEPLOY.md               # 离线部署说明
│
└── plans/                               # 设计文档
    └── device_discovery_plan.md         # 设备发现功能设计方案
```

## 程序入口

- **推荐入口**：根目录 [`main.py`](main.py)
- **兼容入口**：[`CoreBase/main.py`](CoreBase/main.py)

两者 CLI 参数完全一致。根入口会自动切换到 CoreBase 工作目录，保证相对路径配置不受影响。

---

## 部署指南

### 一、在线部署（有外网环境）

适用于开发机或能访问公网的运维主机。

#### 第 1 步：确认 Python 环境

本项目需要 **Python 3.8+**（推荐 3.10+）。

```bash
# 检查版本
python --version
# 或
py --version
```

#### 第 2 步：安装依赖

在仓库根目录下执行：

```bash
pip install -r CoreBase/requirements.txt
```

依赖包列表（共 7 个核心包）：

| 包名           | 用途                |
| -------------- | ------------------- |
| `netmiko`      | SSH 连接网络设备    |
| `openpyxl`     | 读写 Excel 设备清单 |
| `pandas`       | 数据处理            |
| `PyYAML`       | 解析 YAML 配置文件  |
| `streamlit`    | Web 管理界面        |
| `psutil`       | 系统资源监控        |
| `cryptography` | 密码加密存储        |

#### 第 3 步：运行环境检查

```bash
python CoreBase/scripts/check_env.py
```

输出示例：

```text
[OK] Python 3.10.11
[OK] netmiko 4.2.0
[OK] openpyxl 3.1.2
[OK] pandas 2.1.4
[OK] PyYAML 6.0.1
[OK] cryptography 41.0.7
[INFO] streamlit 未安装 (可选, Web UI 需要)
```

如果 `streamlit` 显示未安装但你需要 Web UI，请额外执行：

```bash
pip install streamlit
```

#### 第 4 步：配置密码文件

```bash
# Windows
copy CoreBase\config\password_example.conf CoreBase\config\password.conf

# Linux/macOS
cp CoreBase/config/password_example.conf CoreBase/config/password.conf
```

然后编辑 `CoreBase/config/password.conf`，填入真实的设备凭证。详细格式见 [密码配置](#1-密码配置passwordconf) 章节。

> 💡 **推荐使用加密格式**：运行 `python CoreBase/scripts/encrypt_password.py` 生成加密密码。

#### 第 5 步：配置设备清单

创建或编辑 `CoreBase/devices/devices.xlsx`。可参考示例文件：

```bash
# 生成示例设备表（可选）
python CoreBase/scripts/create_example_devices.py
```

详细格式见 [设备清单配置](#2-设备清单配置devicesxlsx) 章节。

#### 第 6 步：验证安装

```bash
# 查看帮助信息
python main.py --help

# 查看版本
python main.py --version

# 列出支持的厂商
python main.py --list-vendors

# 模拟运行（不连接设备）
python main.py --dry-run
```

#### 第 7 步：开始使用

```bash
# 巡检所有设备
python main.py

# 启动 Web 管理界面
python main.py --ui
```

---

### 二、离线部署（内网环境）

适用于目标机器无法访问外网的环境。

#### 第 1 步：在联网机器上生成交付包

> 建议联网机器与目标机器保持相同的 **Windows 版本**、**CPU 架构**和 **Python 大小版本**。

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\offline_build.ps1
```

如需指定 Python 解释器：

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\offline_build.ps1 -PythonExe "C:\Python310\python.exe"
```

构建完成后，手动把对应版本的 Python 安装包放入：

```text
deploy\build\Iris_Network_Valkyrie_OfflineBundle\python-installer\
```

生成的交付包结构：

```text
Iris_Network_Valkyrie_OfflineBundle/
├── Iris_Network_Valkyrie/     # 项目运行副本
├── wheelhouse/                # 离线依赖包
├── python-installer/          # Python 安装包（需手动放入）
├── run_ui.bat                 # UI 快捷启动
├── run_cli.bat                # CLI 快捷启动
├── OFFLINE_DEPLOY.md          # 离线部署说明
└── bundle-info.txt            # 构建信息
```

#### 第 2 步：将交付包复制到内网机器

将整个 `Iris_Network_Valkyrie_OfflineBundle` 目录拷贝到目标机器，例如 `D:\Tools\`。

#### 第 3 步：在内网机器上安装

1. **安装 Python**：运行 `python-installer` 目录中的安装包。
2. **创建虚拟环境**：

```powershell
cd D:\Tools\Iris_Network_Valkyrie_OfflineBundle
py -m venv .venv
```

3. **离线安装依赖**：

```powershell
.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse -r .\Iris_Network_Valkyrie\CoreBase\requirements.txt
```

4. **验证安装**：

```powershell
.\run_cli.bat --help
```

#### 第 4 步：配置业务文件

确认以下文件已替换为实际配置：

- `Iris_Network_Valkyrie\CoreBase\config\password.conf`
- `Iris_Network_Valkyrie\CoreBase\config\config.yaml`
- `Iris_Network_Valkyrie\CoreBase\devices\devices.xlsx`

#### 第 5 步：日常使用

```powershell
# CLI 模式
.\run_cli.bat
.\run_cli.bat --vendor huawei

# UI 模式
.\run_ui.bat
```

---

## 配置说明

### 1. 密码配置（password.conf）

**文件路径**：`CoreBase/config/password.conf`（需从 `password_example.conf` 复制创建）

**格式**：`厂商名=用户名,密码`

```ini
# 华为设备
huawei=admin,Huawei@123

# H3C设备
h3c=admin,H3c@123

# 锐捷设备
ruijie=admin,Ruijie@123

# 迈普设备
maipu=admin,Maipu@123

# 龙马防火墙
wst=admin,Wst@123

# 思科设备
cisco=admin,Cisco@123
```

**支持的厂商关键字**：`huawei`、`h3c`、`cisco`、`ruijie`、`maipu`、`wst`

#### 密码加密（推荐）

1. 安装 `cryptography` 包（已包含在 requirements.txt 中）
2. 运行加密工具：

```bash
python CoreBase/scripts/encrypt_password.py
```

3. 加密后的密码以 `ENC:` 开头：

```ini
huawei=admin,ENC:gAAAAABl...
```

### 2. 设备清单配置（devices.xlsx）

**文件路径**：`CoreBase/devices/devices.xlsx`

| 列名         | 必填 | 说明               | 示例        |
| ------------ | ---- | ------------------ | ----------- |
| 设备名       | ✅    | 设备名称           | Core-SW-01  |
| IP地址       | ✅    | 设备 IP 地址       | 192.168.1.1 |
| 厂商         | ✅    | 设备厂商关键字     | huawei      |
| 端口         | ❌    | SSH 端口，默认 22  | 22          |
| 设备型号     | ❌    | 设备型号           | S5700       |
| 位置         | ❌    | 设备物理位置       | 核心机房    |
| 联系人       | ❌    | 负责人             | 张三        |
| 备注         | ❌    | 其他备注           | 核心交换机  |
| 分组         | ❌    | 设备分组，用于过滤 | 核心        |
| 跳板机地址   | ❌    | 跳板机 IP          | 10.0.0.1    |
| 跳板机端口   | ❌    | 跳板机 SSH 端口    | 22          |
| 跳板机用户名 | ❌    | 跳板机登录用户名   | admin       |
| 跳板机密码   | ❌    | 跳板机登录密码     | password123 |

**示例设备清单**：

| 设备名       | IP地址       | 厂商   | 端口 | 设备型号   | 位置     | 分组 |
| ------------ | ------------ | ------ | ---- | ---------- | -------- | ---- |
| Core-SW-01   | 192.168.1.1  | huawei | 22   | S5700      | 核心机房 | 核心 |
| Access-SW-01 | 192.168.10.1 | ruijie | 22   | RG-S6000   | 楼层1    | 接入 |
| Core-RT-01   | 10.0.0.1     | cisco  | 22   | C9300      | 核心机房 | 核心 |
| FW-01        | 172.16.0.1   | wst    | 22   | 龙马防火墙 | 边界     | 安全 |

### 3. 主配置文件（config.yaml）

**文件路径**：`CoreBase/config/config.yaml`

关键配置项说明：

```yaml
system:
  log_level: INFO              # 日志级别: DEBUG/INFO/WARNING/ERROR
  retries: 3                   # 连接重试次数
  timeout: 120                 # 默认超时（秒）
  max_workers_precheck: 20     # 预检查并发数
  max_workers_batch: 5         # 巡检并发数
  password_error_disconnect: true  # 密码错误立即断开

network:
  ssh_port: 22                 # 默认 SSH 端口
  connect_timeout: 60          # SSH 连接超时
  command_timeout: 120         # 命令执行超时

output:
  logs_dir: output/logs        # 日志输出目录
  results_dir: output/results  # 巡检结果输出目录
  log_rotation:
    enabled: true
    max_bytes: 10485760        # 单个日志文件最大 10MB
    backup_count: 7            # 保留 7 个备份
    compress_old_logs: true    # 自动压缩旧日志
```

### 4. 命令配置文件（commands.yaml）

**文件路径**：`CoreBase/config/commands.yaml`

定义每个厂商的巡检命令。标准巡检和日志收集模式分别使用不同的命令组。一般无需修改，如需自定义巡检命令请参考文件内的注释。

### 5. 跳板机配置

本工具支持通过 SSH 跳板机连接内网设备，适用于 **内网 PC → 跳板机 → 设备** 的网络拓扑。

#### 方式一：设备清单配置（推荐）

在 `devices.xlsx` 中为每个设备单独配置跳板机信息（见上方设备清单表格）：

| 设备名       | IP地址       | 厂商   | 跳板机地址 | 跳板机端口 | 跳板机用户名 | 跳板机密码  |
| ------------ | ------------ | ------ | ---------- | ---------- | ------------ | ----------- |
| Core-SW-01   | 192.168.1.1  | huawei |            | 22         |              |             |
| Access-SW-01 | 192.168.10.1 | ruijie | 10.0.0.1   | 22         | admin        | password123 |

> 不配置跳板机字段的设备将直接连接。

#### 方式二：全局配置

在 [`config/config.yaml`](CoreBase/config/config.yaml) 中配置默认跳板机：

```yaml
network:
  jump_host:
    address: 10.0.0.1
    port: 22
    username: admin
    password: password123
    connect_timeout: 30
    command_timeout: 60
```

> ⚠️ **注意**：设备清单中的跳板机配置**优先级高于**全局配置。建议在设备清单中配置，避免在配置文件中存储明文密码。

#### 连接流程

```text
本工具 → SSH 连接跳板机 → 从跳板机 SSH 连接目标设备 → 执行巡检命令
```

---

## 功能使用教程

### 1. 标准巡检

标准巡检模式会自动 SSH 连接设备，执行预定义的巡检命令集（如 CPU、内存、接口状态等），将结果保存为日志文件。

```bash
# 巡检所有设备
python main.py

# 自动确认（跳过交互提示）
python main.py --yes

# 模拟运行（不实际连接设备，用于检查配置）
python main.py --dry-run
```

**巡检流程**：

1. 加载设备清单和密码配置
2. 预检查：并发 Ping + SSH 端口探测，过滤不可达设备
3. 确认：显示设备列表，等待用户确认（`--yes` 可跳过）
4. 执行巡检：多线程并发连接设备，执行命令并收集输出
5. 保存结果：每个设备生成一个巡检结果文件

### 2. 日志收集模式

日志收集模式专门用于收集设备运行日志（如 `display logbuffer`、`show logging` 等），命令集与标准巡检不同。

```bash
# 收集所有设备日志
python main.py --logmode

# 收集指定厂商设备日志
python main.py --logmode --vendor huawei

# 收集指定设备日志
python main.py --logmode --ip 192.168.1.1
```

### 3. 设备过滤

支持按厂商、IP、分组等维度过滤设备：

```bash
# 按厂商过滤
python main.py --vendor huawei        # 只巡检华为设备
python main.py --vendor ruijie        # 只巡检锐捷设备
python main.py --vendor cisco         # 只巡检思科设备

# 按 IP 过滤（单台设备）
python main.py --ip 192.168.1.1

# 按分组过滤
python main.py --group 核心           # 只巡检"核心"分组的设备
python main.py --group 接入           # 只巡检"接入"分组的设备

# 组合过滤
python main.py --vendor huawei --group 核心 --logmode

# 查看可用的厂商和分组
python main.py --list-vendors
python main.py --list-groups
```

**支持的厂商列表**：

| 厂商关键字 | 设备厂商           | 适配器        |
| ---------- | ------------------ | ------------- |
| `huawei`   | 华为               | HuaweiAdapter |
| `h3c`      | H3C（新华三）      | H3CAdapter    |
| `cisco`    | 思科               | CiscoAdapter  |
| `ruijie`   | 锐捷（含下级设备） | RuijieAdapter |
| `maipu`    | 迈普               | MaipuAdapter  |
| `wst`      | 龙马防火墙         | WSTAdapter    |

### 4. 连通性测试

在实际巡检前，可以先测试设备的网络连通性：

```bash
# 使用 --dry-run 模拟（不连接设备）
python main.py --dry-run

# --dry-run 会自动执行预检查（Ping + SSH端口探测）
# 输出示例：
# [OK] 192.168.1.1   Ping=OK SSH=OK
# [FAIL] 192.168.1.2 Ping=FAIL SSH=-
```

### 5. 设备自发现

设备自发现功能支持两种发现方式，可以单独使用或组合使用：

#### 5.1 LLDP/CDP 邻居发现

从已知设备（种子设备）出发，通过 LLDP 或 CDP 协议递归发现相邻网络设备。

```bash
# 使用设备清单中的所有设备作为种子
python main.py --discover lldp

# 指定种子设备 IP
python main.py --discover lldp --seed-ip 192.168.1.1

# 设置递归深度（默认 3 层）
python main.py --discover lldp --depth 2

# 指定多个种子设备
python main.py --discover lldp --seed-ip 192.168.1.1,192.168.1.2
```

**发现流程**：

1. 连接种子设备，执行 `show lldp neighbor`（或 `display lldp neighbor`）
2. 解析邻居设备 IP 地址和基本信息
3. 对新发现的设备递归执行步骤 1-2，直到达到最大深度
4. 输出发现结果汇总

#### 5.2 子网扫描

扫描指定网段，自动发现网络设备。

```bash
# 扫描单个子网
python main.py --discover subnet --subnets 192.168.1.0/24

# 扫描多个子网（逗号分隔）
python main.py --discover subnet --subnets 10.0.0.0/24,172.16.0.0/24

# 仅探测可达性（Ping + SSH端口，不尝试登录）
python main.py --discover subnet --subnets 192.168.1.0/24 --discover-dry-run
```

**扫描流程**（三阶段）：

1. **ICMP Ping 探测**：并发 Ping 子网内所有 IP，筛出存活主机
2. **SSH 端口探测**：对存活主机探测 SSH 端口（默认 22），筛出开放端口的主机
3. **SSH 登录识别**：尝试 SSH 登录，通过 Banner/命令输出识别设备厂商和型号

> 💡 使用 `--discover-dry-run` 可跳过第 3 步，仅完成前两步的快速探测。

#### 5.3 组合发现

同时使用 LLDP 邻居发现和子网扫描，自动去重合并结果：

```bash
python main.py --discover all --subnets 192.168.1.0/24 --depth 2
```

#### 5.4 发现结果处理

```bash
# 导出发现结果到 Excel 文件
python main.py --discover subnet --subnets 192.168.1.0/24 --discover-output discovered.xlsx

# 交互式导入发现的设备到设备清单
python main.py --discover lldp --discover-import
```

**交互式导入流程**：

1. 执行设备发现
2. 显示发现设备列表（排除已存在于设备清单中的设备）
3. 逐台询问是否导入（输入 `y` 确认，`n` 跳过，`a` 全部导入）
4. 选中的设备自动写入 `devices.xlsx`

#### 5.5 Web UI 中使用设备发现

1. 启动 Web UI：`python main.py --ui`
2. 在左侧菜单选择 **🔍 设备发现**
3. 选择发现模式（LLDP / 子网扫描 / 组合）
4. 配置参数后点击 **开始发现**
5. 查看结果列表，勾选需要导入的设备
6. 点击 **导入选中设备到设备清单**

### 6. Web 管理界面

基于 Streamlit 的 Web 管理界面，提供可视化操作。

#### 启动

```bash
python main.py --ui
```

启动后自动打开浏览器访问 `http://localhost:8501`。

#### 功能页面

| 页面           | 功能                                          |
| -------------- | --------------------------------------------- |
| **📊 巡检控制** | 配置巡检参数、启动/停止巡检、实时查看日志输出 |
| **📋 设备管理** | 增删改查设备、批量导入/导出 CSV               |
| **📈 统计分析** | 设备厂商分布、设备类型统计、快速连通性测试    |
| **🔍 设备发现** | LLDP/子网扫描设备发现、预览导入               |
| **📥 导入导出** | 设备清单 CSV 导入导出                         |

#### 巡检控制页面

1. 在侧边栏参数面板配置巡检参数：
   - 选择厂商（可选，默认全部）
   - 输入 IP（可选，指定单台设备）
   - 选择分组（可选）
   - 选择巡检模式（标准巡检 / 日志收集）
2. 点击 **开始巡检**
3. 实时查看巡检进度和日志输出
4. 巡检完成后查看运行摘要

#### 设备管理页面

- **添加设备**：填写设备名、IP、厂商、端口等信息
- **编辑设备**：选择已有设备修改配置
- **删除设备**：选择设备确认删除
- **搜索/筛选**：按名称、IP、厂商、分组搜索

### 7. 定时巡检

#### Linux crontab

```bash
# 每天凌晨 2 点执行全量巡检
0 2 * * * cd /path/to/Iris_Network_Valkyrie && python main.py --yes >> /var/log/valkyrie.log 2>&1

# 每天凌晨 3 点收集华为设备日志
0 3 * * * cd /path/to/Iris_Network_Valkyrie && python main.py --vendor huawei --logmode --yes
```

#### Windows 任务计划程序

1. 打开 **任务计划程序** → **创建基本任务**
2. 设置触发器（如每天凌晨 2:00）
3. 操作选择 **启动程序**：
   - 程序：`python` 或 `py`
   - 参数：`main.py --yes`
   - 起始于：`X:\path\to\Iris_Network_Valkyrie`

#### Windows 批处理脚本

```batch
@echo off
cd /d %~dp0
python main.py --yes
pause
```

---

## 帮助参数速查

运行 `python main.py --help` 可查看完整帮助。

### 基本参数

| 参数                  | 说明                        |
| --------------------- | --------------------------- |
| `--vendor <厂商>`     | 按厂商过滤设备              |
| `--ip <IP>`           | 只处理指定 IP 设备          |
| `--group <分组>`      | 按设备分组过滤              |
| `--logmode`           | 日志收集模式                |
| `--dry-run`           | 模拟执行，不连接设备        |
| `--ui`                | 启动 Streamlit Web 管理界面 |
| `--config <路径>`     | 指定配置文件路径            |
| `--output-dir <路径>` | 指定结果输出目录            |
| `--list-vendors`      | 列出支持的厂商              |
| `--list-groups`       | 列出设备分组                |
| `-y, --yes`           | 自动确认交互提示            |
| `--version`           | 显示版本信息                |

### 设备发现参数

| 参数                       | 说明                                    |
| -------------------------- | --------------------------------------- |
| `--discover <模式>`        | 设备发现模式：`lldp` / `subnet` / `all` |
| `--subnets <CIDR>`         | 子网列表，逗号分隔（CIDR 格式）         |
| `--seed-ip <IP>`           | LLDP 种子设备 IP，逗号分隔              |
| `--depth <N>`              | LLDP 递归发现深度（默认 3）             |
| `--discover-output <路径>` | 发现结果导出 Excel 文件路径             |
| `--discover-import`        | 交互式选择导入发现的设备到清单          |
| `--discover-dry-run`       | 仅探测可达性，不尝试 SSH 登录           |

---

## 输出文件说明

程序以 `CoreBase` 目录为工作目录，默认读取/写入以下路径：

### 输入文件

| 文件                            | 说明         |
| ------------------------------- | ------------ |
| `CoreBase/config/config.yaml`   | 主配置文件   |
| `CoreBase/config/commands.yaml` | 巡检命令定义 |
| `CoreBase/config/password.conf` | 设备凭证     |
| `CoreBase/devices/devices.xlsx` | 设备清单     |

### 输出目录

| 目录/文件                  | 说明                                         |
| -------------------------- | -------------------------------------------- |
| `CoreBase/output/logs/`    | 运行日志（`inspection_YYYYMMDD_HHMMSS.log`） |
| `CoreBase/output/results/` | 巡检结果（`设备名(IP)(日期)(厂商).log`）     |

### 巡检结果文件命名规则

```text
SW-Core-01(192.168.1.1)(2026-06-12)(huawei).log
```

### 运行日志命名规则

```text
inspection_20260612_020000.log
```

---

## 返回码说明

| 返回码 | 说明               |
| ------ | ------------------ |
| `0`    | 全部设备巡检成功   |
| `1`    | 全部失败或程序异常 |
| `2`    | 部分设备成功       |
| `130`  | 用户中断（Ctrl+C） |

---

## 常见问题

### Q1：SSH 连接失败

```text
[FAIL] 192.168.1.1 - SSH连接失败
```

**排查步骤**：

1. 确认设备 IP 可达：`ping 192.168.1.1`
2. 确认 SSH 端口开放：`telnet 192.168.1.1 22`
3. 确认用户名密码正确：检查 `password.conf` 配置
4. 如使用跳板机，确认跳板机连通性和凭证

### Q2：模块未找到

```text
ModuleNotFoundError: No module named 'xxx'
```

**解决方法**：

```bash
pip install -r CoreBase/requirements.txt
```

### Q3：设备文件不存在

```text
设备配置文件不存在: devices/devices.xlsx
```

**解决方法**：

- 创建 `CoreBase/devices/devices.xlsx`，按 [设备清单配置](#2-设备清单配置devicesxlsx) 格式填写
- 或运行 `python CoreBase/scripts/create_example_devices.py` 生成示例文件

### Q4：Web UI 启动失败

**解决方法**：

1. 确认 `streamlit` 已安装：`pip install streamlit`
2. 检查端口 8501 是否被占用
3. 查看终端错误信息

### Q5：离线环境依赖安装失败

**解决方法**：

- 确认 `wheelhouse` 目录与目标机器 Python 版本一致
- 单独安装缺失的包：`.\.venv\Scripts\python.exe -m pip install --no-index --find-links .\wheelhouse streamlit`

### Q6：编码问题

程序已处理 Unicode 编码问题，使用 ASCII 字符替代特殊符号。如仍有乱码，请确保系统编码设置为 UTF-8。

---

## 文档导航

| 文档                                           | 说明                   |
| ---------------------------------------------- | ---------------------- |
| [架构说明](CoreBase/doc/ARCHITECTURE.md)       | 系统架构设计文档       |
| [快速手册](CoreBase/doc/QUICKSTART.md)         | 5 分钟快速入门         |
| [迁移指南](CoreBase/doc/MIGRATION_GUIDE.md)    | 旧版迁移说明           |
| [离线部署](deploy/OFFLINE_DEPLOY.md)           | 离线环境部署详细步骤   |
| [配置指南](CoreBase/SETUP.md)                  | 快速配置指南           |
| [设备发现设计](plans/device_discovery_plan.md) | 设备自发现功能设计方案 |
