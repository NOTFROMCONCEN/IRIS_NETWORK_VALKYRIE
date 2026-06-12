#!/usr/bin/env python3
"""
设备发现数据模型
Device Discovery Data Models

定义设备发现过程中使用的核心数据结构。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class DiscoveredDevice:
    """发现的设备信息"""

    # ---- 基础网络信息 ----
    ip: str = ""                             # 发现时的IP地址
    hostname: str = ""                       # 设备主机名
    ssh_port: int = 22                       # SSH端口
    mac_address: str = ""                    # MAC地址

    # ---- 厂商与型号 ----
    vendor: str = ""                         # 标准化厂商名 (huawei/h3c/cisco/ruijie/maipu/wst/unknown)
    vendor_raw: str = ""                     # 原始厂商信息字符串
    model: str = ""                          # 设备型号
    device_type: str = ""                    # 设备类型 (交换机/路由器/防火墙/未知)

    # ---- 管理地址 ----
    management_ip: str = ""                  # 管理IP (可能与发现IP不同)

    # ---- 发现来源信息 ----
    source: str = ""                         # 发现来源: lldp / cdp / subnet_scan
    source_device: str = ""                  # 从哪台设备发现的 (种子设备IP或网段)
    source_interface: str = ""               # 通过哪个接口发现的

    # ---- 状态标记 ----
    ssh_reachable: bool = False              # SSH端口是否可达
    identified: bool = False                 # 是否成功识别厂商
    already_in_inventory: bool = False       # 是否已在设备清单中

    # ---- 其他信息 ----
    remarks: str = ""                        # 备注

    @property
    def display_ip(self) -> str:
        """用于显示的IP地址（优先使用管理IP）"""
        return self.management_ip or self.ip

    @property
    def display_name(self) -> str:
        """用于显示的设备名称"""
        return self.hostname or f"Discovered_{self.ip}"

    def to_inventory_dict(self) -> Dict[str, str]:
        """转换为设备清单格式，用于导入到 devices.xlsx"""
        return {
            "设备名": self.display_name,
            "IP地址": self.display_ip,
            "生产厂商": self.vendor_raw or self.vendor or "unknown",
            "端口": str(self.ssh_port),
            "备注": self.remarks or f"自动发现({self.source}) via {self.source_device}",
        }

    def enrichment_score(self) -> int:
        """计算设备信息完整度分数，用于去重时选择最佳记录"""
        score = 0
        if self.hostname:
            score += 2
        if self.vendor and self.vendor != "unknown":
            score += 3
        if self.model:
            score += 2
        if self.ssh_reachable:
            score += 1
        if self.mac_address:
            score += 1
        if self.source == "lldp" or self.source == "cdp":
            score += 1  # LLDP 信息通常更准确
        return score


@dataclass
class DiscoveryResult:
    """发现任务结果"""

    devices: List[DiscoveredDevice] = field(default_factory=list)
    duplicates_removed: int = 0              # 去重移除的数量
    already_in_inventory: int = 0            # 已在设备清单中的数量
    scan_duration: float = 0.0               # 扫描耗时 (秒)
    errors: List[str] = field(default_factory=list)  # 错误信息列表

    @property
    def new_devices(self) -> List[DiscoveredDevice]:
        """不在现有清单中且已识别的新设备"""
        return [
            d for d in self.devices
            if d.identified and not d.already_in_inventory
        ]

    @property
    def total_found(self) -> int:
        """发现的总设备数"""
        return len(self.devices)

    def to_table_data(self) -> List[Dict[str, Any]]:
        """转换为表格展示数据"""
        rows = []
        for i, device in enumerate(self.devices):
            rows.append({
                "序号": i + 1,
                "IP地址": device.display_ip,
                "主机名": device.hostname or "-",
                "厂商": device.vendor_raw or device.vendor or "unknown",
                "型号": device.model or "-",
                "来源": device.source,
                "发现自": device.source_device,
                "SSH状态": "✅" if device.ssh_reachable else "❌",
                "已识别": "是" if device.identified else "否",
                "已在清单": "是" if device.already_in_inventory else "否",
            })
        return rows
