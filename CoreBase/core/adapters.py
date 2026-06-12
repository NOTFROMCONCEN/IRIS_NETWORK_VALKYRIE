#!/usr/bin/env python3
"""
设备适配器模块
Device Adapters Module

包含所有厂商设备的适配器实现，统一管理设备操作
"""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

import yaml

from .paths import resolve_corebase_path

try:
    from netmiko import ConnectHandler, redispatch
    from netmiko.exceptions import (
        NetmikoTimeoutException,
        NetmikoAuthenticationException,
    )
except ImportError:
    print("[错误] 缺少netmiko模块，请运行: pip install netmiko")
    raise


@dataclass(frozen=True)
class CommandSpec:
    """命令定义，支持执行元数据和备用命令。"""

    command: str
    expect_string: Optional[str] = None
    read_timeout: Optional[int] = None
    allow_empty_output: bool = True
    min_output_length: int = 0
    fallback_commands: Tuple[str, ...] = ()

    def iter_commands(self) -> Tuple[str, ...]:
        """按主命令 + 备用命令顺序返回所有可尝试命令。"""
        return (self.command, *self.fallback_commands)


CommandDefinition = str | CommandSpec


DEFAULT_COMMAND_CATALOG_FILE = "config/commands.yaml"
VENDOR_COMMAND_ALIASES = {"ruijie_xialian": "ruijie"}



def _parse_command_definition(command: Any) -> CommandDefinition:
    """将 YAML 中的命令定义解析为字符串或命令规格对象。"""
    if isinstance(command, str):
        return command

    if not isinstance(command, dict):
        raise ValueError(f"无效的命令定义: {command!r}")

    command_text = str(command.get("command", "")).strip()
    if not command_text:
        raise ValueError(f"命令定义缺少 command 字段: {command!r}")

    fallback_commands = tuple(command.get("fallback_commands", []) or ())
    return CommandSpec(
        command=command_text,
        expect_string=command.get("expect_string"),
        read_timeout=command.get("read_timeout"),
        allow_empty_output=command.get("allow_empty_output", True),
        min_output_length=command.get("min_output_length", 0),
        fallback_commands=fallback_commands,
    )


def _normalize_lookup_key(value: Any) -> str:
    """归一化 YAML 查找键，便于大小写无关匹配。"""
    return str(value or "").strip().lower()


def _merge_command_section(
    merged_commands: Dict[str, CommandDefinition],
    groups: Dict[str, Any],
    command_catalog: Dict[str, Any],
    section: str,
    source_name: str,
):
    """将一段命令配置合并到结果中，后合并的命令可覆盖前者。"""
    group_key = f"{section}_groups"
    group_names = command_catalog.get(group_key, []) or []
    if not isinstance(group_names, list):
        raise ValueError(f"{source_name} 的 {group_key} 配置格式错误")

    for group_name in group_names:
        group_commands = groups.get(group_name, {})
        if not isinstance(group_commands, dict):
            raise ValueError(f"无效的命令组定义: {group_name}")
        for command_name, command in group_commands.items():
            merged_commands[command_name] = _parse_command_definition(command)

    section_commands = command_catalog.get(section, {})
    if section_commands is None:
        section_commands = {}
    if not isinstance(section_commands, dict):
        raise ValueError(f"{source_name} 的 {section} 命令格式错误")

    for command_name, command in section_commands.items():
        merged_commands[command_name] = _parse_command_definition(command)


def _find_hostname_catalog(
    hostnames: Dict[str, Any], device_name: str, resolved_vendor: str
) -> Optional[Dict[str, Any]]:
    """按设备名查找主机名覆盖配置，可选校验厂商。"""
    normalized_device_name = _normalize_lookup_key(device_name)
    if not normalized_device_name:
        return None

    for hostname, hostname_catalog in hostnames.items():
        if _normalize_lookup_key(hostname) != normalized_device_name:
            continue
        if not isinstance(hostname_catalog, dict):
            raise ValueError(f"主机名 {hostname} 的命令配置格式错误")

        hostname_vendor = _normalize_lookup_key(hostname_catalog.get("vendor"))
        if hostname_vendor:
            hostname_vendor = VENDOR_COMMAND_ALIASES.get(
                hostname_vendor, hostname_vendor
            )
            if hostname_vendor != resolved_vendor:
                return None

        return hostname_catalog

    return None


