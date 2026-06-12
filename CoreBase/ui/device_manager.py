#!/usr/bin/env python3
"""
设备管理器 - 用于管理Excel设备文件的增删改查操作
"""

import os
from typing import List, Dict, Any, Optional, Tuple
import tempfile
import shutil
from datetime import datetime, timedelta

try:
    from ..core.adapters import AdapterFactory
    from ..core.device_inventory import (
        inventory_to_ui_device,
        read_device_inventory,
        ui_to_inventory_device,
        validate_ui_device,
        write_device_inventory,
    )
    from ..core.paths import resolve_corebase_path
except ImportError:
    from core.adapters import AdapterFactory
    from core.device_inventory import (
        inventory_to_ui_device,
        read_device_inventory,
        ui_to_inventory_device,
        validate_ui_device,
        write_device_inventory,
    )
    from core.paths import resolve_corebase_path


class DeviceManager:
    """设备管理器类，负责设备Excel文件的CRUD操作"""

    def __init__(self, excel_file: str = "devices/devices.xlsx"):
        """
        初始化设备管理器

        Args:
            excel_file: Excel文件路径
        """
        self.excel_file = str(resolve_corebase_path(excel_file))
        self.backup_dir = str(resolve_corebase_path("devices/backups"))
        self._ensure_backup_dir()

    def _ensure_backup_dir(self):
        """确保备份目录存在"""
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir, exist_ok=True)

    def load_devices(self) -> List[Dict[str, Any]]:
        """
        加载设备列表

        Returns:
            设备字典列表
        """
        if not os.path.exists(self.excel_file):
            return []

        try:
            _, devices, warnings = read_device_inventory(self.excel_file)
            for warning in warnings:
                print(f"[警告] {warning}")
            return [inventory_to_ui_device(device) for device in devices]

        except ValueError as e:
            print(f"[错误] {e}")
            return []

        except Exception as e:
            print(f"[错误] 加载设备失败: {e}")
            return []

    def save_devices(self, devices: List[Dict[str, Any]]) -> bool:
        """
        保存设备列表到Excel文件

        Args:
            devices: 设备字典列表

        Returns:
            是否保存成功
        """
        try:
            # 创建备份
            self._create_backup()

            inventory_devices = [ui_to_inventory_device(device) for device in devices]
            write_device_inventory(self.excel_file, inventory_devices)
            print(f"[成功] 设备已保存到: {self.excel_file}")
            return True

        except Exception as e:
            print(f"[错误] 保存设备失败: {e}")
            return False

    def add_device(self, device: Dict[str, Any]) -> bool:
        """
        添加新设备

        Args:
            device: 设备信息字典

        Returns:
            是否添加成功
        """
        devices = self.load_devices()

        # 检查设备名是否已存在
        device_name = device.get("设备名", "").strip()
        for existing_device in devices:
            if existing_device.get("设备名", "").strip() == device_name:
                print(f"[错误] 设备名 '{device_name}' 已存在")
                return False

        # 检查IP地址是否已存在
        ip_address = device.get("IP地址", "").strip()
        for existing_device in devices:
            if existing_device.get("IP地址", "").strip() == ip_address:
                print(f"[警告] IP地址 '{ip_address}' 已存在")

        devices.append(device)
        return self.save_devices(devices)

    def update_device(self, device_name: str, updated_device: Dict[str, Any]) -> bool:
        """
        更新设备信息

        Args:
            device_name: 要更新的设备名
            updated_device: 更新后的设备信息

        Returns:
            是否更新成功
        """
        devices = self.load_devices()
        found = False

        for i, device in enumerate(devices):
            if device.get("设备名", "").strip() == device_name.strip():
                # 保留原始设备名（不允许修改设备名）
                updated_device["设备名"] = device_name.strip()
                devices[i] = updated_device
                found = True
                break

        if not found:
            print(f"[错误] 未找到设备: {device_name}")
            return False

        return self.save_devices(devices)

    def delete_device(self, device_name: str) -> bool:
        """
        删除设备

        Args:
            device_name: 要删除的设备名

        Returns:
            是否删除成功
        """
        devices = self.load_devices()
        original_count = len(devices)

        # 过滤掉要删除的设备
        filtered_devices = [
            device
            for device in devices
            if device.get("设备名", "").strip() != device_name.strip()
        ]

        if len(filtered_devices) == original_count:
            print(f"[错误] 未找到设备: {device_name}")
            return False

        return self.save_devices(filtered_devices)

    @staticmethod
    def _matches_group(device_name: str, group: str) -> bool:
        """按 CLI 同样的规则判断设备是否属于指定分组。"""
        if not group:
            return True
        return (
            f"{group}_" in device_name
            or f"[{group}]" in device_name
            or f"{group}-" in device_name
        )

    def search_devices(
        self, keyword: str = "", vendor: str = "", group: str = ""
    ) -> List[Dict[str, Any]]:
        """
        搜索设备

        Args:
            keyword: 搜索关键词（设备名或IP地址）
            vendor: 厂商过滤
            group: 分组过滤

        Returns:
            匹配的设备列表
        """
        devices = self.load_devices()

        if not keyword and not vendor and not group:
            return devices

        filtered_devices = []
        keyword = keyword.lower().strip()
        vendor_filter = vendor.lower().strip()
        group_filter = group.strip()

        for device in devices:
            match = True
            device_name_raw = device.get("设备名", "").strip()

            if keyword:
                device_name = device_name_raw.lower()
                ip_address = device.get("IP地址", "").lower()
                if keyword not in device_name and keyword not in ip_address:
                    match = False

            if vendor_filter:
                device_vendor = device.get("生产厂商", "").lower()
                if vendor_filter not in device_vendor:
                    match = False

            if group_filter and not self._matches_group(device_name_raw, group_filter):
                match = False

            if match:
                filtered_devices.append(device)

        return filtered_devices

    def get_vendors(self) -> List[str]:
        """
        获取所有厂商列表

        Returns:
            厂商列表
        """
        devices = self.load_devices()
        vendors = set()

        for device in devices:
            vendor = device.get("生产厂商", "").strip()
            if vendor:
                vendors.add(vendor)

        return sorted(list(vendors))

    def get_supported_vendors(self) -> List[str]:
        """获取程序当前支持的厂商关键字列表。"""
        return AdapterFactory.get_supported_vendors()

    def get_vendor_options(self) -> List[str]:
        """获取 UI 可选厂商：现有厂商 + 当前程序支持厂商。"""
        configured_vendors = self.get_vendors()
        configured_keys = {vendor.lower() for vendor in configured_vendors}

        options = configured_vendors.copy()
        for vendor in self.get_supported_vendors():
            if vendor.lower() not in configured_keys:
                options.append(vendor)

        return options

    def get_device_groups(self) -> List[str]:
        """从当前设备清单中提取可用分组。"""
        groups = set()
        for device in self.load_devices():
            device_name = str(device.get("设备名", "")).strip()
            if "_" in device_name:
                groups.add(device_name.split("_", 1)[0])
            elif "[" in device_name and "]" in device_name:
                start = device_name.index("[") + 1
                end = device_name.index("]")
                groups.add(device_name[start:end])
            elif "-" in device_name:
                groups.add(device_name.split("-", 1)[0])

        return sorted(group for group in groups if group)

    def validate_device(self, device: Dict[str, Any]) -> Tuple[bool, str]:
        """
        验证设备信息

        Args:
            device: 设备信息字典

        Returns:
            (是否有效, 错误信息)
        """
        return validate_ui_device(device)

    def _create_backup(self):
        """创建文件备份"""
        if not os.path.exists(self.excel_file):
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(self.backup_dir, f"devices_backup_{timestamp}.xlsx")

        try:
            shutil.copy2(self.excel_file, backup_file)
            print(f"[信息] 已创建备份: {backup_file}")
            # 创建备份后清理旧备份
            self._cleanup_old_backups()
        except Exception as e:
            print(f"[警告] 创建备份失败: {e}")

    def _cleanup_old_backups(self, keep_count: int = 10):
        """
        清理旧的备份文件

        Args:
            keep_count: 保留的备份数量
        """
        if not os.path.exists(self.backup_dir):
            return

        try:
            # 获取所有备份文件
            backup_files = []
            for filename in os.listdir(self.backup_dir):
                if filename.startswith("devices_backup_") and filename.endswith(
                    ".xlsx"
                ):
                    filepath = os.path.join(self.backup_dir, filename)
                    backup_files.append((filepath, os.path.getmtime(filepath)))

            # 按修改时间排序（最新的在前）
            backup_files.sort(key=lambda x: x[1], reverse=True)

            # 删除超过保留数量的旧备份
            if len(backup_files) > keep_count:
                for filepath, _ in backup_files[keep_count:]:
                    try:
                        os.remove(filepath)
                        print(f"[清理] 已删除旧备份: {os.path.basename(filepath)}")
                    except Exception as e:
                        print(f"[警告] 删除备份失败 {filepath}: {e}")

            # 也可以清理超过7天的备份
            cutoff_time = datetime.now() - timedelta(days=7)
            for filepath, mtime in backup_files:
                if datetime.fromtimestamp(mtime) < cutoff_time:
                    try:
                        os.remove(filepath)
                        print(f"[清理] 已删除过期备份: {os.path.basename(filepath)}")
                    except Exception:
                        pass
        except Exception as e:
            print(f"[警告] 清理旧备份失败: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取设备统计信息

        Returns:
            统计信息字典
        """
        devices = self.load_devices()

        # 按厂商统计
        vendor_stats = {}
        for device in devices:
            vendor = device.get("生产厂商", "未知")
            vendor_stats[vendor] = vendor_stats.get(vendor, 0) + 1

        return {
            "total_devices": len(devices),
            "vendor_stats": vendor_stats,
            "file_path": self.excel_file,
            "last_modified": (
                os.path.getmtime(self.excel_file)
                if os.path.exists(self.excel_file)
                else None
            ),
        }
