#!/usr/bin/env python3
"""
子网扫描模块
Subnet Scanner Module

扫描指定子网段，发现存活网络设备并识别厂商。
"""

import ipaddress
import logging
import platform
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Set

from .discovery_models import DiscoveredDevice, DiscoveryResult
from .device_prober import DeviceProber

logger = logging.getLogger(__name__)


class SubnetScanner:
    """子网扫描器"""

    def __init__(self, config: Dict[str, Any], passwords: Dict[str, Dict[str, str]]):
        """
        初始化子网扫描器。

        Args:
            config: 全局配置字典
            passwords: 凭证字典
        """
        self.config = config
        self.passwords = passwords
        self.scan_config = config.get("discovery", {}).get("subnet_scan", {})
        self.ping_timeout = self.scan_config.get("ping_timeout", 1)
        self.ping_count = self.scan_config.get("ping_count", 1)
        self.ssh_timeout = self.scan_config.get("ssh_timeout", 3)
        self.ssh_ports = self.scan_config.get("ssh_ports", [22])
        self.max_workers = self.scan_config.get("max_workers", 50)
        self.try_ssh_login = self.scan_config.get("try_ssh_login", True)
        self.prober = DeviceProber(config, passwords)

    def scan(
        self,
        subnets: List[str],
        exclude_ips: Optional[Set[str]] = None,
        dry_run: bool = False,
        progress_callback=None,
    ) -> DiscoveryResult:
        """
        扫描指定的子网段。

        Args:
            subnets: CIDR 格式的子网列表，如 ["192.168.1.0/24"]
            exclude_ips: 排除的IP集合
            dry_run: 仅探测可达性，不尝试SSH登录
            progress_callback: 进度回调函数

        Returns:
            DiscoveryResult
        """
        start_time = time.time()
        result = DiscoveryResult()
        exclude_ips = exclude_ips or set()

        # 展开所有子网为IP列表
        all_ips = self._expand_subnets(subnets)
        if not all_ips:
            result.errors.append("未提供有效的子网或网段")
            result.scan_duration = time.time() - start_time
            return result

        # 过滤排除IP
        scan_ips = [ip for ip in all_ips if ip not in exclude_ips]
        self._log_progress(
            progress_callback,
            f"[子网扫描] 共 {len(all_ips)} 个IP，排除 {len(all_ips) - len(scan_ips)} 个已知IP，"
            f"待扫描 {len(scan_ips)} 个"
        )

        # 第一阶段：ICMP Ping 探测存活主机
        self._log_progress(progress_callback, "[子网扫描] 阶段1/3: ICMP Ping 探测...")
        alive_ips = self._ping_scan(scan_ips, progress_callback)
        self._log_progress(
            progress_callback,
            f"[子网扫描] Ping 存活: {len(alive_ips)}/{len(scan_ips)}"
        )

        if not alive_ips:
            self._log_progress(progress_callback, "[子网扫描] 未发现存活主机")
            result.scan_duration = time.time() - start_time
            return result

        # 第二阶段：SSH 端口探测
        self._log_progress(progress_callback, "[子网扫描] 阶段2/3: SSH 端口探测...")
        ssh_reachable = self._ssh_port_scan(alive_ips, progress_callback)
        self._log_progress(
            progress_callback,
            f"[子网扫描] SSH 可达: {len(ssh_reachable)}/{len(alive_ips)}"
        )

        if not ssh_reachable:
            self._log_progress(progress_callback, "[子网扫描] 未发现SSH可达设备")
            # Ping 存活但 SSH 不可达的主机也记录（供参考）
            for ip in alive_ips:
                device = DiscoveredDevice(
                    ip=ip,
                    source="subnet_scan",
                    source_device=",".join(subnets),
                    ssh_reachable=False,
                    identified=False,
                )
                result.devices.append(device)
            result.scan_duration = time.time() - start_time
            return result

        # 第三阶段：SSH 登录识别厂商（如果不是 dry_run 模式）
        if dry_run or not self.try_ssh_login:
            self._log_progress(
                progress_callback,
                "[子网扫描] 跳过SSH登录识别 (dry_run 或未启用)"
            )
            for ip, port in ssh_reachable:
                device = DiscoveredDevice(
                    ip=ip,
                    ssh_port=port,
                    source="subnet_scan",
                    source_device=",".join(subnets),
                    ssh_reachable=True,
                    identified=False,
                )
                result.devices.append(device)
        else:
            self._log_progress(progress_callback, "[子网扫描] 阶段3/3: SSH 登录识别厂商...")
            identified_devices = self._identify_devices(ssh_reachable, progress_callback)
            result.devices.extend(identified_devices)

        result.scan_duration = time.time() - start_time
        self._log_progress(
            progress_callback,
            f"[子网扫描] 完成，共发现 {result.total_found} 台设备，"
            f"其中 {sum(1 for d in result.devices if d.identified)} 台已识别，"
            f"耗时 {result.scan_duration:.1f}s"
        )
        return result

    def _expand_subnets(self, subnets: List[str]) -> List[str]:
        """
        将 CIDR 子网展开为 IP 地址列表。

        Args:
            subnets: CIDR 格式子网列表

        Returns:
            IP地址字符串列表
        """
        all_ips = []

        for subnet_str in subnets:
            subnet_str = subnet_str.strip()
            if not subnet_str:
                continue

            try:
                # 支持单IP和CIDR格式
                if "/" in subnet_str:
                    network = ipaddress.ip_network(subnet_str, strict=False)
                    # 排除网络地址和广播地址
                    ips = [str(ip) for ip in network.hosts()]
                else:
                    # 单个IP
                    ipaddress.ip_address(subnet_str)  # 验证格式
                    ips = [subnet_str]

                all_ips.extend(ips)
                logger.info("子网 %s 展开 %d 个IP", subnet_str, len(ips))

            except ValueError as e:
                logger.warning("无效的子网格式: %s (%s)", subnet_str, e)

        return all_ips

    def _ping_scan(
        self, ips: List[str], progress_callback=None
    ) -> List[str]:
        """
        并发 ICMP Ping 扫描。

        Args:
            ips: 待扫描的IP列表

        Returns:
            存活的IP列表
        """
        alive_ips = []
        total = len(ips)
        completed = 0

        # Ping 扫描使用较高并发数
        ping_workers = min(self.max_workers, len(ips))

        with ThreadPoolExecutor(max_workers=ping_workers) as executor:
            future_to_ip = {
                executor.submit(self._ping_single, ip): ip for ip in ips
            }

            for future in as_completed(future_to_ip):
                ip = future_to_ip[future]
                completed += 1

                if completed % 50 == 0 or completed == total:
                    self._log_progress(
                        progress_callback,
                        f"\r  Ping 进度: {completed}/{total} ({completed / total * 100:.1f}%)",
                    )

                try:
                    if future.result():
                        alive_ips.append(ip)
                except Exception:
                    pass

        return alive_ips

    def _ping_single(self, ip: str) -> bool:
        """
        对单个IP执行 ICMP Ping。

        Args:
            ip: 目标IP

        Returns:
            是否存活
        """
        system = platform.system().lower()

        if system == "windows":
            cmd = [
                "ping", "-n", str(self.ping_count),
                "-w", str(self.ping_timeout * 1000), ip
            ]
        else:
            cmd = [
                "ping", "-c", str(self.ping_count),
                "-W", str(self.ping_timeout), ip
            ]

        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=self.ping_timeout + 2,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _ssh_port_scan(
        self, ips: List[str], progress_callback=None
    ) -> List[tuple]:
        """
        并发 SSH 端口扫描。

        Args:
            ips: 待扫描的IP列表

        Returns:
            [(ip, port), ...] SSH端口开放的设备列表
        """
        reachable = []
        total = len(ips)
        completed = 0

        # 构建 (ip, port) 任务列表
        tasks = [(ip, port) for ip in ips for port in self.ssh_ports]
        scan_workers = min(self.max_workers, len(tasks))

        with ThreadPoolExecutor(max_workers=scan_workers) as executor:
            future_to_task = {
                executor.submit(
                    self.prober.check_ssh_port, ip, port, self.ssh_timeout
                ): (ip, port)
                for ip, port in tasks
            }

            for future in as_completed(future_to_task):
                ip, port = future_to_task[future]
                completed += 1

                if completed % 20 == 0 or completed == len(tasks):
                    self._log_progress(
                        progress_callback,
                        f"\r  SSH探测进度: {completed}/{len(tasks)}",
                    )

                try:
                    if future.result():
                        reachable.append((ip, port))
                except Exception:
                    pass

        return reachable

    def _identify_devices(
        self, ssh_reachable: List[tuple], progress_callback=None
    ) -> List[DiscoveredDevice]:
        """
        对 SSH 可达设备进行登录和厂商识别。

        Args:
            ssh_reachable: [(ip, port), ...]

        Returns:
            已识别的设备列表
        """
        devices = []
        total = len(ssh_reachable)
        completed = 0

        # 识别阶段使用较低并发（SSH登录较重）
        identify_workers = min(10, total)

        with ThreadPoolExecutor(max_workers=identify_workers) as executor:
            future_to_ip = {
                executor.submit(self.prober.probe_device, ip, port): (ip, port)
                for ip, port in ssh_reachable
            }

            for future in as_completed(future_to_ip):
                ip, port = future_to_ip[future]
                completed += 1

                if completed % 5 == 0 or completed == total:
                    self._log_progress(
                        progress_callback,
                        f"\r  识别进度: {completed}/{total} "
                        f"(已识别: {sum(1 for d in devices if d.identified)})",
                    )

                try:
                    device = future.result()
                    device.source = "subnet_scan"
                    device.source_device = "子网扫描"
                    devices.append(device)
                except Exception as e:
                    logger.debug("识别设备 %s 失败: %s", ip, e)
                    # 记录为未识别设备
                    device = DiscoveredDevice(
                        ip=ip,
                        ssh_port=port,
                        ssh_reachable=True,
                        identified=False,
                        source="subnet_scan",
                        source_device="子网扫描",
                    )
                    devices.append(device)

        return devices

    @staticmethod
    def _log_progress(callback, message: str):
        """输出进度信息"""
        logger.info(message)
        if callback:
            callback(message)
