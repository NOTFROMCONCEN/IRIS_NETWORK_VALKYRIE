# IRIS Network Valkyrie

网络设备巡检工具（v3.0.0）。

本仓库支持多厂商网络设备自动巡检，提供命令行巡检与设备管理 UI 两种入口。

## 项目结构

```text
Iris_Network_Valkyrie/
├── main.py                              # 仓库根目录入口（推荐）
├── README.md
├── .gitignore
├── CoreBase/
│   ├── main.py                          # 核心 CLI 入口（兼容保留）
│   ├── requirements.txt
│   ├── config/
│   │   ├── config.yaml
│   │   └── password.conf
│   ├── core/
│   ├── devices/
│   ├── output/
│   ├── scripts/
│   ├── ui/
│   └── doc/
└── PROJECT_RESTRUCTURE_PLAN_BLUEPRINT.md
```

## 程序入口

- 推荐入口：根目录 [main.py](main.py)
- 兼容入口：[CoreBase/main.py](CoreBase/main.py)

两者 CLI 参数保持一致。根入口会自动切换到 CoreBase 工作目录，保证现有相对路径配置不受影响。

## 快速开始

### 1) 安装依赖

```bash
pip install -r CoreBase/requirements.txt
```

### 2) 环境检查

```bash
python CoreBase/scripts/check_env.py
```

### 3) 查看帮助

```bash
python main.py --help
```

### 4) 常用命令

```bash
# 标准巡检（全部设备）
python main.py

# 按厂商过滤
python main.py --vendor huawei

# 按 IP 过滤
python main.py --ip 192.168.1.1

# 日志收集模式
python main.py --logmode

# 按分组过滤
python main.py --group 核心

# 模拟运行（不连接设备）
python main.py --dry-run

# 列出厂商与分组
python main.py --list-vendors
python main.py --list-groups

# 启动设备管理 UI
python main.py --ui
```

## 帮助参数速览

运行 `python main.py --help` 可看到完整分组说明。核心参数如下：

| 参数             | 说明                 |
| ---------------- | -------------------- |
| `--vendor`       | 按厂商过滤设备       |
| `--ip`           | 只处理指定 IP        |
| `--group`        | 按设备分组过滤       |
| `--logmode`      | 日志收集模式         |
| `--dry-run`      | 模拟执行，不连接设备 |
| `--ui`           | 启动 Streamlit UI    |
| `--config`       | 指定配置文件路径     |
| `--output-dir`   | 指定结果输出目录     |
| `--list-vendors` | 列出支持厂商         |
| `--list-groups`  | 列出设备分组         |
| `-y, --yes`      | 自动确认交互提示     |
| `--version`      | 显示版本信息         |

## 配置与输出路径

程序以 CoreBase 目录为工作目录，默认读取/写入：

- 设备清单：[CoreBase/devices/devices.xlsx](CoreBase/devices/devices.xlsx)
- 主配置：[CoreBase/config/config.yaml](CoreBase/config/config.yaml)
- 密码配置：[CoreBase/config/password.conf](CoreBase/config/password.conf)
- 日志输出：[CoreBase/output/logs](CoreBase/output/logs)
- 巡检结果：[CoreBase/output/results](CoreBase/output/results)

## 返回码说明

- 0：全部设备成功
- 1：全部失败或程序异常
- 2：部分成功
- 130：用户中断

## 文档导航

- 架构说明：[CoreBase/doc/ARCHITECTURE.md](CoreBase/doc/ARCHITECTURE.md)
- 快速手册：[CoreBase/doc/QUICKSTART.md](CoreBase/doc/QUICKSTART.md)
- 迁移指南：[CoreBase/doc/MIGRATION_GUIDE.md](CoreBase/doc/MIGRATION_GUIDE.md)

