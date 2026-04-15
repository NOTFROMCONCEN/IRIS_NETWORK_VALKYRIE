# 快速入门指南

## 5分钟快速上手

### 第一步：环境检查

```bash
# 检查Python版本（需要3.7+）
python --version

# 运行环境检查脚本
python scripts/check_env.py
```

### 第二步：安装依赖

```bash
# 安装所需依赖包（仅4个核心包）
pip install -r requirements.txt
```

### 第三步：配置

1. **配置设备信息**
   ```bash
   # 编辑设备配置文件
   # Excel格式，包含列：生产厂商、设备型号、device、IP
   notepad devices/devices.xlsx  # Windows
   # 或
   open devices/devices.xlsx     # macOS
   ```

2. **配置认证信息**（可选，默认配置已可用）
   ```bash
   # 编辑密码配置
   notepad config/password.conf
   ```

### 第四步：运行

```bash
# 运行所有设备
python main.py

# 或指定条件
python main.py --vendor ruijie
python main.py --ip 192.168.1.1
python main.py --logmode
```

## 常用命令

### 基本命令

```bash
# 查看帮助
python main.py --help

# 查看版本
python main.py --version

# 列出支持的厂商
python main.py --list-vendors

# 环境检查
python scripts/check_env.py
```

### 过滤选项

```bash
# 按厂商过滤
python main.py --vendor ruijie
python main.py --vendor huawei

# 按IP过滤
python main.py --ip 192.168.1.1

# 快捷选项
python main.py --ruijie          # 只处理锐捷设备
python main.py --huawei          # 只处理华为设备
```

### 工作模式

```bash
# 标准巡检模式（执行所有命令）
python main.py

# 日志收集模式（只收集日志）
python main.py --logmode

# 组合使用
python main.py --vendor ruijie --logmode
```

## 设备配置示例

### devices.xlsx 格式

| 生产厂商 | 设备型号 | device       | IP           |
| -------- | -------- | ------------ | ------------ |
| ruijie   | RG-S6000 | SW-Core-01   | 192.168.1.1  |
| huawei   | S5700    | SW-Access-01 | 192.168.1.10 |
| h3c      | S5120    | SW-Access-02 | 192.168.1.11 |

### password.conf 格式

```ini
# 默认配置
default=check.sd,31485sdQRXG=

# 各厂商专用配置（可选）
ruijie=check.sd,Password123
huawei=admin,Password456
```

## 输出说明

### 结果文件

巡检结果保存在 `output/results/` 目录：

```
设备名(IP)(日期)(厂商).log
示例: SW-Core-01(192.168.1.1)(2025-10-15)(ruijie).log
```

### 日志文件

运行日志保存在 `output/logs/` 目录：

```
inspection_YYYYMMDD_HHMMSS.log
```

### 汇总报告

```
summary_YYYYMMDD_HHMMSS.txt
```

## 故障排查

### 问题1：模块未找到

```bash
# 错误：ModuleNotFoundError: No module named 'xxx'
# 解决：安装依赖
pip install -r requirements.txt
```

### 问题2：设备连接失败

```bash
# 检查网络连通性
ping 192.168.1.1

# 检查SSH端口
telnet 192.168.1.1 22

# 检查认证信息
# 编辑 config/password.conf
```

### 问题3：设备文件不存在

```bash
# 错误：设备配置文件不存在
# 解决：创建设备文件
# 从 old_python 复制：
cp ../old_python/DevicesXLSX/devices.xlsx devices/
```

## 与 old_python 的区别

### 命令兼容性

✅ 以下命令完全兼容：
- `python main.py`
- `python main.py --vendor ruijie`
- `python main.py --ip 192.168.1.1`
- `python main.py --logmode`
- `python main.py --ruijie`
- `python main.py --huawei`

❌ 以下功能已移除：
- `--mode gui` (GUI界面)
- `--mode web` (Web界面)

### 配置文件

- ✅ `password.conf` - 完全兼容
- ✅ `devices.xlsx` - 完全兼容
- ⚠️ `config.conf` → `config.yaml` - 需要转换格式

### 性能提升

- 启动速度：↓75% (2秒 → 0.5秒)
- 内存占用：↓67% (150MB → 50MB)
- 依赖包数：↓90% (40+ → 4个)

## 高级用法

### 批处理脚本

**Windows (run.bat):**
```batch
@echo off
cd /d %~dp0
python main.py --vendor ruijie --logmode
pause
```

**Linux/macOS (run.sh):**
```bash
#!/bin/bash
cd "$(dirname "$0")"
python main.py --vendor ruijie --logmode
```

### 定时任务

**Linux crontab:**
```bash
# 每天凌晨2点执行
0 2 * * * cd /path/to/new_python && python main.py --logmode
```

**Windows 任务计划程序:**
```
创建基本任务 → 设置触发器 → 启动程序：
程序：python
参数：main.py --logmode
起始于：C:\path\to\new_python
```

## 下一步

- 📖 阅读完整文档：[README.md](README.md)
- 🏗️ 了解架构设计：[ARCHITECTURE.md](ARCHITECTURE.md)
- 🔄 从旧版迁移：[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- 📊 查看优化分析：[OPTIMIZATION_ANALYSIS.md](OPTIMIZATION_ANALYSIS.md)

## 获取帮助

```bash
# 查看帮助信息
python main.py --help

# 运行环境检查
python scripts/check_env.py

# 查看支持的厂商
python main.py --list-vendors
```

---

**提示**: 首次使用建议先测试单台设备，确认正常后再批量执行！

```bash
# 测试单台设备
python main.py --ip 192.168.1.1

# 确认无误后批量执行
python main.py