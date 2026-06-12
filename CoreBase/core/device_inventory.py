#!/usr/bin/env python3
"""
设备清单读写模块。

统一 CLI 与 UI 对 Excel 设备清单的读取、转换与保存逻辑。
"""

import ipaddress
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import pandas as pd

from .paths import resolve_corebase_path


REQUIRED_COLUMNS = ["设备名", "IP地址", "生产厂商"]


def validate_inventory_device(device: Dict[str, Any]) -> Tuple[bool, str]:
    """验证并标准化统一设备模型。"""
    required_fields = {
        "name": "设备名",
        "ip": "IP地址",
        "vendor": "生产厂商",
    }

    for field, display_name in required_fields.items():
        value = str(device.get(field, "")).strip()
        if not value:
            return False, f"字段 '{display_name}' 不能为空"
        device[field] = value

    device["vendor"] = device["vendor"].lower()
    device["vendor_raw"] = str(
        device.get("vendor_raw") or device.get("vendor", "")
    ).strip()
    device["remark"] = str(device.get("remark", "")).strip()

    try:
        ipaddress.ip_address(device["ip"])
    except ValueError:
        return False, f"无效的IP地址格式: {device['ip']}"

    try:
        port = int(device.get("port", 22))
    except (TypeError, ValueError):
        return False, f"无效的端口格式: {device.get('port', '')}"

    if not 1 <= port <= 65535:
        return False, f"端口超出范围: {port}"
    device["port"] = port

    # 验证跳板机配置（可选字段）
    jump_host = device.get("jump_host")
    if jump_host:
        # 验证跳板机地址格式
        try:
            ipaddress.ip_address(jump_host)
        except ValueError:
            return False, f"无效的跳板机IP地址格式: {jump_host}"

        # 验证跳板机端口
        try:
            jump_port = int(device.get("jump_port", 22))
        except (TypeError, ValueError):
            return False, f"无效的跳板机端口格式: {device.get('jump_port', '')}"

        if not 1 <= jump_port <= 65535:
            return False, f"跳板机端口超出范围: {jump_port}"
        device["jump_port"] = jump_port

        # 验证跳板机用户名
        jump_username = str(device.get("jump_username", "")).strip()
        if not jump_username:
            return False, "配置跳板机时必须提供跳板机用户名"
        device["jump_username"] = jump_username
        
        # 验证认证方式：密码或密钥至少提供一种
        jump_password = str(device.get("jump_password", "")).strip()
        jump_key_path = str(device.get("jump_key_path", "")).strip()
        
        if not jump_password and not jump_key_path:
            return False, "配置跳板机时必须提供密码或SSH密钥路径"
        
        device["jump_password"] = jump_password
        device["jump_key_path"] = jump_key_path
        device["jump_key_type"] = str(device.get("jump_key_type", "")).strip()
    else:
        # 如果没有配置跳板机，设置默认值
        device["jump_host"] = None
        device["jump_port"] = 22
        device["jump_username"] = ""
        device["jump_password"] = ""
        device["jump_key_path"] = ""
        device["jump_key_type"] = ""

    return True, ""


def validate_cli_device(
    device: Dict[str, Any], supported_vendors: Iterable[str] | None = None
) -> Tuple[bool, str]:
    """验证 CLI 使用的设备模型。"""
    inventory_device = {
        "name": device.get("name", ""),
        "ip": device.get("ip", ""),
        "vendor": device.get("vendor", ""),
        "vendor_raw": device.get("vendor", ""),
        "port": device.get("port", 22),
        "remark": device.get("remark", ""),
        # 跳板机配置
        "jump_host": device.get("jump_host"),
        "jump_port": device.get("jump_port", 22),
        "jump_username": device.get("jump_username", ""),
        "jump_password": device.get("jump_password", ""),
    }

    is_valid, error_msg = validate_inventory_device(inventory_device)
    if not is_valid:
        return False, error_msg

    for field in ["username", "password"]:
        value = str(device.get(field, "")).strip()
        if not value:
            return False, f"缺少必要字段或字段为空: {field}"
        device[field] = value

    device["name"] = inventory_device["name"]
    device["ip"] = inventory_device["ip"]
    device["vendor"] = inventory_device["vendor"]
    device["port"] = inventory_device["port"]
    device["remark"] = inventory_device.get("remark", "")
    # 跳板机配置
    device["jump_host"] = inventory_device.get("jump_host")
    device["jump_port"] = inventory_device.get("jump_port", 22)
    device["jump_username"] = inventory_device.get("jump_username", "")
    device["jump_password"] = inventory_device.get("jump_password", "")

    if supported_vendors is not None and device["vendor"] not in set(supported_vendors):
        return False, f"不支持的厂商: {device['vendor']}"

    return True, ""


