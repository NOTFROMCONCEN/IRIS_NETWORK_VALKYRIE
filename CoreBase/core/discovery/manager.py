#!/usr/bin/env python3
"""
设备发现管理器
Discovery Manager Module

编排完整的设备发现流程，支持 LLDP/CDP 邻居发现、子网扫描和组合发现。
"""

import logging
import time
from typing import Dict, List, Any, Optional, Set, Callable

from .discovery_models import DiscoveredDevice, DiscoveryResult
from .lldp_discovery import LLDPNeighborDiscovery
from .subnet_scanner import SubnetScanner
from .merger import DiscoveryResultMerger

logger = logging.getLogger(__name__)


class DiscoveryManager:
    """设备发现管理器 — 编排发现流程"""

    def __init__(
        self,
        config: Dict[str, Any],
        passwords: Dict[str, Dict[str, str]],
    ):
        """
        初始化发现管理器。

        Args:
            config: 全局配置字典
            passwords: 凭证字典 {vendor: {'username': ..., 'password': ...}}
        """
        self.config = config
        self.passwords = passwords
        self.lldp = LLDPNeighborDiscovery(config, passwords)
        self.scanner = SubnetScanner(config, passwords)
        self.merger = DiscoveryResultMerger()

    def discover_from_seeds(
        self,
        seed_devices: List[Dict[str, Any]],
        max_depth: Optional[int] = None,
        exclude_ips: Optional[Set[str]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> DiscoveryResult:
        """
        从种子设备通过 LLDP/CDP 发现邻居。

        Args:
            seed_devices: 种子设备列表，每个元素需包含:
                ip, vendor, username, password, port(可选), jump_host(可选) 等
            max_depth: 递归深度 (None 则使用配置值)
            exclude_ips: 排除的IP集合
            progress_callback: 进度回调

        Returns:
            DiscoveryResult
        """
        if max_depth is not None:
            original_depth = self.lldp.max_depth
            self.lldp.max_depth = max_depth

        try:
            return self.lldp.discover(
                seed_devices,
                exclude_ips=exclude_ips,
                progress_callback=progress_callback,
            )
        finally:
            if max_depth is not None:
                self.lldp.max_depth = original_depth

    def scan_subnets(
        self,
        subnets: List[str],
        exclude_ips: Optional[Set[str]] = None,
        dry_run: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> DiscoveryResult:
        """
        扫描指定子网。

        Args:
            subnets: CIDR 格式子网列表
            exclude_ips: 排除的IP集合
            dry_run: 仅探测可达性
            progress_callback: 进度回调

        Returns:
            DiscoveryResult
        """
        return self.scanner.scan(
            subnets,
            exclude_ips=exclude_ips,
            dry_run=dry_run,
            progress_callback=progress_callback,
        )

    def combined_discover(
        self,
        seed_devices: List[Dict[str, Any]],
        subnets: List[str],
        max_depth: Optional[int] = None,
        exclude_ips: Optional[Set[str]] = None,
        dry_run: bool = False,
        progress_callback: Optional[Callable] = None,
    ) -> DiscoveryResult:
        """
        组合发现: LLDP邻居 + 子网扫描，自动去重。

        Args:
            seed_devices: 种子设备列表
            subnets: 子网列表
            max_depth: LLDP递归深度
            exclude_ips: 排除的IP集合
            dry_run: 仅探测可达性
            progress_callback: 进度回调

        Returns:
            合并后的 DiscoveryResult
        """
        results = []

        # LLDP 发现
        if seed_devices:
            self._log_progress(progress_callback, "[组合发现] 开始 LLDP/CDP 邻居发现...")
            lldp_result = self.discover_from_seeds(
                seed_devices,
                max_depth=max_depth,
                exclude_ips=exclude_ips,
                progress_callback=progress_callback,
            )
            results.append(lldp_result)
            self._log_progress(
                progress_callback,
                f"[组合发现] LLDP 发现 {lldp_result.total_found} 台设备"
            )

        # 子网扫描
        if subnets:
            self._log_progress(progress_callback, "[组合发现] 开始子网扫描...")
            subnet_result = self.scan_subnets(
                subnets,
                exclude_ips=exclude_ips,
                dry_run=dry_run,
                progress_callback=progress_callback,
            )
            results.append(subnet_result)
            self._log_progress(
                progress_callback,
                f"[组合发现] 子网扫描发现 {subnet_result.total_found} 台设备"
            )

        if not results:
            return DiscoveryResult()

        # 合并去重
        self._log_progress(progress_callback, "[组合发现] 合并去重...")
        merged = self.merger.merge(results, existing_ips=exclude_ips)

        self._log_progress(
            progress_callback,
            f"[组合发现] 完成: 总计 {merged.total_found} 台设备，"
            f"去重 {merged.duplicates_removed} 台，"
            f"已识别 {sum(1 for d in merged.devices if d.identified)} 台，"
            f"已在清单 {merged.already_in_inventory} 台"
        )

        return merged

    def get_device_credentials(self, vendor: str) -> Optional[Dict[str, str]]:
        """
        根据厂商获取凭证。

        Args:
            vendor: 厂商名

        Returns:
            {'username': ..., 'password': ...} 或 None
        """
        return self.passwords.get(vendor) or self.passwords.get("default")

    @staticmethod
    def _log_progress(callback, message: str):
        """输出进度信息"""
        logger.info(message)
        if callback:
            callback(message)
