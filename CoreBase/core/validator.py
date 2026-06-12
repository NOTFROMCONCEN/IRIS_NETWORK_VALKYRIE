#!/usr/bin/env python3
"""
配置验证模块
Configuration Validator Module

提供配置文件验证功能
"""

from typing import Dict, Any, List, Tuple
from pathlib import Path

from .paths import resolve_corebase_path


class ConfigValidator:
    """配置验证器"""

    # 配置项定义
    CONFIG_SCHEMA = {
        "version": {"type": str, "required": True, "default": "3.1.0"},
        "description": {"type": str, "required": False, "default": "新增跳板机支持"},
        "release_date": {"type": str, "required": False, "default": "2026-05-06"},
        "system": {
            "type": dict,
            "required": False,
            "default": {},
            "subkeys": {
                "timeout": {"type": int, "min": 1, "max": 600, "default": 60},
                "retries": {"type": int, "min": 0, "max": 10, "default": 3},
                "log_level": {
                    "type": str,
                    "options": ["DEBUG", "INFO", "WARNING", "ERROR"],
                    "default": "INFO",
                },
                "max_workers_precheck": {
                    "type": int,
                    "min": 1,
                    "max": 100,
                    "default": 20,
                },
                "max_workers_batch": {"type": int, "min": 1, "max": 50, "default": 5},
                "disk_space_check_mb": {
                    "type": int,
                    "min": 10,
                    "max": 10000,
                    "default": 100,
                },
                "low_power_mode": {"type": bool, "default": False},
                "password_error_disconnect": {"type": bool, "default": False},
            },
        },
        "network": {
            "type": dict,
            "required": False,
            "default": {},
            "subkeys": {
                "ssh_port": {"type": int, "min": 1, "max": 65535, "default": 22},
                "connect_timeout": {"type": int, "min": 1, "max": 300, "default": 60},
                "command_timeout": {"type": int, "min": 1, "max": 600, "default": 120},
                "jump_host": {
                    "type": dict,
                    "required": False,
                    "default": {},
                    "subkeys": {
                        "address": {"type": str, "default": ""},
                        "port": {"type": int, "min": 1, "max": 65535, "default": 22},
                        "username": {"type": str, "default": ""},
                        "password": {"type": str, "default": ""},
                        "connect_timeout": {"type": int, "min": 1, "max": 300, "default": 30},
                        "command_timeout": {"type": int, "min": 1, "max": 600, "default": 60},
                    },
                },
            },
        },
        "commands": {
            "type": dict,
            "required": False,
            "default": {},
            "subkeys": {
                "catalog_file": {"type": str, "default": "config/commands.yaml"},
            },
        },
        "output": {
            "type": dict,
            "required": False,
            "default": {},
            "subkeys": {
                "results_dir": {"type": str, "default": "output/results"},
                "logs_dir": {"type": str, "default": "output/logs"},
                "log_rotation": {
                    "type": dict,
                    "default": {},
                    "subkeys": {
                        "enabled": {"type": bool, "default": True},
                        "max_bytes": {
                            "type": int,
                            "min": 1024,
                            "max": 104857600,
                            "default": 10485760,
                        },
                        "backup_count": {
                            "type": int,
                            "min": 1,
                            "max": 30,
                            "default": 7,
                        },
                        "compress_old_logs": {"type": bool, "default": True},
                    },
                },
            },
        },
        "features": {
            "type": dict,
            "required": False,
            "default": {},
            "subkeys": {
                "auto_retry": {"type": bool, "default": True},
                "log_mode": {"type": bool, "default": True},
                "progress_bar": {"type": bool, "default": True},
            },
        },
    }

    def __init__(self, config: Dict[str, Any]):
        """
        初始化配置验证器

        Args:
            config: 配置字典
        """
        self.config = config
        self.errors = []
        self.warnings = []

    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """
        验证配置

        Returns:
            (是否有效, 错误列表, 警告列表)
        """
        self.errors = []
        self.warnings = []

        # 验证顶层配置项
        for key, schema in self.CONFIG_SCHEMA.items():
            self._validate_key(key, schema, self.config)

        return len(self.errors) == 0, self.errors, self.warnings

    def _validate_key(
        self,
        key: str,
        schema: Dict[str, Any],
        config: Dict[str, Any],
        parent_key: str = "",
    ):
        """
        验证单个配置项

        Args:
            key: 配置键
            schema: 配置模式
            config: 配置字典
            parent_key: 父键名
        """
        full_key = f"{parent_key}.{key}" if parent_key else key

        # 检查必需项
        if schema.get("required", False) and key not in config:
            self.errors.append(f"缺少必需配置项: {full_key}")
            return

        # 使用默认值
        value = config.get(key, schema.get("default"))

        # 检查类型
        expected_type = schema.get("type")
        if expected_type and not isinstance(value, expected_type):
            self.errors.append(
                f"配置项 {full_key} 类型错误: 期望 {expected_type.__name__}, 实际 {type(value).__name__}"
            )
            return

        # 验证子键
        subkeys = schema.get("subkeys", {})
        if subkeys and isinstance(value, dict):
            for subkey, subschema in subkeys.items():
                self._validate_key(subkey, subschema, value, full_key)
            return

        # 验证数值范围
        if expected_type == int:
            min_val = schema.get("min")
            max_val = schema.get("max")
            if min_val is not None and value < min_val:
                self.errors.append(f"配置项 {full_key} 值过小: {value} < {min_val}")
            if max_val is not None and value > max_val:
                self.errors.append(f"配置项 {full_key} 值过大: {value} > {max_val}")

        # 验证选项
        options = schema.get("options")
        if options and value not in options:
            self.errors.append(f"配置项 {full_key} 值无效: {value}, 可选值: {options}")

        # 验证路径
        if expected_type == str and (
            "dir" in key.lower() or key.lower().endswith("file")
        ):
            self._validate_path(full_key, value)

    def _validate_path(self, key: str, path: str):
        """
        验证路径配置

        Args:
            key: 配置键
            path: 路径
        """
        try:
            path_obj = resolve_corebase_path(path)
            # 检查路径是否可创建
            parent = path_obj.parent
            if not parent.exists():
                # 尝试创建父目录
                parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.warnings.append(f"配置项 {key} 路径可能无效: {path} ({e})")

    def print_report(self):
        """打印验证报告"""
        if not self.errors and not self.warnings:
            print("[验证] 配置验证通过 [OK]")
            return

        if self.errors:
            print("\n[错误] 配置验证失败:")
            for error in self.errors:
                print(f"  [FAIL] {error}")

        if self.warnings:
            print("\n[警告] 配置验证警告:")
            for warning in self.warnings:
                print(f"  ! {warning}")


def validate_config(config: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
    """
    验证配置文件

    Args:
        config: 配置字典

    Returns:
        (是否有效, 错误列表, 警告列表)
    """
    validator = ConfigValidator(config)
    return validator.validate()
