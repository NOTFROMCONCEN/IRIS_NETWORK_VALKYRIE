#!/usr/bin/env python3
"""
设备适配器模块
Device Adapters Module

包含所有厂商设备的适配器实现，统一管理设备操作
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

try:
    from netmiko import ConnectHandler
    from netmiko.exceptions import (
        NetmikoTimeoutException,
        NetmikoAuthenticationException,
    )
except ImportError:
    print("[错误] 缺少netmiko模块，请运行: pip install netmiko")
    raise


class BaseAdapter(ABC):
    """设备适配器基类"""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        vendor: str = "",
        config: Dict[str, Any] = None,
    ):
        """
        初始化适配器

        Args:
            host: 设备IP地址
            username: 用户名
            password: 密码
            port: SSH端口
            vendor: 厂商名称
            config: 配置字典
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.vendor = vendor
        self.connection = None
        self.is_connected = False
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.config = config or {}

        # 命令映射（子类需要设置）
        self.commands = {}
        self.device_type = ""  # netmiko设备类型

    def connect(self) -> Tuple[bool, str]:
        """
        连接设备

        Returns:
            (成功标志, 消息)
        """
        try:
            self.logger.info(f"正在连接设备 {self.host}...")

            # 从配置获取超时时间，默认值适配内网环境
            connect_timeout = self.config.get("network", {}).get("connect_timeout", 60)
            command_timeout = self.config.get("network", {}).get("command_timeout", 120)

            device = {
                "device_type": self.device_type,
                "host": self.host,
                "username": self.username,
                "password": self.password,
                "port": self.port,
                "timeout": connect_timeout,
                "session_timeout": command_timeout,
            }

            self.connection = ConnectHandler(**device)
            self.is_connected = True

            message = f"[成功] 设备 {self.host} 连接成功"
            self.logger.info(message)
            return True, message

        except NetmikoAuthenticationException as e:
            message = f"[失败] 认证失败: {self.host} - 请检查用户名/密码"
            self.logger.error(message)
            # 认证失败时立即断开连接
            self.disconnect()
            return False, message

        except NetmikoTimeoutException as e:
            message = f"[失败] 连接超时: {self.host} - 请检查IP/端口/网络连通性"
            self.logger.error(message)
            return False, message

        except Exception as e:
            message = f"[失败] 连接异常: {self.host} - {str(e)}"
            self.logger.error(message)
            return False, message

    def disconnect(self):
        """断开连接"""
        if self.connection:
            try:
                self.connection.disconnect()
                self.is_connected = False
                self.logger.info(f"设备 {self.host} 已断开连接")
            except Exception as e:
                self.logger.error(f"断开连接时发生错误: {e}")

    def send_command(self, command: str, expect_string: str = None) -> Tuple[bool, str]:
        """
        发送单个命令

        Args:
            command: 命令字符串
            expect_string: 期望的提示符

        Returns:
            (成功标志, 输出内容)
        """
        if not self.is_connected or not self.connection:
            return False, "设备未连接"

        try:
            self.logger.debug(f"执行命令: {command}")

            # 从配置获取命令超时时间
            command_timeout = self.config.get("network", {}).get("command_timeout", 120)

            if expect_string:
                output = self.connection.send_command(
                    command, expect_string=expect_string, read_timeout=command_timeout
                )
            else:
                output = self.connection.send_command(
                    command, read_timeout=command_timeout
                )

            return True, output

        except Exception as e:
            error_msg = f"命令执行失败: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

    def run_commands(self) -> Dict[str, Any]:
        """
        执行所有命令

        Returns:
            结果字典
        """
        if not self.is_connected:
            return {"error": "设备未连接"}

        results = {}
        success_count = 0

        self.logger.info(f"开始执行 {len(self.commands)} 个命令")

        for cmd_type, cmd_string in self.commands.items():
            start_ts = time.time()
            try:
                self.logger.debug(f"执行命令: {cmd_type} -> {cmd_string}")

                success, output = self.send_command(cmd_string)
                duration_ms = int((time.time() - start_ts) * 1000)

                results[cmd_type] = {
                    "status": success,
                    "output": output,
                    "timestamp": datetime.now().isoformat(),
                    "command": cmd_string,
                    "duration_ms": duration_ms,
                }

                self.logger.info(
                    "命令执行结束: host=%s vendor=%s cmd_type=%s status=%s duration_ms=%s",
                    self.host,
                    self.vendor,
                    cmd_type,
                    success,
                    duration_ms,
                )

                if success:
                    success_count += 1

                # 命令间延迟
                time.sleep(1)

            except Exception as e:
                self.logger.error(f"命令 {cmd_type} 执行异常: {e}")
                duration_ms = int((time.time() - start_ts) * 1000)
                results[cmd_type] = {
                    "status": False,
                    "output": f"异常: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                    "command": cmd_string,
                    "duration_ms": duration_ms,
                }

        self.logger.info(f"命令执行完成: {success_count}/{len(self.commands)}")
        return results

    def _collect_logs_from_commands(
        self, log_commands: Dict[str, str]
    ) -> Tuple[bool, str, str]:
        """从给定命令字典中收集日志"""
        if not self.is_connected:
            return False, "", "设备未连接"

        all_logs = []
        success_count = 0

        for cmd_name, cmd_string in log_commands.items():
            try:
                success, output = self.send_command(cmd_string)
                if success and output:
                    all_logs.append(f"\n{'='*60}\n")
                    all_logs.append(f"日志类型: {cmd_name}\n")
                    all_logs.append(f"{'='*60}\n")
                    all_logs.append(output)
                    success_count += 1
            except Exception as e:
                self.logger.error(f"获取日志 {cmd_name} 失败: {e}")

        if success_count > 0:
            combined_logs = "\n".join(all_logs)
            return True, combined_logs, f"成功获取 {success_count} 个日志"
        else:
            return False, "", "所有日志命令执行失败"

    @abstractmethod
    def get_logs(self) -> Tuple[bool, str, str]:
        """
        获取设备日志（子类必须实现）

        Returns:
            (成功标志, 日志内容, 消息)
        """
        pass


