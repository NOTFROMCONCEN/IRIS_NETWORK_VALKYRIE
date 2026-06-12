#!/usr/bin/env python3
"""
工具函数模块
Utility Functions Module

提供配置加载、设备管理、日志设置等通用功能
"""

import os
import sys
import logging
import ipaddress
import yaml
import gzip
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Tuple

from .device_inventory import (
    inventory_to_cli_device,
    read_device_inventory,
    validate_cli_device,
)
from .paths import COREBASE_ROOT, resolve_corebase_path
from .crypto import is_encrypted, decrypt_password


def load_config(config_file: str = "config/config.yaml") -> Dict[str, Any]:
    """
    加载YAML配置文件

    Args:
        config_file: 配置文件路径

    Returns:
        配置字典
    """
    try:
        config_path = resolve_corebase_path(config_file)
        if not config_path.exists():
            print(f"[警告] 配置文件不存在: {config_path}，使用默认配置")
            return _get_default_config()

        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        print(f"[成功] 配置文件加载成功: {config_path}")
        return config

    except Exception as e:
        print(f"[错误] 配置文件加载失败: {e}")
        print("[提示] 使用默认配置继续")
        return _get_default_config()


def _get_default_config() -> Dict[str, Any]:
    """获取默认配置"""
    return {
        "version": "3.0.0",
        "system": {"timeout": 60, "retries": 3, "log_level": "INFO"},
        "network": {"ssh_port": 22, "connect_timeout": 30, "command_timeout": 60},
        "commands": {"catalog_file": "config/commands.yaml"},
        "output": {"results_dir": "output/results", "logs_dir": "output/logs"},
        "features": {"log_mode": True, "auto_retry": True, "progress_bar": True},
    }


def load_devices(excel_file: str) -> List[Dict[str, Any]]:
    """
    从Excel文件加载设备信息

    Args:
        excel_file: Excel文件路径

    Returns:
        设备信息列表
    """
    try:
        _, inventory_devices, warnings = read_device_inventory(excel_file)
        for warning in warnings:
            print(f"[警告] {warning}")

        devices = []
        for inventory_device in inventory_devices:
            device = inventory_to_cli_device(inventory_device)
            if device["ip"] and device["vendor"]:
                devices.append(device)
            else:
                print(f"[警告] 跳过无效设备: {device.get('name', 'unknown')}")

        print(f"[成功] 成功加载 {len(devices)} 台设备")
        return devices

    except FileNotFoundError:
        excel_path = resolve_corebase_path(excel_file)
        print(f"[错误] 设备配置文件不存在: {excel_path}")
        return []

    except ValueError as e:
        print(f"[错误] {e}")
        return []

    except Exception as e:
        print(f"[错误] 读取设备信息失败: {e}")
        return []


