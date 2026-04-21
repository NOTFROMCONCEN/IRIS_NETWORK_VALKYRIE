# 配置文件说明

## 配置文件列表

- `config.yaml` - 主配置文件（已提交到Git）
- `password.conf` - 密码配置文件（已添加到.gitignore，不会提交）
- `password_example.conf` - 密码配置示例文件

## 快速开始

### 1. 配置密码文件

复制示例密码文件并填入真实密码：

```bash
# Windows
copy password_example.conf password.conf

# Linux/Mac
cp password_example.conf password.conf
```

然后编辑 `password.conf`，填入真实的设备密码。

### 2. 配置设备列表

设备列表文件位于 `devices/devices.xlsx`，请参考 `devices/devices_example.xlsx` 示例文件创建。

设备表格式：

| 列名 | 必填 | 说明 |
|------|------|------|
| 设备名 | 是 | 设备名称，建议使用有意义的名称 |
| IP地址 | 是 | 设备的IP地址 |
| 厂商 | 是 | 设备厂商：huawei, h3c, ruijie, maipu, wst, cisco |
| 端口 | 否 | SSH端口，默认22 |
| 设备型号 | 否 | 设备型号 |
| 位置 | 否 | 设备物理位置 |
| 联系人 | 否 | 设备联系人 |
| 备注 | 否 | 其他备注信息 |

### 3. 修改主配置

编辑 `config.yaml` 根据需要调整以下配置：

- 日志级别和输出目录
- 网络连接超时时间
- 巡检命令列表
- 通知设置

## 安全注意事项

- `password.conf` 文件包含敏感信息，已添加到 `.gitignore`，不会提交到Git
- 请妥善保管密码文件，不要将其分享给未授权人员
- 建议定期更换设备密码
