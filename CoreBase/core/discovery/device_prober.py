#!/usr/bin/env python3
"""
单设备探测模块
Device Prober Module

对单个设备进行 SSH 探测，尝试登录并识别厂商和型号。
"""

import socket
import logging
from typing import Dict, Any, Optional, Tuple

from .discovery_models import DiscoveredDevice
from .vendor_identifier import VendorIdentifier

logger = logging.getLogger(__name__)


class DeviceProber:
    """单设备 SSH 探测器"""

    # netmiko 设备类型与厂商的映射（用于尝试连接）
    VENDOR_DEVICE_TYPES = {
        "huawei": "huawei",
        "h3c": "hp_comware",
        "cisco": "cisco_ios",
        "ruijie": "ruijie_os",
        "maipu": "generic",
        "wst": "generic_termserver",
    }

    # 各厂商用于识别的命令
    VENDOR_IDENTIFY_COMMANDS = {
        "huawei": "display version",
        "h3c": "display version",
        "cisco": "show version",
        "ruijie": "show version",
        "maipu": "show version",
        "wst": "show version",
    }

    def __init__(self, config: Dict[str, Any], passwords: Dict[str, Dict[str, str]]):
        """
        初始化探测器。

        Args:
            config: 全局配置字典
            passwords: 凭证字典 {vendor: {'username': ..., 'password': ...}}
        """
        self.config = config
        self.passwords = passwords
        self.identification_config = config.get("discovery", {}).get("identification", {})
        self.login_timeout = self.identification_config.get("login_timeout", 10)
        self.command_timeout = self.identification_config.get("command_timeout", 10)

    def check_ssh_port(self, ip: str, port: int = 22, timeout: float = 3) -> bool:
        """
        检查 SSH 端口是否开放。

        Args:
            ip: 目标IP
            port: 目标端口
            timeout: 超时时间(秒)

        Returns:
            端口是否开放
        """
        try:
            with socket.create_connection((ip, port), timeout=timeout):
                return True
        except (socket.timeout, socket.error, OSError):
            return False

    def probe_device(
        self,
        ip: str,
        port: int = 22,
        jump_host_config: Dict[str, Any] = None,
    ) -> DiscoveredDevice:
        """
        探测单个设备：检查SSH可达性，尝试登录识别厂商。

        Args:
            ip: 设备IP
            port: SSH端口
            jump_host_config: 跳板机配置（可选）

        Returns:
            探测结果 DiscoveredDevice
        """
        device = DiscoveredDevice(ip=ip, ssh_port=port)

        # 第一步：检查SSH端口
        ssh_timeout = self.config.get("discovery", {}).get("subnet_scan", {}).get(
            "ssh_timeout", 3
        )
        if not self.check_ssh_port(ip, port, timeout=ssh_timeout):
            logger.debug("设备 %s:%s SSH端口不可达", ip, port)
            return device

        device.ssh_reachable = True

        # 第二步：尝试SSH登录并识别厂商
        try:
            from netmiko import ConnectHandler
            from netmiko.exceptions import (
                NetmikoTimeoutException,
                NetmikoAuthenticationException,
            )
        except ImportError:
            logger.error("缺少 netmiko 模块，无法进行SSH探测")
            return device

        vendor, hostname, model, version_output = self._try_identify(
            ip, port, jump_host_config
        )

        if vendor:
            device.vendor = vendor
            device.vendor_raw = self._vendor_display_name(vendor)
            device.identified = True
        if hostname:
            device.hostname = hostname
        if model:
            device.model = model

        return device

    def _try_identify(
        self,
        ip: str,
        port: int,
        jump_host_config: Dict[str, Any] = None,
    ) -> Tuple[Optional[str], str, str, str]:
        """
        尝试通过SSH登录识别设备厂商。

        策略：
        1. 按已配置的凭证逐个尝试
        2. 如果 try_all_credentials=True，尝试所有厂商凭证
        3. 成功连接后执行版本命令获取信息

        Returns:
            (vendor, hostname, model, version_output)
        """
        try:
            from netmiko import ConnectHandler
            from netmiko.exceptions import (
                NetmikoTimeoutException,
                NetmikoAuthenticationException,
            )
        except ImportError:
            return None, "", "", ""

        try_all = self.identification_config.get("try_all_credentials", True)

        # 构建凭证尝试列表
        credential_list = self._build_credential_list(try_all)

        for vendor_hint, username, password in credential_list:
            device_type = self.VENDOR_DEVICE_TYPES.get(vendor_hint, "autodetect")
            connection = None

            try:
                connect_params = {
                    "device_type": device_type,
                    "host": ip,
                    "username": username,
                    "password": password,
                    "port": port,
                    "timeout": self.login_timeout,
                    "session_timeout": self.command_timeout,
                    "conn_timeout": self.login_timeout,
                }

                # 跳板机连接
                if jump_host_config:
                    connection = self._connect_via_jump(
                        connect_params, jump_host_config
                    )
                else:
                    connection = ConnectHandler(**connect_params)

                if not connection:
                    continue

                # 获取提示符
                prompt = connection.find_prompt()
                hostname = VendorIdentifier.extract_hostname_from_prompt(prompt)

                # 执行版本命令
                vendor, model, version_output = self._identify_from_connection(
                    connection, vendor_hint
                )

                connection.disconnect()

                return vendor, hostname, model, version_output or ""

            except NetmikoAuthenticationException:
                logger.debug(
                    "设备 %s 使用 %s 凭证认证失败", ip, vendor_hint
                )
                if connection:
                    try:
                        connection.disconnect()
                    except Exception:
                        pass
                continue

            except NetmikoTimeoutException:
                logger.debug("设备 %s 连接超时 (device_type=%s)", ip, device_type)
                if connection:
                    try:
                        connection.disconnect()
                    except Exception:
                        pass
                continue

            except Exception as e:
                logger.debug("设备 %s 连接异常: %s", ip, e)
                if connection:
                    try:
                        connection.disconnect()
                    except Exception:
                        pass
                continue

        logger.debug("设备 %s 所有凭证尝试均失败", ip)
        return None, "", "", ""

    def _build_credential_list(self, try_all: bool) -> list:
        """
        构建凭证尝试列表。

        Returns:
            [(vendor_hint, username, password), ...]
        """
        credentials = []

        # 首先添加各厂商专用凭证
        for vendor, cred in self.passwords.items():
            if vendor == "default":
                continue
            username = cred.get("username", "")
            password = cred.get("password", "")
            if username and password:
                credentials.append((vendor, username, password))

        # 添加 default 凭证
        if "default" in self.passwords:
            cred = self.passwords["default"]
            username = cred.get("username", "")
            password = cred.get("password", "")
            if username and password:
                credentials.append(("default", username, password))

        if not try_all and credentials:
            # 只尝试第一个
            credentials = credentials[:1]

        return credentials

    def _identify_from_connection(
        self, connection, vendor_hint: str
    ) -> Tuple[Optional[str], str, str]:
        """
        从已建立的SSH连接识别厂商、型号。

        Args:
            connection: netmiko 连接对象
            vendor_hint: 凭证对应的厂商提示

        Returns:
            (vendor, model, version_output)
        """
        version_output = ""

        # 执行对应厂商的版本命令
        command = self.VENDOR_IDENTIFY_COMMANDS.get(vendor_hint, "show version")
        if command:
            try:
                version_output = connection.send_command(
                    command,
                    read_timeout=self.command_timeout,
                    strip_prompt=True,
                    strip_command=True,
                )
            except Exception as e:
                logger.debug("执行版本命令失败 (%s): %s", command, e)

        # 从输出识别厂商
        vendor = None
        if version_output:
            vendor = VendorIdentifier.identify_from_output(version_output)

        # 如果无法从输出识别，使用凭证对应的厂商
        if not vendor and vendor_hint != "default":
            vendor = vendor_hint

        # 提取型号
        model = ""
        if vendor and version_output:
            model = VendorIdentifier.extract_model_from_version(vendor, version_output)

        return vendor, model, version_output

    def _connect_via_jump(self, connect_params: dict, jump_config: dict):
        """通过跳板机连接设备"""
        try:
            from netmiko import ConnectHandler
        except ImportError:
            return None

        jump_params = {
            "device_type": "terminal_server",
            "host": jump_config.get("host", ""),
            "username": jump_config.get("username", ""),
            "password": jump_config.get("password", ""),
            "port": jump_config.get("port", 22),
            "timeout": self.login_timeout,
            "session_timeout": self.command_timeout,
        }

        jump_conn = None
        try:
            jump_conn = ConnectHandler(**jump_params)

            # 通过跳板机SSH到目标设备
            dest_host = connect_params["host"]
            dest_port = connect_params.get("port", 22)
            dest_user = connect_params["username"]
            dest_pass = connect_params["password"]

            ssh_cmd = f"ssh -o StrictHostKeyChecking=no {dest_user}@{dest_host} -p {dest_port}"
            jump_conn.write_channel(ssh_cmd + "\n")

            import time
            time.sleep(2)

            # 处理密码提示
            output = jump_conn.read_channel()
            if "password" in output.lower() or "assword" in output.lower():
                jump_conn.write_channel(dest_pass + "\n")
                time.sleep(2)

            from netmiko import redispatch
            redispatch(jump_conn, device_type=connect_params.get("device_type", "cisco_ios"))
            return jump_conn

        except Exception as e:
            logger.debug("通过跳板机连接失败: %s", e)
            if jump_conn:
                try:
                    jump_conn.disconnect()
                except Exception:
                    pass
            return None

    @staticmethod
    def _vendor_display_name(vendor: str) -> str:
        """获取厂商的显示名称"""
        display_names = {
            "huawei": "huawei",
            "h3c": "h3c",
            "cisco": "cisco",
            "ruijie": "ruijie",
            "maipu": "maipu",
            "wst": "wst",
        }
        return display_names.get(vendor, vendor)
