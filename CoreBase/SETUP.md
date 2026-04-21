# 网络设备巡检工具 - 快速配置指南

## 项目简介

网络设备巡检工具 v3.0.0 是一个用于自动巡检网络设备的工具，支持多种厂商设备（华为、H3C、锐捷、迈普、龙马防火墙、思科等）。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置密码文件

复制示例密码文件并填入真实密码：

```bash
# Windows
copy config\password_example.conf config\password.conf

# Linux/Mac
cp config/password_example.conf config/password.conf
```

然后编辑 `config/password.conf`，填入真实的设备密码。

### 3. 配置设备列表

设备列表文件位于 `devices/devices.xlsx`，请参考 `devices/devices_example.xlsx` 示例文件创建。

设备表格式：

| 列名 | 必填 | 说明 |
|------|------|------|
| 设备名 | 是 | 设备名称 |
| IP地址 | 是 | 设备的IP地址 |
| 厂商 | 是 | 设备厂商：huawei, h3c, ruijie, maipu, wst, cisco |
| 端口 | 否 | SSH端口，默认22 |
| 设备型号 | 否 | 设备型号 |
| 位置 | 否 | 设备物理位置 |
| 联系人 | 否 | 设备联系人 |
| 备注 | 否 | 其他备注信息 |

### 4. 运行程序

#### 命令行模式

```bash
# 运行所有设备巡检
python main.py

# 只处理指定厂商设备
python main.py --vendor huawei

# 只处理指定IP设备
python main.py --ip 192.168.1.1

# 日志收集模式
python main.py --logmode

# 模拟运行（不实际连接设备）
python main.py --dry-run

# 自动确认（无需手动输入）
python main.py --yes
```

#### Web界面模式

```bash
python main.py --ui
```

然后在浏览器中访问 http://localhost:8501

## Git配置说明

### 已排除的敏感文件

以下文件已添加到 `.gitignore`，不会提交到Git：

- `config/password.conf` - 密码配置文件
- `devices/*.xlsx` - 设备数据文件（包含真实设备信息）
- `output/` - 输出目录（日志和结果文件）

### 已提交的示例文件

- `config/password_example.conf` - 密码配置示例
- `devices/devices_example.xlsx` - 设备表示例

## 常见问题

### 1. SSH连接失败

- 确认设备IP地址是否正确
- 确认设备SSH服务已开启（端口22）
- 确认网络连通性
- 确认用户名和密码正确

### 2. 编码问题

程序已修复Unicode编码问题，使用 `[OK]`、`[FAIL]` 等ASCII字符替代Unicode符号。

### 3. Web模式卡住

已添加 `--yes` 参数，Web模式会自动添加该参数跳过交互式确认。

## 更多信息

详细文档请参考 `doc/` 目录下的文件。
