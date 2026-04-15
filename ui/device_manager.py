#!/usr/bin/env python3
"""
设备管理器 - 用于管理Excel设备文件的增删改查操作
"""

import os
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple
import tempfile
import shutil
from datetime import datetime, timedelta


class DeviceManager:
    """设备管理器类，负责设备Excel文件的CRUD操作"""
    
    def __init__(self, excel_file: str = "devices/devices.xlsx"):
        """
        初始化设备管理器
        
        Args:
            excel_file: Excel文件路径
        """
        self.excel_file = excel_file
        self.backup_dir = "devices/backups"
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
            df = pd.read_excel(self.excel_file)
            devices = []
            
            # 检查必需的列
            required_cols = ["设备名", "IP地址", "生产厂商"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                print(f"[错误] Excel缺少必需列: {missing_cols}")
                return []
            
            for _, row in df.iterrows():
                if pd.isna(row.get("设备名")) or pd.isna(row.get("IP地址")) or pd.isna(row.get("生产厂商")):
                    continue
                
                device = {
                    "设备名": str(row["设备名"]).strip(),
                    "IP地址": str(row["IP地址"]).strip(),
                    "生产厂商": str(row["生产厂商"]).strip(),
                }
                
                # 添加可选字段
                if "端口" in df.columns and pd.notna(row["端口"]):
                    device["端口"] = str(row["端口"]).strip()
                else:
                    device["端口"] = "22"
                
                if "备注" in df.columns and pd.notna(row["备注"]):
                    device["备注"] = str(row["备注"]).strip()
                else:
                    device["备注"] = ""
                
                devices.append(device)
            
            return devices
            
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
            
            # 转换为DataFrame
            df_data = []
            for device in devices:
                row = {
                    "设备名": device.get("设备名", ""),
                    "IP地址": device.get("IP地址", ""),
                    "生产厂商": device.get("生产厂商", ""),
                    "端口": device.get("端口", "22"),
                    "备注": device.get("备注", ""),
                }
                df_data.append(row)
            
            df = pd.DataFrame(df_data)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(self.excel_file), exist_ok=True)
            
            # 保存到Excel
            df.to_excel(self.excel_file, index=False)
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
            device for device in devices 
            if device.get("设备名", "").strip() != device_name.strip()
        ]
        
        if len(filtered_devices) == original_count:
            print(f"[错误] 未找到设备: {device_name}")
            return False
        
        return self.save_devices(filtered_devices)
    
    def search_devices(self, keyword: str = "", vendor: str = "") -> List[Dict[str, Any]]:
        """
        搜索设备
        
        Args:
            keyword: 搜索关键词（设备名或IP地址）
            vendor: 厂商过滤
            
        Returns:
            匹配的设备列表
        """
        devices = self.load_devices()
        
        if not keyword and not vendor:
            return devices
        
        filtered_devices = []
        keyword = keyword.lower().strip()
        vendor_filter = vendor.lower().strip()
        
        for device in devices:
            match = True
            
            if keyword:
                device_name = device.get("设备名", "").lower()
                ip_address = device.get("IP地址", "").lower()
                if keyword not in device_name and keyword not in ip_address:
                    match = False
            
            if vendor_filter:
                device_vendor = device.get("生产厂商", "").lower()
                if vendor_filter not in device_vendor:
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
    
    def validate_device(self, device: Dict[str, Any]) -> Tuple[bool, str]:
        """
        验证设备信息
        
        Args:
            device: 设备信息字典
            
        Returns:
            (是否有效, 错误信息)
        """
        # 检查必需字段
        required_fields = ["设备名", "IP地址", "生产厂商"]
        for field in required_fields:
            if not device.get(field, "").strip():
                return False, f"字段 '{field}' 不能为空"
        
        # 验证IP地址格式（简单验证）
        ip_address = device.get("IP地址", "").strip()
        ip_parts = ip_address.split(".")
        if len(ip_parts) != 4:
            return False, "IP地址格式无效"
        
        try:
            for part in ip_parts:
                num = int(part)
                if num < 0 or num > 255:
                    return False, "IP地址格式无效"
        except ValueError:
            return False, "IP地址格式无效"
        
        # 验证端口号
        port = device.get("端口", "22").strip()
        if port:
            try:
                port_num = int(port)
                if port_num < 1 or port_num > 65535:
                    return False, "端口号必须在1-65535之间"
            except ValueError:
                return False, "端口号必须是数字"
        
        return True, ""
    
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
                if filename.startswith("devices_backup_") and filename.endswith(".xlsx"):
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
            "last_modified": os.path.getmtime(self.excel_file) if os.path.exists(self.excel_file) else None,
        }