def validate_ui_device(device: Dict[str, Any]) -> Tuple[bool, str]:
    """验证 UI 使用的设备模型。"""
    inventory_device = ui_to_inventory_device(device)
    is_valid, error_msg = validate_inventory_device(inventory_device)
    if not is_valid:
        return False, error_msg

    device.clear()
    device.update(inventory_to_ui_device(inventory_device))
    return True, ""


def read_device_inventory(
    excel_file: str | Path,
) -> Tuple[Path, List[Dict[str, Any]], List[str]]:
    """读取设备清单并返回统一字段模型。"""
    excel_path = resolve_corebase_path(excel_file)
    warnings: List[str] = []

    if not excel_path.exists():
        raise FileNotFoundError(str(excel_path))

    df = pd.read_excel(excel_path)
    missing_cols = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Excel缺少必需列: {missing_cols}；当前列: {list(df.columns)}")

    devices: List[Dict[str, Any]] = []
    for index, row in df.iterrows():
        if any(pd.isna(row.get(col)) for col in REQUIRED_COLUMNS):
            warnings.append(f"跳过缺少必需信息的行 {index + 2}: {row.to_dict()}")
            continue

        raw_vendor = str(row["生产厂商"]).strip()
        port = 22
        if "端口" in df.columns and pd.notna(row["端口"]):
            try:
                port = int(row["端口"])
            except (ValueError, TypeError):
                warnings.append(
                    f"设备 {row.get('设备名', 'unknown')} 端口格式无效，使用默认端口22"
                )
                port = 22

        remark = ""
        if "备注" in df.columns and pd.notna(row["备注"]):
            remark = str(row["备注"]).strip()

        # 读取跳板机配置（可选字段）
        jump_host = None
        jump_port = 22
        jump_username = ""
        jump_password = ""
        jump_key_path = ""
        jump_key_type = ""
        
        def _get_cell_str(row_data, col_name: str, default: str = "") -> str:
            """安全获取单元格字符串值"""
            if col_name not in df.columns:
                return default
            val = row_data.get(col_name)
            if pd.isna(val):
                return default
            return str(val).strip()
        
        def _get_cell_int(row_data, col_name: str, default: int) -> int:
            """安全获取单元格整数值"""
            if col_name not in df.columns:
                return default
            val = row_data.get(col_name)
            if pd.isna(val):
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                warnings.append(
                    f"设备 {row.get('设备名', 'unknown')} {col_name}格式无效，使用默认值{default}"
                )
                return default
        
        jump_host = _get_cell_str(row, "跳板机地址") or None
        jump_port = _get_cell_int(row, "跳板机端口", 22)
        jump_username = _get_cell_str(row, "跳板机用户名")
        jump_password = _get_cell_str(row, "跳板机密码")
        jump_key_path = _get_cell_str(row, "跳板机密钥路径")
        jump_key_type = _get_cell_str(row, "跳板机密钥类型")

        device = {
            "name": str(row["设备名"]).strip(),
            "ip": str(row["IP地址"]).strip(),
            "vendor": raw_vendor.lower(),
            "vendor_raw": raw_vendor,
            "port": port,
            "remark": remark,
            # 跳板机配置
            "jump_host": jump_host,
            "jump_port": jump_port,
            "jump_username": jump_username,
            "jump_password": jump_password,
            "jump_key_path": jump_key_path,
            "jump_key_type": jump_key_type,
        }

        is_valid, error_msg = validate_inventory_device(device)
        if not is_valid:
            warnings.append(
                f"跳过无效设备 {device.get('name', 'unknown')}: {error_msg}"
            )
            continue

        devices.append(device)

    return excel_path, devices, warnings


