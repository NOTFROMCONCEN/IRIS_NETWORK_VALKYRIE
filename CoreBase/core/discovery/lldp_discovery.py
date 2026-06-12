#!/usr/bin/env python3
"""
LLDP/CDP 邻居发现模块
LLDP/CDP Neighbor Discovery Module

从种子设备通过 LLDP/CDP 协议发现邻居网络设备，支持递归发现。
"""

import logging
import time
import re
from typing import Dict, List, Any, Optional, Set

from .discovery_models import DiscoveredDevice, DiscoveryResult
from .vendor_identifier import VendorIdentifier

logger = logging.getLogger(__name__)


class LLDPNeighborDiscovery:
    """LLDP/CDP 邻居发现"""

    # 各厂商的 LLDP/CDP 命令
    LLDP_COMMANDS = {
        "huawei": {
            "lldp_neighbor": "display lldp neighbor brief",
            "lldp_detail": "display lldp neighbor",
        },
        "h3c": {
            "lldp_neighbor": "display lldp neighbor-information list",
            "lldp_detail": "display lldp neighbor-information",
        },
        "cisco": {
            "lldp_neighbor": "show lldp neighbors",
            "lldp_detail": "show lldp neighbors detail",
            "cdp_neighbor": "show cdp neighbors",
            "cdp_detail": "show cdp neighbors detail",
        },
        "ruijie": {
            "lldp_neighbor": "show lldp neighbors",
            "lldp_detail": "show lldp neighbors detail",
        },
        "maipu": {
            "lldp_neighbor": "show lldp neighbors",
        },
    }

    def __init__(self, config: Dict[str, Any], passwords: Dict[str, Dict[str, str]]):
        """
        初始化 LLDP 发现器。

        Args:
            config: 全局配置字典
            passwords: 凭证字典
        """
        self.config = config
        self.passwords = passwords
        self.lldp_config = config.get("discovery", {}).get("lldp", {})
        self.max_depth = self.lldp_config.get("max_depth", 3)
        self.max_devices = self.lldp_config.get("max_devices", 200)
        self.timeout_per_device = self.lldp_config.get("timeout_per_device", 30)
        self.use_cdp = self.lldp_config.get("use_cdp", True)
        self.max_workers = self.lldp_config.get("max_workers", 5)

    def discover(
        self,
        seed_devices: List[Dict[str, Any]],
        exclude_ips: Optional[Set[str]] = None,
        progress_callback=None,
    ) -> DiscoveryResult:
        """
        从种子设备通过 LLDP/CDP 递归发现邻居设备。

        Args:
            seed_devices: 种子设备列表，每个元素需包含 ip, vendor, username, password
            exclude_ips: 排除的IP集合（已知的设备IP）
            progress_callback: 进度回调函数 callback(message: str)

        Returns:
            DiscoveryResult
        """
        start_time = time.time()
        result = DiscoveryResult()
        exclude_ips = exclude_ips or set()

        # 已处理的IP集合（避免重复处理）
        processed_ips: Set[str] = set()
        # 当前层的种子设备
        current_seeds = list(seed_devices)
        # 种子设备IP加入排除集
        for seed in seed_devices:
            seed_ip = seed.get("ip", "")
            if seed_ip:
                exclude_ips.add(seed_ip)

        for depth in range(1, self.max_depth + 1):
            if not current_seeds:
                break

            if len(result.devices) >= self.max_devices:
                msg = f"已达到最大发现设备数限制 ({self.max_devices})，停止递归"
                result.errors.append(msg)
                logger.warning(msg)
                break

            self._log_progress(progress_callback, 
                f"[LLDP发现] 第 {depth}/{self.max_depth} 层，处理 {len(current_seeds)} 台种子设备..."
            )

            next_seeds = []
            for seed in current_seeds:
                seed_ip = seed.get("ip", "")

                if seed_ip in processed_ips:
                    continue
                processed_ips.add(seed_ip)

                if len(result.devices) >= self.max_devices:
                    break

                # 发现该设备的邻居
                neighbors = self._discover_neighbors_from_device(seed)

                for neighbor in neighbors:
                    neighbor_ip = neighbor.display_ip

                    # 跳过排除的IP
                    if neighbor_ip in exclude_ips:
                        neighbor.already_in_inventory = True
                        result.already_in_inventory += 1
                        continue

                    # 跳过已处理的IP
                    if neighbor_ip in processed_ips:
                        continue

                    # 检查是否已发现
                    existing_ips = {d.display_ip for d in result.devices}
                    if neighbor_ip in existing_ips:
                        result.duplicates_removed += 1
                        continue

                    result.devices.append(neighbor)
                    self._log_progress(progress_callback,
                        f"  发现邻居: {neighbor_ip} ({neighbor.hostname or '?'}) "
                        f"厂商={neighbor.vendor or '?'} 来源={neighbor.source}"
                    )

                    # 如果邻居已识别且有凭证，加入下一层的种子
                    if neighbor.identified and neighbor_ip not in exclude_ips:
                        next_seed = self._neighbor_to_seed(neighbor)
                        if next_seed:
                            next_seeds.append(next_seed)

            current_seeds = next_seeds

        result.scan_duration = time.time() - start_time
        self._log_progress(progress_callback,
            f"[LLDP发现] 完成，共发现 {result.total_found} 台设备，耗时 {result.scan_duration:.1f}s"
        )
        return result

    def _discover_neighbors_from_device(
        self, seed_device: Dict[str, Any]
    ) -> List[DiscoveredDevice]:
        """
        从单台种子设备发现其 LLDP/CDP 邻居。

        Args:
            seed_device: 种子设备信息

        Returns:
            发现的邻居设备列表
        """
        seed_ip = seed_device.get("ip", "")
        vendor = seed_device.get("vendor", "").lower()
        username = seed_device.get("username", "")
        password = seed_device.get("password", "")
        port = seed_device.get("port", 22)

        if not all([seed_ip, username, password]):
            logger.debug("种子设备缺少必要凭证信息: %s", seed_ip)
            return []

        neighbors = []
        connection = None

        try:
            from netmiko import ConnectHandler
            from netmiko.exceptions import (
                NetmikoTimeoutException,
                NetmikoAuthenticationException,
            )
        except ImportError:
            logger.error("缺少 netmiko 模块")
            return []

        try:
            # 获取对应的 netmiko device_type
            device_type_map = {
                "huawei": "huawei",
                "h3c": "hp_comware",
                "cisco": "cisco_ios",
                "ruijie": "ruijie_os",
                "maipu": "generic",
            }
            device_type = device_type_map.get(vendor, "autodetect")

            connect_params = {
                "device_type": device_type,
                "host": seed_ip,
                "username": username,
                "password": password,
                "port": port,
                "timeout": self.timeout_per_device,
                "session_timeout": self.timeout_per_device,
            }

            # 处理跳板机
            jump_host = seed_device.get("jump_host")
            if jump_host:
                connection = self._connect_via_jump_host(connect_params, seed_device)
            else:
                connection = ConnectHandler(**connect_params)

            if not connection:
                return []

            # 获取 LLDP 命令
            lldp_cmds = self.LLDP_COMMANDS.get(vendor, {})
            if not lldp_cmds:
                logger.debug("厂商 %s 不支持 LLDP 发现", vendor)
                return []

            # 执行 LLDP 命令
            lldp_cmd = lldp_cmds.get("lldp_neighbor")
            if lldp_cmd:
                try:
                    lldp_output = connection.send_command(
                        lldp_cmd,
                        read_timeout=self.timeout_per_device,
                        strip_prompt=True,
                        strip_command=True,
                    )
                    if lldp_output:
                        lldp_neighbors = self._parse_lldp_output(
                            vendor, lldp_output, seed_ip
                        )
                        neighbors.extend(lldp_neighbors)
                except Exception as e:
                    logger.debug("执行 LLDP 命令失败 (%s): %s", lldp_cmd, e)

            # 执行 CDP 命令（如果启用且厂商支持）
            if self.use_cdp and "cdp_neighbor" in lldp_cmds:
                cdp_cmd = lldp_cmds.get("cdp_neighbor")
                if cdp_cmd:
                    try:
                        cdp_output = connection.send_command(
                            cdp_cmd,
                            read_timeout=self.timeout_per_device,
                            strip_prompt=True,
                            strip_command=True,
                        )
                        if cdp_output:
                            cdp_neighbors = self._parse_cdp_output(
                                cdp_output, seed_ip
                            )
                            neighbors.extend(cdp_neighbors)
                    except Exception as e:
                        logger.debug("执行 CDP 命令失败 (%s): %s", cdp_cmd, e)

        except NetmikoAuthenticationException:
            logger.debug("种子设备 %s 认证失败", seed_ip)
        except NetmikoTimeoutException:
            logger.debug("种子设备 %s 连接超时", seed_ip)
        except Exception as e:
            logger.debug("种子设备 %s 连接异常: %s", seed_ip, e)
        finally:
            if connection:
                try:
                    connection.disconnect()
                except Exception:
                    pass

        return neighbors

    # ============================================================
    # LLDP 输出解析
    # ============================================================

    def _parse_lldp_output(
        self, vendor: str, output: str, source_ip: str
    ) -> List[DiscoveredDevice]:
        """
        根据厂商类型选择对应的 LLDP 输出解析器。

        Args:
            vendor: 厂商名
            output: LLDP 命令输出
            source_ip: 来源设备IP

        Returns:
            发现的邻居设备列表
        """
        parsers = {
            "huawei": self._parse_huawei_lldp,
            "h3c": self._parse_h3c_lldp,
            "cisco": self._parse_cisco_lldp,
            "ruijie": self._parse_ruijie_lldp,
        }
        parser = parsers.get(vendor)
        if parser:
            return parser(output, source_ip)
        return []

    def _parse_huawei_lldp(self, output: str, source_ip: str) -> List[DiscoveredDevice]:
        """
        解析华为 LLDP 输出。

        典型格式 (display lldp neighbor brief):
        ----------------------------------------------------------------------
        Local Intf   Neighbor Dev         Neighbor Intf        Neighbor IP
        ----------------------------------------------------------------------
        GE1/0/1      SW-Access-01         GE1/0/1              192.168.1.2
        GE1/0/2      SW-Core-02           10GE1/0/1            10.0.0.2
        """
        devices = []

        # 尝试解析表格式输出
        lines = output.strip().splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("-") or line.startswith("Local"):
                continue

            # 尝试提取IP地址
            ip_match = re.search(
                r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line
            )
            if not ip_match:
                continue

            ip = ip_match.group(1)
            parts = line.split()

            # 提取本地接口和邻居名称
            local_intf = parts[0] if parts else ""
            neighbor_name = parts[1] if len(parts) > 1 else ""
            neighbor_intf = parts[2] if len(parts) > 2 else ""

            device = DiscoveredDevice(
                ip=ip,
                hostname=neighbor_name,
                source="lldp",
                source_device=source_ip,
                source_interface=local_intf,
                ssh_reachable=True,  # LLDP 能发现说明链路可达
            )
            devices.append(device)

        return devices

    def _parse_h3c_lldp(self, output: str, source_ip: str) -> List[DiscoveredDevice]:
        """
        解析 H3C LLDP 输出。

        典型格式 (display lldp neighbor-information list):
        ----------------------------------------------------------------------
        Local Interface  Neighbor Interface  Neighbor Device    Neighbor IP
        ----------------------------------------------------------------------
        GE1/0/1          GE1/0/1             SW-Access-01       192.168.1.2
        """
        devices = []
        lines = output.strip().splitlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith("-") or line.startswith("Local"):
                continue

            ip_match = re.search(
                r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line
            )
            if not ip_match:
                continue

            ip = ip_match.group(1)
            parts = line.split()
            local_intf = parts[0] if parts else ""
            neighbor_name = parts[2] if len(parts) > 2 else ""

            device = DiscoveredDevice(
                ip=ip,
                hostname=neighbor_name,
                source="lldp",
                source_device=source_ip,
                source_interface=local_intf,
                ssh_reachable=True,
            )
            devices.append(device)

        return devices

    def _parse_cisco_lldp(self, output: str, source_ip: str) -> List[DiscoveredDevice]:
        """
        解析 Cisco LLDP 输出。

        典型格式 (show lldp neighbors):
        Device ID           Local Intf     Hold-time  Capability  Port ID
        SW-ACCESS-01        Gi0/1         120        B,R         Gi0/1

        以及 (show lldp neighbors detail):
        ------------------------------------------------
        Chassis id: aabb.cc00.1000
        Port id: Gi0/1
        Port Description: GigabitEthernet0/1
        System Name: SW-ACCESS-01
        System Description: ...
        Management Addresses:
            IP: 192.168.1.2
        """
        devices = []

        # 先尝试解析 detail 格式（信息更丰富）
        if "Management Addresses" in output or "Chassis id" in output:
            devices = self._parse_cisco_lldp_detail(output, source_ip)
        else:
            # 解析简表格式
            lines = output.strip().splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("Device") or line.startswith("-"):
                    continue

                parts = line.split()
                if len(parts) >= 5:
                    device_name = parts[0]
                    local_intf = parts[1]
                    # 简表没有IP，只记录设备名和接口
                    device = DiscoveredDevice(
                        hostname=device_name,
                        source="lldp",
                        source_device=source_ip,
                        source_interface=local_intf,
                    )
                    devices.append(device)

        return devices

    def _parse_cisco_lldp_detail(
        self, output: str, source_ip: str
    ) -> List[DiscoveredDevice]:
        """
        解析 Cisco LLDP Detail 输出，提取更丰富的邻居信息。
        """
        devices = []

        # 按 "-----" 分割各邻居块
        blocks = re.split(r"-{4,}", output)

        for block in blocks:
            if not block.strip():
                continue

            chassis_id = ""
            port_id = ""
            system_name = ""
            management_ip = ""

            # Chassis id
            match = re.search(r"Chassis id:\s*(.+)", block)
            if match:
                chassis_id = match.group(1).strip()

            # Port id
            match = re.search(r"Port id:\s*(.+)", block)
            if match:
                port_id = match.group(1).strip()

            # System Name
            match = re.search(r"System Name:\s*(.+)", block)
            if match:
                system_name = match.group(1).strip()

            # Management Addresses - IP
            match = re.search(r"IP:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", block)
            if match:
                management_ip = match.group(1).strip()

            # System Description (用于厂商识别)
            sys_desc = ""
            match = re.search(r"System Description:\s*(.+?)(?:\n|$)", block)
            if match:
                sys_desc = match.group(1).strip()

            # 识别厂商
            vendor = VendorIdentifier.identify_from_lldp_info(system_name, sys_desc)

            if system_name or management_ip or chassis_id:
                device = DiscoveredDevice(
                    ip=management_ip or "",
                    hostname=system_name,
                    mac_address=chassis_id if ":" in chassis_id else "",
                    vendor=vendor or "",
                    vendor_raw=vendor or "",
                    identified=bool(vendor),
                    source="lldp",
                    source_device=source_ip,
                    source_interface=port_id,
                    management_ip=management_ip,
                    ssh_reachable=bool(management_ip),
                )
                devices.append(device)

        return devices

    def _parse_ruijie_lldp(self, output: str, source_ip: str) -> List[DiscoveredDevice]:
        """
        解析锐捷 LLDP 输出。

        格式与 Cisco 类似。
        """
        # 锐捷 LLDP 输出格式与 Cisco 非常相似
        return self._parse_cisco_lldp(output, source_ip)

    def _parse_cdp_output(
        self, output: str, source_ip: str
    ) -> List[DiscoveredDevice]:
        """
        解析 Cisco CDP 输出。

        典型格式 (show cdp neighbors detail):
        -------------------------
        Device ID: SW-ACCESS-01.cisco.com
        Entry address(es):
          IP address: 192.168.1.2
        Platform: cisco WS-C3750,  Capabilities: Switch
        Interface: GigabitEthernet0/1,  Port ID (outgoing port): Gi0/1
        """
        devices = []

        # 按 "-----" 分割各邻居块
        blocks = re.split(r"-{4,}", output)

        for block in blocks:
            if not block.strip():
                continue

            device_id = ""
            ip_address = ""
            platform = ""
            interface = ""
            port_id = ""

            # Device ID
            match = re.search(r"Device ID:\s*(.+)", block)
            if match:
                device_id = match.group(1).strip()
                # 去掉域名部分
                if "." in device_id:
                    device_id = device_id.split(".")[0]

            # IP address
            match = re.search(
                r"IP address:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", block
            )
            if match:
                ip_address = match.group(1).strip()

            # Platform
            match = re.search(r"Platform:\s*(.+?)(?:,|\n)", block)
            if match:
                platform = match.group(1).strip()

            # Interface
            match = re.search(r"Interface:\s*(.+?)(?:,|\n)", block)
            if match:
                interface = match.group(1).strip()

            # Port ID
            match = re.search(r"Port ID.*?:\s*(.+)", block)
            if match:
                port_id = match.group(1).strip()

            # 从 Platform 识别厂商
            vendor = VendorIdentifier.identify_from_lldp_info(device_id, platform)

            if device_id or ip_address:
                device = DiscoveredDevice(
                    ip=ip_address or "",
                    hostname=device_id,
                    vendor=vendor or "",
                    vendor_raw=vendor or "",
                    model=platform,
                    identified=bool(vendor),
                    source="cdp",
                    source_device=source_ip,
                    source_interface=interface or port_id,
                    management_ip=ip_address,
                    ssh_reachable=bool(ip_address),
                )
                devices.append(device)

        return devices

    # ============================================================
    # 辅助方法
    # ============================================================

    def _neighbor_to_seed(self, neighbor: DiscoveredDevice) -> Optional[Dict[str, Any]]:
        """
        将发现的邻居设备转换为种子设备格式，用于下一层递归。

        需要匹配对应厂商的凭证。
        """
        vendor = neighbor.vendor
        ip = neighbor.display_ip

        if not vendor or vendor == "unknown":
            return None

        # 查找对应厂商的凭证
        cred = self.passwords.get(vendor) or self.passwords.get("default")
        if not cred:
            return None

        username = cred.get("username", "")
        password = cred.get("password", "")

        if not username or not password:
            return None

        return {
            "ip": ip,
            "vendor": vendor,
            "username": username,
            "password": password,
            "port": neighbor.ssh_port,
        }

    def _connect_via_jump_host(
        self, connect_params: dict, seed_device: dict
    ):
        """通过跳板机连接种子设备"""
        try:
            from netmiko import ConnectHandler
        except ImportError:
            return None

        jump_host = seed_device.get("jump_host", "")
        jump_username = seed_device.get("jump_username", "")
        jump_password = seed_device.get("jump_password", "")
        jump_port = seed_device.get("jump_port", 22)

        if not all([jump_host, jump_username, jump_password]):
            return None

        jump_params = {
            "device_type": "terminal_server",
            "host": jump_host,
            "username": jump_username,
            "password": jump_password,
            "port": jump_port,
            "timeout": self.timeout_per_device,
        }

        jump_conn = None
        try:
            jump_conn = ConnectHandler(**jump_params)

            dest_host = connect_params["host"]
            dest_user = connect_params["username"]
            dest_pass = connect_params["password"]
            dest_port = connect_params.get("port", 22)

            ssh_cmd = f"ssh -o StrictHostKeyChecking=no {dest_user}@{dest_host} -p {dest_port}"
            jump_conn.write_channel(ssh_cmd + "\n")

            import time
            time.sleep(2)

            output = jump_conn.read_channel()
            if "password" in output.lower() or "assword" in output.lower():
                jump_conn.write_channel(dest_pass + "\n")
                time.sleep(2)

            from netmiko import redispatch
            redispatch(jump_conn, device_type=connect_params.get("device_type", "cisco_ios"))
            return jump_conn

        except Exception as e:
            logger.debug("通过跳板机连接种子设备失败: %s", e)
            if jump_conn:
                try:
                    jump_conn.disconnect()
                except Exception:
                    pass
            return None

    @staticmethod
    def _log_progress(callback, message: str):
        """输出进度信息"""
        logger.info(message)
        if callback:
            callback(message)