class HuaweiAdapter(BaseAdapter):
    """华为设备适配器"""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        vendor: str = "huawei",
        config: Dict[str, Any] = None,
    ):
        super().__init__(host, username, password, port, vendor, config)
        self.device_type = "huawei"

        # 华为设备命令集
        self.commands = {
            "version": "display version",
            "device": "display device",
            "cpu": "display cpu-usage",
            "memory": "display memory-usage",
            "temperature": "display temperature all",
            "fan": "display fan",
            "power": "display power",
            "interface_brief": "display interface brief",
            "ip_interface": "display ip interface brief",
            "arp": "display arp",
            "mac": "display mac-address",
            "vlan": "display vlan",
            "route": "display ip routing-table",
            "bgp": "display bgp peer",
            "ospf": "display ospf peer brief",
        }

    def get_logs(self) -> Tuple[bool, str, str]:
        """获取华为设备日志"""
        log_commands = {
            "logbuffer": "display logbuffer",
            "alarm": "display alarm active",
        }
        return self._collect_logs_from_commands(log_commands)


class H3CAdapter(BaseAdapter):
    """H3C设备适配器"""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        vendor: str = "h3c",
        config: Dict[str, Any] = None,
    ):
        super().__init__(host, username, password, port, vendor, config)
        self.device_type = "hp_comware"

        # H3C设备命令集
        self.commands = {
            "version": "display version",
            "device": "display device",
            "cpu": "display cpu-usage",
            "memory": "display memory",
            "temperature": "display environment",
            "fan": "display fan",
            "power": "display power",
            "interface_brief": "display interface brief",
            "ip_interface": "display ip interface brief",
            "arp": "display arp",
            "mac": "display mac-address",
            "vlan": "display vlan all",
            "route": "display ip routing-table",
        }

    def get_logs(self) -> Tuple[bool, str, str]:
        """获取H3C设备日志"""
        log_commands = {
            "logbuffer": "display logbuffer",
        }
        return self._collect_logs_from_commands(log_commands)


class RuijieAdapter(BaseAdapter):
    """锐捷设备适配器（包括下级设备）"""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        vendor: str = "ruijie",
        config: Dict[str, Any] = None,
    ):
        super().__init__(host, username, password, port, vendor, config)
        self.device_type = "ruijie_os"

        # 锐捷设备命令集
        self.commands = {
            "version": "show version",
            "cpu": "show cpu",
            "memory": "show memory",
            "processes": "show processes",
            "interface_status": "show interface status",
            "interface_description": "show interface description",
            "ip_interface": "show ip interface brief",
            "arp": "show arp",
            "mac": "show mac-address-table",
            "vlan": "show vlan",
            "route": "show ip route",
        }

    def get_logs(self) -> Tuple[bool, str, str]:
        """获取锐捷设备日志"""
        if not self.is_connected:
            return False, "", "设备未连接"

        # 锐捷日志命令的多种尝试
        log_commands = [
            "show loggin",
            "sh loggin",
            "show logging",
        ]

        all_logs = []
        success = False

        for cmd in log_commands:
            try:
                status, output = self.send_command(cmd)
                if status and output and len(output) > 50:
                    all_logs.append(f"\n{'='*60}\n")
                    all_logs.append(f"日志命令: {cmd}\n")
                    all_logs.append(f"{'='*60}\n")
                    all_logs.append(output)
                    success = True
                    break  # 成功获取就不再尝试其他命令
            except Exception as e:
                self.logger.debug(f"尝试命令 {cmd} 失败: {e}")
                continue

        if success:
            combined_logs = "\n".join(all_logs)
            return True, combined_logs, "成功获取日志"
        else:
            return False, "", "所有日志命令尝试失败"


