#!/usr/bin/env python3
"""
创建设备表示例文件
"""

import pandas as pd
from pathlib import Path

# 示例设备数据
example_devices = [
    {
        "设备名": "Core-SW-01",
        "IP地址": "192.168.1.1",
        "厂商": "huawei",
        "端口": 22,
        "设备型号": "S5720-52X-SI",
        "位置": "机房A-机架1",
        "联系人": "网络管理员",
        "备注": "核心交换机"
    },
    {
        "设备名": "Core-SW-02",
        "IP地址": "192.168.1.2",
        "厂商": "h3c",
        "端口": 22,
        "设备型号": "S5130S-28S-HPWR-EI",
        "位置": "机房A-机架2",
        "联系人": "网络管理员",
        "备注": "核心交换机"
    },
    {
        "设备名": "Access-SW-01",
        "IP地址": "192.168.10.1",
        "厂商": "ruijie",
        "端口": 22,
        "设备型号": "RG-S5760C-48GT4XS-X",
        "位置": "机房B-机架1",
        "联系人": "网络管理员",
        "备注": "接入交换机"
    },
    {
        "设备名": "Access-SW-02",
        "IP地址": "192.168.10.2",
        "厂商": "ruijie",
        "端口": 22,
        "设备型号": "RG-S5760C-48GT4XS-X",
        "位置": "机房B-机架2",
        "联系人": "网络管理员",
        "备注": "接入交换机"
    },
    {
        "设备名": "Firewall-01",
        "IP地址": "192.168.100.1",
        "厂商": "wst",
        "端口": 22,
        "设备型号": "WST-6000",
        "位置": "机房A-机架10",
        "联系人": "安全管理员",
        "备注": "防火墙"
    }
]

# 创建 DataFrame
df = pd.DataFrame(example_devices)

# 保存为 Excel 文件
output_dir = Path(__file__).parent.parent / "devices"
output_dir.mkdir(exist_ok=True)

output_file = output_dir / "devices_example.xlsx"
df.to_excel(output_file, index=False, engine='openpyxl')

print(f"示例设备表已创建: {output_file}")
print(f"包含 {len(example_devices)} 台示例设备")
print("\n设备列表:")
for device in example_devices:
    print(f"  - {device['设备名']} ({device['IP地址']}) - {device['厂商']}")