def load_passwords(
    config_file: str = "config/password.conf",
) -> Dict[str, Dict[str, str]]:
    """
    加载密码配置文件

    Args:
        config_file: 密码配置文件路径

    Returns:
        密码配置字典 {厂商: {'username': xxx, 'password': xxx}}
    """
    passwords = {}

    try:
        config_path = resolve_corebase_path(config_file)
        if not config_path.exists():
            print(f"[警告] 密码配置文件不存在: {config_path}")
            return {"default": {"username": "admin", "password": "admin"}}

        with open(config_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # 跳过注释和空行
                if not line or line.startswith("#"):
                    continue

                if "=" in line:
                    parts = line.split("=", 1)
                    if len(parts) != 2:
                        print(f"[警告] 第 {line_num} 行格式错误，已忽略: {line}")
                        continue

                    vendor, credentials = parts
                    vendor = vendor.strip()

                    if "," in credentials:
                        cred_parts = credentials.split(",", 1)
                        if len(cred_parts) != 2:
                            print(
                                f"[警告] 第 {line_num} 行凭证格式错误，已忽略: {line}"
                            )
                            continue

                        username, password = cred_parts
                        username = username.strip()
                        password = password.strip()

                        # 检查是否为加密密码，如果是则解密
                        if is_encrypted(password):
                            decrypted = decrypt_password(password)
                            if decrypted is None:
                                print(
                                    f"[警告] 第 {line_num} 行密码解密失败，已忽略: {vendor}"
                                )
                                continue
                            password = decrypted
                            print(f"[提示] 已解密 {vendor} 的加密密码")

                        if vendor in passwords:
                            print(
                                f"[提示] 第 {line_num} 行发现重复的厂商配置 '{vendor}'，将覆盖旧值"
                            )

                        passwords[vendor] = {
                            "username": username,
                            "password": password,
                        }
                    else:
                        print(
                            f"[警告] 第 {line_num} 行凭证格式错误(缺少逗号)，已忽略: {line}"
                        )

        if not passwords:
            print("[警告] 密码配置为空，使用默认配置")
            passwords["default"] = {"username": "admin", "password": "admin"}

        print(f"[成功] 成功加载 {len(passwords)} 个厂商的密码配置")
        return passwords

    except Exception as e:
        print(f"[错误] 读取密码配置失败: {e}")
        return {"default": {"username": "admin", "password": "admin"}}


def setup_logging(config: Dict[str, Any]) -> str:
    """
    设置日志系统（支持日志轮转）

    Args:
        config: 配置字典

    Returns:
        日志文件路径
    """
    try:
        # 获取日志配置
        log_level = config.get("system", {}).get("log_level", "INFO")
        logs_dir = config.get("output", {}).get("logs_dir", "output/logs")
        log_rotation = config.get("output", {}).get("log_rotation", {})

        # 确保日志目录存在
        logs_path = resolve_corebase_path(logs_dir)
        logs_path.mkdir(parents=True, exist_ok=True)

        # 生成日志文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = logs_path / f"inspection_{timestamp}.log"

        # 配置日志
        log_level_obj = getattr(logging, log_level.upper(), logging.INFO)

        # 获取日志轮转配置
        rotation_enabled = log_rotation.get("enabled", False)
        max_bytes = log_rotation.get("max_bytes", 10 * 1024 * 1024)  # 默认10MB
        backup_count = log_rotation.get("backup_count", 7)  # 默认保留7个
        compress_old_logs = log_rotation.get("compress_old_logs", True)

        # 配置处理器列表
        handlers = []

        # 文件处理器（支持轮转）
        if rotation_enabled:
            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                str(log_file),
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding="utf-8",
            )
            handlers.append(file_handler)
        else:
            handlers.append(logging.FileHandler(str(log_file), encoding="utf-8"))

        # 控制台处理器
        handlers.append(logging.StreamHandler(sys.stdout))

        # 配置根日志记录器
        logging.basicConfig(
            level=log_level_obj,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=handlers,
            force=True,
        )

        # 压缩旧日志
        if rotation_enabled and compress_old_logs:
            _compress_old_logs(str(logs_path), backup_count)

        print(f"[日志] 日志文件: {log_file}")
        print(f"[日志] 日志级别: {log_level}")
        if rotation_enabled:
            print(
                f"[日志] 日志轮转: 已启用 (最大{max_bytes//1024//1024}MB, 保留{backup_count}个)"
            )

        return log_file

    except Exception as e:
        print(f"[错误] 日志设置失败: {e}")
        # 至少配置控制台输出
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        return ""


