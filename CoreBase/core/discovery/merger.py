#!/usr/bin/env python3
"""
发现结果去重与合并模块
Discovery Result Merger Module

对多种来源的设备发现结果进行去重和合并。
"""

import logging
from typing import Dict, List, Optional, Set

from .discovery_models import DiscoveredDevice, DiscoveryResult

logger = logging.getLogger(__name__)


class DiscoveryResultMerger:
    """发现结果去重与合并"""

    def merge(
        self,
        results: List[DiscoveryResult],
        existing_ips: Optional[Set[str]] = None,
    ) -> DiscoveryResult:
        """
        合并多个发现结果，自动去重。

        去重规则:
        1. 主键: IP地址 (management_ip 优先于 discovery_ip)
        2. 同一IP多次发现时，信息更完整的记录优先
        3. 优先级: 已SSH识别 > 未识别; lldp/cdp来源 > subnet来源
        4. 标记已在现有清单中的设备

        Args:
            results: 多个发现结果列表
            existing_ips: 现有设备清单中的IP集合

        Returns:
            合并后的 DiscoveryResult
        """
        merged = DiscoveryResult()
        existing_ips = existing_ips or set()

        # 收集所有设备
        all_devices: List[DiscoveredDevice] = []
        total_errors: List[str] = []
        total_duration = 0.0
        total_duplicates = 0

        for result in results:
            all_devices.extend(result.devices)
            total_errors.extend(result.errors)
            total_duration += result.scan_duration
            total_duplicates += result.duplicates_removed

        # 去重
        unique_devices = self._deduplicate(all_devices)
        merged.duplicates_removed = total_duplicates + (
            len(all_devices) - len(unique_devices)
        )

        # 标记已在清单中的设备
        inventory_count = 0
        for device in unique_devices:
            display_ip = device.display_ip
            if display_ip in existing_ips or device.ip in existing_ips:
                device.already_in_inventory = True
                inventory_count += 1

        merged.devices = unique_devices
        merged.already_in_inventory = inventory_count
        merged.errors = total_errors
        merged.scan_duration = total_duration

        logger.info(
            "合并完成: 共 %d 台设备，去重 %d 台，已在清单 %d 台",
            len(unique_devices),
            merged.duplicates_removed,
            inventory_count,
        )

        return merged

    def _deduplicate(
        self, devices: List[DiscoveredDevice]
    ) -> List[DiscoveredDevice]:
        """
        基于 IP 去重，保留信息最丰富的记录。

        Args:
            devices: 待去重的设备列表

        Returns:
            去重后的设备列表
        """
        ip_map: Dict[str, DiscoveredDevice] = {}

        for device in devices:
            # 使用管理IP（如果有）或发现IP作为主键
            key = device.management_ip or device.ip

            if not key:
                # 没有IP的设备，使用主机名作为备选
                key = device.hostname or ""

            if not key:
                continue

            if key not in ip_map:
                ip_map[key] = device
            else:
                # 已存在，选择信息更丰富的记录
                existing = ip_map[key]
                if device.enrichment_score() > existing.enrichment_score():
                    ip_map[key] = device
                    logger.debug(
                        "去重替换: %s (新分数 %d > 旧分数 %d)",
                        key,
                        device.enrichment_score(),
                        existing.enrichment_score(),
                    )

        return list(ip_map.values())