def inventory_to_cli_device(device: Dict[str, Any]) -> Dict[str, Any]:
    """将统一设备模型转换为 CLI 使用的字段结构。"""
    return {
        "name": device["name"],
        "ip": device["ip"],
        "vendor": device["vendor"],
        "model": device["name"],
        "port": int(device.get("port", 22)),
        "username": "",
        "password": "",
        "remark": device.get("remark", ""),
        # 跳板机配置
        "jump_host": device.get("jump_host"),
        "jump_port": int(device.get("jump_port", 22)),
        "jump_username": device.get("jump_username", ""),
        "jump_password": device.get("jump_password", ""),
    }


def inventory_to_ui_device(device: Dict[str, Any]) -> Dict[str, str]:
    """将统一设备模型转换为 UI 使用的字段结构。"""
    return {
        "设备名": device["name"],
        "IP地址": device["ip"],
        "生产厂商": device.get("vendor_raw") or device["vendor"],
        "端口": str(device.get("port", 22)),
        "备注": device.get("remark", ""),
        # 跳板机配置
        "跳板机地址": device.get("jump_host", ""),
        "跳板机端口": str(device.get("jump_port", 22)),
        "跳板机用户名": device.get("jump_username", ""),
        "跳板机密码": device.get("jump_password", ""),
    }


def ui_to_inventory_device(device: Dict[str, Any]) -> Dict[str, Any]:
    """将 UI 设备记录转换为统一设备模型。"""
    raw_vendor = str(device.get("生产厂商", "")).strip()
    try:
        port = int(str(device.get("端口", "22")).strip() or "22")
    except (TypeError, ValueError):
        port = 22

    # 跳板机配置
    jump_host = str(device.get("跳板机地址", "")).strip() or None
    try:
        jump_port = int(str(device.get("跳板机端口", "22")).strip() or "22")
    except (TypeError, ValueError):
        jump_port = 22
    jump_username = str(device.get("跳板机用户名", "")).strip()
    jump_password = str(device.get("跳板机密码", "")).strip()

    return {
        "name": str(device.get("设备名", "")).strip(),
        "ip": str(device.get("IP地址", "")).strip(),
        "vendor": raw_vendor.lower(),
        "vendor_raw": raw_vendor,
        "port": port,
        "remark": str(device.get("备注", "")).strip(),
        # 跳板机配置
        "jump_host": jump_host,
        "jump_port": jump_port,
        "jump_username": jump_username,
        "jump_password": jump_password,
    }


def write_device_inventory(
    excel_file: str | Path, devices: List[Dict[str, Any]]
) -> Path:
    """将统一设备模型写回 Excel（原子写入，避免读取半完成文件）。"""
    excel_path = resolve_corebase_path(excel_file)
    excel_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for device in devices:
        row = {
            "设备名": device.get("name", ""),
            "IP地址": device.get("ip", ""),
            "生产厂商": device.get("vendor_raw") or device.get("vendor", ""),
            "端口": int(device.get("port", 22)),
            "备注": device.get("remark", ""),
        }
        
        # 跳板机配置（可选字段）
        if device.get("jump_host"):
            row["跳板机地址"] = device.get("jump_host", "")
            row["跳板机端口"] = int(device.get("jump_port", 22))
            row["跳板机用户名"] = device.get("jump_username", "")
            row["跳板机密码"] = device.get("jump_password", "")
        
        rows.append(row)

    # 原子写入：先写入临时文件，再用 replace() 替换目标文件
    tmp_path = excel_path.with_suffix(".tmp")
    pd.DataFrame(rows).to_excel(tmp_path, index=False)
    tmp_path.replace(excel_path)
    return excel_path