class MaipuAdapter(BaseAdapter):
    """迈普设备适配器"""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        vendor: str = "maipu",
        config: Dict[str, Any] = None,
    ):
        super().__init__(host, username, password, port, vendor, config)
        self.device_type = "generic_termserver"  # 使用通用类型

        # 迈普设备命令集
        self.commands = {
            "version": "show version",
            "cpu": "show cpu",
            "memory": "show memory",
            "interface": "show interface",
            "ip_interface": "show ip interface brief",
            "route": "show ip route",
        }

    def get_logs(self) -> Tuple[bool, str, str]:
        """获取迈普设备日志"""
        log_commands = {
            "logging": "show logging",
        }
        return self._collect_logs_from_commands(log_commands)


class WSTAdapter(BaseAdapter):
    """龙马防火墙设备适配器"""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        vendor: str = "wst",
        config: Dict[str, Any] = None,
    ):
        super().__init__(host, username, password, port, vendor, config)
        self.device_type = "generic_termserver"  # 使用通用类型

        # 龙马防火墙命令集
        self.commands = {
            "version": "show version",
            "system": "show system",
            "interface": "show interface",
            "route": "show route",
            "session": "show session",
            "policy": "show policy",
        }

    def get_logs(self) -> Tuple[bool, str, str]:
        """获取龙马设备日志"""
        log_commands = {
            "log": "show log",
        }
        return self._collect_logs_from_commands(log_commands)


class CiscoAdapter(BaseAdapter):
    """思科设备适配器"""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        vendor: str = "cisco",
        config: Dict[str, Any] = None,
    ):
        super().__init__(host, username, password, port, vendor, config)
        self.device_type = "cisco_ios"

        # 思科设备命令集
        self.commands = {
            "version": "show version",
            "running_config": "show running-config",
            "inventory": "show inventory",
            "processes": "show processes cpu",
            "memory": "show memory statistics",
            "interface_status": "show interface status",
            "interface_description": "show interface description",
            "ip_interface": "show ip interface brief",
            "arp": "show arp",
            "mac": "show mac address-table",
            "vlan": "show vlan brief",
            "route": "show ip route",
            "bgp": "show ip bgp summary",
            "ospf": "show ip ospf neighbor",
        }

    def get_logs(self) -> Tuple[bool, str, str]:
        """获取思科设备日志"""
        log_commands = {
            "logging": "show logging",
        }
        return self._collect_logs_from_commands(log_commands)


class AdapterFactory:
    """适配器工厂类"""

    # 适配器注册表
    _adapters: Dict[str, type] = {
        "huawei": HuaweiAdapter,
        "h3c": H3CAdapter,
        "ruijie": RuijieAdapter,
        "ruijie_xialian": RuijieAdapter,  # 锐捷下级也使用RuijieAdapter
        "maipu": MaipuAdapter,
        "wst": WSTAdapter,
        "cisco": CiscoAdapter,
    }

    @classmethod
    def create(
        cls,
        vendor: str,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        config: Dict[str, Any] = None,
    ) -> Optional[BaseAdapter]:
        """
        创建适配器实例

        Args:
            vendor: 厂商名称
            host: 设备IP
            username: 用户名
            password: 密码
            port: SSH端口
            config: 配置字典

        Returns:
            适配器实例，如果不支持的厂商则返回None
        """
        vendor_lower = vendor.lower()

        if vendor_lower not in cls._adapters:
            logging.error(f"不支持的厂商: {vendor}")
            return None

        adapter_class = cls._adapters[vendor_lower]

        try:
            return adapter_class(
                host=host,
                username=username,
                password=password,
                port=port,
                vendor=vendor_lower,
                config=config,
            )
        except Exception as e:
            logging.error(f"创建适配器失败: {e}")
            return None

    @classmethod
    def get_supported_vendors(cls) -> List[str]:
        """
        获取支持的厂商列表

        Returns:
            厂商名称列表
        """
        return list(cls._adapters.keys())

    @classmethod
    def is_vendor_supported(cls, vendor: str) -> bool:
        """
        检查厂商是否支持

        Args:
            vendor: 厂商名称

        Returns:
            是否支持
        """
        return vendor.lower() in cls._adapters

    @classmethod
    def register_adapter(cls, vendor: str, adapter_class: type):
        """
        注册新的适配器（用于扩展）

        Args:
            vendor: 厂商名称
            adapter_class: 适配器类
        """
        cls._adapters[vendor.lower()] = adapter_class
        logging.info(f"注册新适配器: {vendor} -> {adapter_class.__name__}")


# 模块初始化时显示支持的厂商
def _init_adapters():
    """初始化适配器模块"""
    vendors = AdapterFactory.get_supported_vendors()
    logging.info(f"设备适配器模块已加载，支持的厂商: {', '.join(vendors)}")


# 自动初始化
_init_adapters()