def _compress_old_logs(logs_dir: str, backup_count: int):
    """
    压缩旧的日志文件

    Args:
        logs_dir: 日志目录
        backup_count: 保留的备份数量
    """
    try:
        logs_path = Path(logs_dir)
        # 查找所有.log和.log.1, .log.2等文件
        log_files = []
        for filename in logs_path.iterdir():
            if filename.suffix == ".log" or (
                filename.name.startswith("inspection_") and ".log." in filename.name
            ):
                # 只压缩轮转的备份文件（.log.1, .log.2等）
                if ".log." in filename.name and not filename.name.endswith(".gz"):
                    log_files.append(filename)

        # 按修改时间排序，压缩最旧的
        log_files.sort(key=lambda x: os.path.getmtime(x))

        for log_file in log_files:
            try:
                # 压缩文件
                with open(log_file, "rb") as f_in:
                    with gzip.open(str(log_file) + ".gz", "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                # 删除原文件
                log_file.unlink()
            except Exception as e:
                # 忽略压缩错误
                pass

        # 清理过期的压缩日志
        gz_files = list(logs_path.glob("*.gz"))
        gz_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # 删除超过保留数量的旧压缩日志
        for gz_file in gz_files[backup_count:]:
            try:
                gz_file.unlink()
            except Exception:
                pass
    except Exception as e:
        # 忽略压缩错误，不影响主程序
        pass


def validate_device(device: Dict[str, Any]) -> Tuple[bool, str]:
    """
    验证设备信息是否完整有效

    Args:
        device: 设备信息字典

    Returns:
        (是否有效, 错误消息)
    """
    from .adapters import AdapterFactory

    return validate_cli_device(device, AdapterFactory.get_supported_vendors())


def update_devices_with_passwords(
    devices: List[Dict[str, Any]], passwords: Dict[str, Dict[str, str]]
) -> List[Dict[str, Any]]:
    """
    使用密码配置更新设备信息

    Args:
        devices: 设备列表
        passwords: 密码配置字典

    Returns:
        更新后的设备列表
    """
    for device in devices:
        vendor = device["vendor"]

        # 尝试获取厂商专用配置，否则使用默认配置
        pwd_config = passwords.get(vendor, passwords.get("default", {}))

        if not pwd_config:
            print(f"[警告] 设备 {device['name']} 没有找到密码配置")
            continue

        device["username"] = pwd_config.get("username", "")
        device["password"] = pwd_config.get("password", "")

    return devices


def filter_devices_by_group(
    devices: List[Dict[str, Any]], group: str = ""
) -> List[Dict[str, Any]]:
    """
    按分组过滤设备

    Args:
        devices: 设备列表
        group: 分组名称（空字符串表示所有设备）

    Returns:
        过滤后的设备列表
    """
    if not group:
        return devices

    filtered = []
    for device in devices:
        # 检查设备名中是否包含分组标识
        device_name = device.get("name", "")
        # 支持多种分组格式：分组名_设备名、[分组名]设备名、分组名-设备名
        if (
            f"{group}_" in device_name
            or f"[{group}]" in device_name
            or f"{group}-" in device_name
        ):
            filtered.append(device)

    return filtered


def get_device_groups(devices: List[Dict[str, Any]]) -> List[str]:
    """
    获取所有设备分组

    Args:
        devices: 设备列表

    Returns:
        分组名称列表
    """
    groups = set()
    for device in devices:
        device_name = device.get("name", "")
        # 提取分组标识
        if "_" in device_name:
            group = device_name.split("_")[0]
            groups.add(group)
        elif "[" in device_name and "]" in device_name:
            start = device_name.index("[") + 1
            end = device_name.index("]")
            group = device_name[start:end]
            groups.add(group)
        elif "-" in device_name:
            group = device_name.split("-")[0]
            groups.add(group)

    return sorted(list(groups))


def check_disk_space(required_mb: int = 100) -> Tuple[bool, int, str]:
    """
    检查磁盘空间是否足够

    Args:
        required_mb: 需要的最小空间（MB）

    Returns:
        (是否足够, 可用空间MB, 错误信息)
    """
    try:
        disk = shutil.disk_usage(COREBASE_ROOT)
        free_mb = disk.free / (1024 * 1024)

        if free_mb < required_mb:
            error_msg = (
                f"磁盘空间不足！需要至少 {required_mb}MB，当前可用 {free_mb:.1f}MB"
            )
            return False, int(free_mb), error_msg

        return True, int(free_mb), ""
    except Exception as e:
        error_msg = f"检查磁盘空间失败: {e}"
        return False, 0, error_msg


def print_banner(config: Dict[str, Any]):
    """
    打印程序横幅

    Args:
        config: 配置字典
    """
    version = config.get("version", "3.0.0")
    description = config.get("description", "简化优化版本")

    print("=" * 70)
    print("   网络设备巡检工具 | Network Device Inspection Tool")
    print("=" * 70)
    print(f"   版本: {version}")
    print(f"   描述: {description}")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()


def create_output_dirs(config: Dict[str, Any]):
    """
    创建输出目录

    Args:
        config: 配置字典
    """
    results_dir = config.get("output", {}).get("results_dir", "output/results")
    logs_dir = config.get("output", {}).get("logs_dir", "output/logs")

    results_path = resolve_corebase_path(results_dir)
    logs_path = resolve_corebase_path(logs_dir)

    results_path.mkdir(parents=True, exist_ok=True)
    logs_path.mkdir(parents=True, exist_ok=True)

    print(f"[输出] 结果目录: {results_path}")
    print(f"[输出] 日志目录: {logs_path}")