@lru_cache(maxsize=8)
def _load_command_catalog(command_catalog_file: str) -> Dict[str, Any]:
    """读取独立命令配置文件。"""
    catalog_path = resolve_corebase_path(command_catalog_file)
    if not catalog_path.exists():
        raise FileNotFoundError(f"命令配置文件不存在: {catalog_path}")

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = yaml.safe_load(f) or {}

    if not isinstance(catalog, dict):
        raise ValueError(f"命令配置文件格式错误: {catalog_path}")

    return catalog


def _load_vendor_command_set(
    vendor: str,
    section: str,
    command_catalog_file: str = DEFAULT_COMMAND_CATALOG_FILE,
    device_name: str = "",
) -> Dict[str, CommandDefinition]:
    """从独立命令配置中加载命令集合，支持主机名覆盖厂商默认命令。"""
    catalog = _load_command_catalog(command_catalog_file)
    groups = catalog.get("groups", {})
    vendors = catalog.get("vendors", {})
    hostnames = catalog.get("hostnames", {})

    if not isinstance(groups, dict):
        raise ValueError("命令配置中的 groups 格式错误")
    if not isinstance(vendors, dict):
        raise ValueError("命令配置中的 vendors 格式错误")
    if hostnames is None:
        hostnames = {}
    if not isinstance(hostnames, dict):
        raise ValueError("命令配置中的 hostnames 格式错误")

    resolved_vendor = VENDOR_COMMAND_ALIASES.get(vendor, vendor)
    vendor_catalog = vendors.get(resolved_vendor)
    if not isinstance(vendor_catalog, dict):
        raise KeyError(f"命令配置中未找到厂商: {resolved_vendor}")

    merged_commands: Dict[str, CommandDefinition] = {}

    _merge_command_section(
        merged_commands,
        groups,
        vendor_catalog,
        section,
        source_name=f"厂商 {resolved_vendor}",
    )

    hostname_catalog = _find_hostname_catalog(hostnames, device_name, resolved_vendor)
    if hostname_catalog:
        _merge_command_section(
            merged_commands,
            groups,
            hostname_catalog,
            section,
            source_name=f"主机名 {device_name}",
        )

    return merged_commands


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
        device_name: str = "",
        jump_host: str = None,
        jump_port: int = 22,
        jump_username: str = "",
        jump_password: str = "",
        jump_key_path: str = "",
        jump_key_type: str = "",
        jump_hosts: List[Dict[str, Any]] = None,
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
            jump_host: 跳板机地址（单级跳板机）
            jump_port: 跳板机端口
            jump_username: 跳板机用户名
            jump_password: 跳板机密码
            jump_key_path: 跳板机SSH密钥路径
            jump_key_type: 跳板机密钥类型（如ssh-rsa, ecdsa-sha2-nistp256等）
            jump_hosts: 多级跳板机列表，每个元素为跳板机配置字典
                例如: [{"host": "10.0.0.1", "port": 22, "username": "admin", "password": "pass"}, ...]
        """
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.vendor = vendor
        self.device_name = device_name or host
        self.connection = None
        self.is_connected = False
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.config = config or {}
        self.command_catalog_file = self.config.get("commands", {}).get(
            "catalog_file", DEFAULT_COMMAND_CATALOG_FILE
        )

        # 跳板机配置
        self.jump_host = jump_host
        self.jump_port = jump_port
        self.jump_username = jump_username
        self.jump_password = jump_password
        self.jump_key_path = jump_key_path
        self.jump_key_type = jump_key_type
        self.jump_hosts = jump_hosts or []

        # 命令映射（对外保留字符串字典，内部使用命令规格）
        self.commands = {}
        self.command_specs: Dict[str, CommandSpec] = {}
        self.device_type = ""  # netmiko设备类型

    @staticmethod
    def _normalize_command_spec(command: CommandDefinition) -> CommandSpec:
        """将字符串命令转换为命令规格对象。"""
        if isinstance(command, CommandSpec):
            return command
        return CommandSpec(command=command)

    def _set_commands(self, commands: Dict[str, CommandDefinition]):
        """设置命令定义，同时维护兼容的公开命令映射。"""
        self.command_specs = {
            name: self._normalize_command_spec(command)
            for name, command in commands.items()
        }
        self.commands = {
            name: spec.command for name, spec in self.command_specs.items()
        }

    def _set_commands_from_catalog(self, section: str = "standard"):
        """从独立命令配置文件加载命令。"""
        self._set_commands(
            _load_vendor_command_set(
                self.vendor,
                section,
                command_catalog_file=self.command_catalog_file,
                device_name=self.device_name,
            )
        )

    def _get_log_commands_from_catalog(self) -> Dict[str, CommandDefinition]:
        """从独立命令配置文件加载日志命令。"""
        return _load_vendor_command_set(
            self.vendor,
            "logs",
            command_catalog_file=self.command_catalog_file,
            device_name=self.device_name,
        )

    @staticmethod
    def _is_output_acceptable(spec: CommandSpec, output: str) -> bool:
        """校验命令输出是否满足规格要求。"""
        text = (output or "").strip()
        if not spec.allow_empty_output and not text:
            return False
        if spec.min_output_length and len(text) < spec.min_output_length:
            return False
        return True

    def _execute_command_spec(self, spec: CommandSpec) -> Tuple[bool, str, str]:
        """按命令规格执行，必要时自动尝试备用命令。"""
        last_output = ""
        last_command = spec.command

        for candidate in spec.iter_commands():
            success, output = self.send_command(
                candidate,
                expect_string=spec.expect_string,
                read_timeout=spec.read_timeout,
            )
            last_output = output
            last_command = candidate

            if success and self._is_output_acceptable(spec, output):
                return True, output, candidate

            if success:
                self.logger.debug(
                    "命令输出未通过校验，继续尝试备用命令: host=%s vendor=%s command=%s",
                    self.host,
                    self.vendor,
                    candidate,
                )

        return False, last_output, last_command

    def _get_connect_params(self) -> Dict[str, Any]:
        """构建设备连接参数"""
        return {
            "device_type": self.device_type,
            "host": self.host,
            "username": self.username,
            "password": self.password,
            "port": self.port,
            "timeout": self.config.get("network", {}).get("connect_timeout", 60),
            "session_timeout": self.config.get("network", {}).get("command_timeout", 120),
        }

    def _get_jump_host_params(self) -> Dict[str, Any]:
        """构建跳板机连接参数（使用独立的跳板机超时配置）"""
        jump_host_config = self.config.get("network", {}).get("jump_host", {})
        params = {
            "device_type": "terminal_server",
            "host": self.jump_host,
            "username": self.jump_username,
            "password": self.jump_password,
            "port": self.jump_port,
            "timeout": jump_host_config.get("connect_timeout", 30),
            "session_timeout": jump_host_config.get("command_timeout", 60),
        }
        
        # 如果使用密钥认证
        if self.jump_key_path:
            params["use_keys"] = True
            params["key_file"] = self.jump_key_path
            # 日志中只记录文件名，不记录完整路径（安全考虑）
            key_filename = self.jump_key_path.replace("\\", "/").split("/")[-1]
            self.logger.debug(f"使用SSH密钥连接跳板机: {key_filename}")
            # 如果配置了密钥类型，设置key_type
            if self.jump_key_type:
                params["key_type"] = self.jump_key_type
        
        return params

    def _connect_via_jump_host(self) -> Tuple[bool, str]:
        """通过跳板机连接目标设备（带重试机制）"""
        max_retries = self.config.get("system", {}).get("retries", 3)
        last_error = None
        
        # 记录连接链路信息
        auth_method = "密钥认证" if self.jump_key_path else "密码认证"
        self.logger.info(
            f"连接链路: PC -> [{self.jump_host}:{self.jump_port}] -> [{self.host}:{self.port}] "
            f"(厂商: {self.vendor}, 认证: {auth_method})"
        )
        
        for attempt in range(1, max_retries + 1):
            jump_connection = None
            try:
                self.logger.info(
                    f"通过跳板机 {self.jump_host}:{self.jump_port} 连接设备 {self.host}:{self.port} "
                    f"(尝试 {attempt}/{max_retries})"
                )
                
                # 连接跳板机
                jump_connection = ConnectHandler(**self._get_jump_host_params())
                
                # 从跳板机SSH到目标设备
                ssh_command = f"ssh {self.username}@{self.host} -p {self.port}"
                jump_connection.write_channel(ssh_command + "\r\n")
                
                # 等待密码提示
                time.sleep(2)
                output = jump_connection.read_channel()
                
                if "password" in output.lower():
                    jump_connection.write_channel(self.password + "\r\n")
                    time.sleep(1)
                
                # 使用 redispatch 将连接切换到目标设备类型
                redispatch(jump_connection, device_type=self.device_type)
                
                self.connection = jump_connection
                self.is_connected = True
                
                message = (
                    f"[成功] 设备 {self.host}:{self.port}（厂商: {self.vendor}）"
                    f"通过跳板机 {self.jump_host}:{self.jump_port} 连接成功"
                )
                self.logger.info(message)
                return True, message
                
            except NetmikoAuthenticationException:
                # 认证失败不进行重试，立即清理资源并抛出
                self.logger.error(
                    f"跳板机认证失败: {self.jump_host}:{self.jump_port} "
                    f"(认证: {auth_method})"
                )
                if jump_connection:
                    try:
                        jump_connection.disconnect()
                    except Exception:
                        pass
                raise
                
            except Exception as e:
                last_error = e
                # 连接失败时清理跳板机资源
                if jump_connection:
                    try:
                        jump_connection.disconnect()
                        self.logger.debug(f"跳板机 {self.jump_host} 连接已清理")
                    except Exception as cleanup_error:
                        self.logger.warning(f"清理跳板机连接时出错: {cleanup_error}")
                
                if attempt < max_retries:
                    wait_time = min(2 ** attempt, 30)  # 指数退避，最多30秒
                    self.logger.warning(
                        f"跳板机连接链路失败（尝试 {attempt}/{max_retries}）: "
                        f"PC -> {self.jump_host}:{self.jump_port} -> {self.host}:{self.port} "
                        f"错误: {e}，{wait_time}秒后重试..."
                    )
                    time.sleep(wait_time)
                else:
                    self.logger.error(
                        f"跳板机连接链路失败，已用尽所有 {max_retries} 次重试机会: "
                        f"PC -> {self.jump_host}:{self.jump_port} -> {self.host}:{self.port}"
                    )
        
        raise ConnectionError(f"通过跳板机连接失败（重试 {max_retries} 次）: {last_error}") from last_error

    def _connect_direct(self) -> Tuple[bool, str]:
        """直接连接目标设备"""
        self.connection = ConnectHandler(**self._get_connect_params())
        self.is_connected = True

        message = f"[成功] 设备 {self.host} 连接成功"
        self.logger.info(message)
        return True, message

    def connect(self) -> Tuple[bool, str]:
        """
        连接设备（支持通过跳板机连接）

        Returns:
            (成功标志, 消息)
        """
        self.logger.info(f"正在连接设备 {self.host}...")

        try:
            if self.jump_host:
                return self._connect_via_jump_host()
            return self._connect_direct()

        except NetmikoAuthenticationException:
            message = f"[失败] 认证失败: {self.host} - 请检查用户名/密码"
            self.logger.error(message)
            self.disconnect()
            return False, message

        except NetmikoTimeoutException:
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
                self.logger.info(f"设备 {self.host} 已断开连接")
                self.is_connected = False
            except Exception as e:
                self.logger.error(f"断开连接时发生错误: {e}")

    def send_command(
        self,
        command: str,
        expect_string: str = None,
        read_timeout: Optional[int] = None,
    ) -> Tuple[bool, str]:
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
            command_timeout = (
                read_timeout
                if read_timeout is not None
                else self.config.get("network", {}).get("command_timeout", 120)
            )

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
            # 检测连接是否已断开（如连接超时、连接重置等）
            error_str = str(e).lower()
            if any(keyword in error_str for keyword in ["connection", "session", "closed", "reset", "timeout"]):
                self.is_connected = False
                self.logger.warning(f"检测到连接已断开: {self.host}")
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

        self.logger.info(f"开始执行 {len(self.command_specs)} 个命令")

        for cmd_type, spec in self.command_specs.items():
            start_ts = time.time()
            try:
                self.logger.debug(f"执行命令: {cmd_type} -> {spec.command}")

                success, output, executed_command = self._execute_command_spec(spec)
                duration_ms = int((time.time() - start_ts) * 1000)

                results[cmd_type] = {
                    "status": success,
                    "output": output,
                    "timestamp": datetime.now().isoformat(),
                    "command": executed_command,
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
                    "command": spec.command,
                    "duration_ms": duration_ms,
                }

        self.logger.info(f"命令执行完成: {success_count}/{len(self.command_specs)}")
        return results

    def _collect_logs_from_commands(
        self, log_commands: Dict[str, CommandDefinition]
    ) -> Tuple[bool, str, str]:
        """从给定命令字典中收集日志"""
        if not self.is_connected:
            return False, "", "设备未连接"

        all_logs = []
        success_count = 0

        for cmd_name, command in log_commands.items():
            try:
                spec = self._normalize_command_spec(command)
                success, output, executed_command = self._execute_command_spec(spec)
                if success and output:
                    all_logs.append(f"\n{'='*60}\n")
                    all_logs.append(f"日志类型: {cmd_name}\n")
                    all_logs.append(f"实际命令: {executed_command}\n")
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
        device_name: str = "",
        jump_host: str = None,
        jump_port: int = 22,
        jump_username: str = "",
        jump_password: str = "",
        jump_key_path: str = "",
        jump_key_type: str = "",
    ):
        super().__init__(host, username, password, port, vendor, config, device_name, jump_host, jump_port, jump_username, jump_password, jump_key_path, jump_key_type)
        self.device_type = "huawei"
        self._set_commands_from_catalog()

    def get_logs(self) -> Tuple[bool, str, str]:
        """获取华为设备日志"""
        return self._collect_logs_from_commands(self._get_log_commands_from_catalog())


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
        device_name: str = "",
        jump_host: str = None,
        jump_port: int = 22,
        jump_username: str = "",
        jump_password: str = "",
        jump_key_path: str = "",
        jump_key_type: str = "",
    ):
        super().__init__(host, username, password, port, vendor, config, device_name, jump_host, jump_port, jump_username, jump_password, jump_key_path, jump_key_type)
        self.device_type = "hp_comware"
        self._set_commands_from_catalog()

    def get_logs(self) -> Tuple[bool, str, str]:
        """获取H3C设备日志"""
        return self._collect_logs_from_commands(self._get_log_commands_from_catalog())


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
        device_name: str = "",
        jump_host: str = None,
        jump_port: int = 22,
        jump_username: str = "",
        jump_password: str = "",
        jump_key_path: str = "",
        jump_key_type: str = "",
    ):
        super().__init__(host, username, password, port, vendor, config, device_name, jump_host, jump_port, jump_username, jump_password, jump_key_path, jump_key_type)
        self.device_type = "ruijie_os"
        self._set_commands_from_catalog()

    def get_logs(self) -> Tuple[bool, str, str]:
        """获取锐捷设备日志"""
        return self._collect_logs_from_commands(self._get_log_commands_from_catalog())


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
        device_name: str = "",
        jump_host: str = None,
        jump_port: int = 22,
        jump_username: str = "",
        jump_password: str = "",
        jump_key_path: str = "",
        jump_key_type: str = "",
    ):
        super().__init__(host, username, password, port, vendor, config, device_name, jump_host, jump_port, jump_username, jump_password, jump_key_path, jump_key_type)
        self.device_type = "generic_termserver"  # 使用通用类型
        self._set_commands_from_catalog()

    def get_logs(self) -> Tuple[bool, str, str]:
        """获取迈普设备日志"""
        return self._collect_logs_from_commands(self._get_log_commands_from_catalog())


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
        device_name: str = "",
        jump_host: str = None,
        jump_port: int = 22,
        jump_username: str = "",
        jump_password: str = "",
        jump_key_path: str = "",
        jump_key_type: str = "",
    ):
        super().__init__(host, username, password, port, vendor, config, device_name, jump_host, jump_port, jump_username, jump_password, jump_key_path, jump_key_type)
        self.device_type = "generic_termserver"  # 使用通用类型
        self._set_commands_from_catalog()

    def get_logs(self) -> Tuple[bool, str, str]:
        """获取龙马设备日志"""
        return self._collect_logs_from_commands(self._get_log_commands_from_catalog())


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
        device_name: str = "",
        jump_host: str = None,
        jump_port: int = 22,
        jump_username: str = "",
        jump_password: str = "",
        jump_key_path: str = "",
        jump_key_type: str = "",
    ):
        super().__init__(host, username, password, port, vendor, config, device_name, jump_host, jump_port, jump_username, jump_password, jump_key_path, jump_key_type)
        self.device_type = "cisco_ios"
        self._set_commands_from_catalog()

    def get_logs(self) -> Tuple[bool, str, str]:
        """获取思科设备日志"""
        return self._collect_logs_from_commands(self._get_log_commands_from_catalog())


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
        device_name: str = "",
        jump_host: str = None,
        jump_port: int = 22,
        jump_username: str = "",
        jump_password: str = "",
        jump_key_path: str = "",
        jump_key_type: str = "",
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
            device_name: 设备名，用于主机名命令覆盖
            jump_host: 跳板机地址
            jump_port: 跳板机端口
            jump_username: 跳板机用户名
            jump_password: 跳板机密码
            jump_key_path: 跳板机SSH密钥路径
            jump_key_type: 跳板机密钥类型

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
                device_name=device_name,
                jump_host=jump_host,
                jump_port=jump_port,
                jump_username=jump_username,
                jump_password=jump_password,
                jump_key_path=jump_key_path,
                jump_key_type=jump_key_type,
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
