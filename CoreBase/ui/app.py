#!/usr/bin/env python3
"""
设备管理UI应用 - 基于Streamlit的设备增删改查界面
"""

import subprocess
import threading
import queue
import time
import os
import sys
from pathlib import Path
from typing import Tuple

import streamlit as st
import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ui.device_manager import DeviceManager


def show_success_message(message: str, auto_close: bool = False):
    """显示成功消息"""
    st.success(f"✅ {message}")


def show_error_message(message: str, details: str = None):
    """显示错误消息"""
    st.error(f"❌ {message}")
    if details:
        with st.expander("查看详细信息"):
            st.code(details, language="text")


def show_warning_message(message: str):
    """显示警告消息"""
    st.warning(f"⚠️ {message}")


def show_info_message(message: str):
    """显示信息消息"""
    st.info(f"ℹ️ {message}")


def show_loading(message: str = "正在处理..."):
    """显示加载状态"""
    return st.spinner(f"⏳ {message}")


def init_session_state():
    """初始化会话状态"""
    if 'device_manager' not in st.session_state:
        st.session_state.device_manager = DeviceManager()
    if 'refresh_counter' not in st.session_state:
        st.session_state.refresh_counter = 0
    if 'edit_device_name' not in st.session_state:
        st.session_state.edit_device_name = None
    if 'inspection_running' not in st.session_state:
        st.session_state.inspection_running = False
    if 'inspection_output' not in st.session_state:
        st.session_state.inspection_output = ""


def show_header():
    """显示页面标题"""
    st.set_page_config(
        page_title="网络设备管理",
        page_icon="🖧",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    st.title("🖧 网络设备管理系统")
    st.markdown("---")
    
    # 显示统计信息
    manager = st.session_state.device_manager
    stats = manager.get_statistics()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📦 设备总数", stats["total_devices"])
    with col2:
        st.metric("🏭 厂商数量", len(stats["vendor_stats"]))
    with col3:
        if stats["last_modified"]:
            from datetime import datetime
            last_mod = datetime.fromtimestamp(stats["last_modified"]).strftime("%Y-%m-%d %H:%M")
            st.metric("🕒 最后修改", last_mod)
        else:
            st.metric("🕒 最后修改", "无")
    with col4:
        st.metric("📄 文件路径", "devices.xlsx")
    
    st.markdown("---")


def show_sidebar():
    """显示侧边栏"""
    with st.sidebar:
        st.header("📊 操作菜单")
        
        # 操作选择
        operation = st.radio(
            "选择操作",
            ["📋 查看设备", "➕ 添加设备", "✏️ 编辑设备", "🗑️ 删除设备", "📈 统计分析", "📦 导入导出", "🚀 启动巡检"],
            key="operation_select"
        )
        
        st.markdown("---")
        
        # 搜索和过滤
        st.header("🔍 搜索过滤")
        search_keyword = st.text_input("搜索设备名或IP地址", "")
        vendor_filter = st.selectbox(
            "按厂商过滤",
            ["全部厂商"] + st.session_state.device_manager.get_vendors()
        )
        
        st.markdown("---")
        
        # 文件操作
        st.header("💾 文件操作")
        if st.button("🔄 刷新数据", use_container_width=True):
            with show_loading("正在刷新数据..."):
                st.session_state.refresh_counter += 1
                st.rerun()
        
        st.markdown("---")
        
        # 帮助信息
        with st.expander("ℹ️ 使用帮助"):
            st.markdown("""
            **设备字段说明:**
            - **设备名**: 设备的唯一标识名称
            - **IP地址**: 设备的IP地址
            - **生产厂商**: 设备厂商（如华为、H3C等）
            - **端口**: SSH端口，默认22
            - **备注**: 设备备注信息
            
            **支持的操作:**
            1. 查看所有设备列表
            2. 添加新设备
            3. 编辑现有设备
            4. 删除设备
            5. 搜索和过滤设备
            6. 导入/导出数据
            7. 启动设备巡检
            """)
    
    return operation, search_keyword, vendor_filter


def show_device_table(search_keyword="", vendor_filter="全部厂商"):
    """显示设备表格"""
    manager = st.session_state.device_manager
    
    # 获取设备列表
    vendor = vendor_filter if vendor_filter != "全部厂商" else ""
    devices = manager.search_devices(search_keyword, vendor)
    
    if not devices:
        show_warning_message("没有找到符合条件的设备")
        return
    
    # 转换为DataFrame显示
    df = pd.DataFrame(devices)
    
    # 显示表格
    st.subheader(f"📋 设备列表 (共 {len(devices)} 台)")
    
    # 使用st.data_editor实现可编辑表格
    edited_df = st.data_editor(
        df,
        column_config={
            "设备名": st.column_config.TextColumn("设备名", width="medium", required=True),
            "IP地址": st.column_config.TextColumn("IP地址", width="medium", required=True),
            "生产厂商": st.column_config.SelectboxColumn(
                "生产厂商",
                width="medium",
                options=manager.get_vendors(),
                required=True
            ),
            "端口": st.column_config.NumberColumn("端口", width="small", min_value=1, max_value=65535, default=22, help="SSH 端口号，默认 22"),
            "备注": st.column_config.TextColumn("备注", width="large"),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key="device_table"
    )
    
    # 保存修改
    if not edited_df.equals(df):
        if st.button("💾 保存所有修改", type="primary", use_container_width=True):
            try:
                with show_loading("正在保存设备信息..."):
                    # 转换为设备列表
                    updated_devices = edited_df.to_dict('records')
                    if manager.save_devices(updated_devices):
                        show_success_message(f"成功保存 {len(updated_devices)} 台设备信息")
                        st.session_state.refresh_counter += 1
                        st.rerun()
                    else:
                        show_error_message("保存失败，请检查数据格式")
            except Exception as e:
                show_error_message("保存失败", str(e))


def export_selected_devices(df):
    """导出选中的设备到 CSV"""
    if df.empty:
        show_warning_message("没有设备可导出")
        return
    
    csv = df.to_csv(index=False).encode('utf-8-sig')
    
    st.download_button(
        label="📥 下载选中的设备 CSV",
        data=csv,
        file_name=f"devices_export_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )


import re


def validate_ip_address(ip: str) -> Tuple[bool, str]:
    """验证 IP 地址格式"""
    if not ip:
        return False, "IP 地址不能为空"
    
    # IPv4 验证
    ipv4_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    if re.match(ipv4_pattern, ip):
        octets = ip.split('.')
        if all(0 <= int(octet) <= 255 for octet in octets):
            return True, ""
        else:
            return False, "IP 地址的每个字节必须在 0-255 之间"
    
    # IPv6 验证（简化版）
    if ':' in ip:
        return True, ""  # 简化处理，接受 IPv6 格式
    
    return False, "请输入有效的 IP 地址格式（如 192.168.1.1）"


def show_add_device_form():
    """显示添加设备表单"""
    st.subheader("➕ 添加新设备")

    submitted, device, errors = render_device_form(
        form_key="add_device_form",
        submit_label="✅ 添加设备",
    )

    if not submitted:
        return

    if errors:
        show_error_message("表单验证失败", "\n".join(f"  • {error}" for error in errors))
        return

    manager = st.session_state.device_manager
    is_valid, error_msg = manager.validate_device(device)

    if not is_valid:
        show_error_message("设备信息无效", error_msg)
        return

    with show_loading("正在添加设备..."):
        if manager.add_device(device):
            show_success_message(f"设备 '{device['设备名']}' 添加成功")
            st.session_state.refresh_counter += 1
            st.rerun()
        else:
            show_error_message("添加设备失败", "设备名可能已存在")


def show_edit_device_form():
    """显示编辑设备表单"""
    st.subheader("✏️ 编辑设备")
    
    manager = st.session_state.device_manager
    devices = manager.load_devices()
    
    if not devices:
        show_warning_message("没有可编辑的设备")
        return
    
    # 选择要编辑的设备
    device_names = [d["设备名"] for d in devices]
    selected_device = st.selectbox("选择要编辑的设备", device_names)
    
    if selected_device:
        # 获取设备信息
        device_info = None
        for device in devices:
            if device["设备名"] == selected_device:
                device_info = device
                break
        
        if device_info:
            submitted, updated_device, errors = render_device_form(
                form_key="edit_device_form",
                submit_label="💾 保存修改",
                initial_device=device_info,
                lock_device_name=True,
            )

            if not submitted:
                return

            if errors:
                show_error_message("表单验证失败", "\n".join(f"  • {error}" for error in errors))
                return

            updated_device["设备名"] = selected_device

            is_valid, error_msg = manager.validate_device(updated_device)

            if not is_valid:
                show_error_message("设备信息无效", error_msg)
                return

            with show_loading("正在更新设备..."):
                if manager.update_device(selected_device, updated_device):
                    show_success_message(f"设备 '{selected_device}' 更新成功")
                    st.session_state.refresh_counter += 1
                    st.rerun()
                else:
                    show_error_message("更新设备失败")


def render_device_form(
    form_key: str,
    submit_label: str,
    initial_device: dict = None,
    lock_device_name: bool = False,
):
    """渲染设备表单并返回 (submitted, device, errors)"""
    manager = st.session_state.device_manager
    initial = initial_device or {}

    def _safe_port(value):
        try:
            port_num = int(value)
            return port_num if 1 <= port_num <= 65535 else 22
        except (TypeError, ValueError):
            return 22

    with st.form(form_key):
        col1, col2 = st.columns(2)

        with col1:
            if lock_device_name:
                device_name = str(initial.get("设备名", "")).strip()
                st.text_input("设备名", value=device_name, disabled=True)
            else:
                device_name = st.text_input(
                    "设备名 *",
                    value=str(initial.get("设备名", "")),
                    placeholder="请输入设备名称",
                )

            ip_address = st.text_input(
                "IP地址 *",
                value=str(initial.get("IP地址", "")),
                placeholder="例如: 192.168.1.1",
            )

        with col2:
            vendor_options = manager.get_vendors()
            select_options = vendor_options + ["其他"]
            current_vendor = str(initial.get("生产厂商", "")).strip()

            if current_vendor and current_vendor not in vendor_options:
                default_vendor_index = len(select_options) - 1
            else:
                default_vendor_index = vendor_options.index(current_vendor) if current_vendor in vendor_options else 0

            selected_vendor = st.selectbox(
                "生产厂商 *",
                select_options,
                index=default_vendor_index,
            )

            custom_vendor = ""
            if selected_vendor == "其他":
                custom_vendor = st.text_input(
                    "请输入厂商名称",
                    value=current_vendor if current_vendor not in vendor_options else "",
                    placeholder="例如: 华为",
                )

            vendor = custom_vendor if selected_vendor == "其他" else selected_vendor

            port = st.number_input(
                "端口",
                min_value=1,
                max_value=65535,
                value=_safe_port(initial.get("端口", 22)),
            )

        remark = st.text_area(
            "备注",
            value=str(initial.get("备注", "")),
            placeholder="可选的设备备注信息",
        )

        submitted = st.form_submit_button(submit_label, type="primary", use_container_width=True)

    if not submitted:
        return False, None, []

    errors = []
    if not device_name.strip():
        errors.append("设备名不能为空")
    if not ip_address.strip():
        errors.append("IP 地址不能为空")
    if not vendor.strip():
        errors.append("生产厂商不能为空")

    if ip_address.strip():
        is_valid_ip, ip_error = validate_ip_address(ip_address.strip())
        if not is_valid_ip:
            errors.append(f"IP 地址格式错误: {ip_error}")

    device = {
        "设备名": device_name.strip(),
        "IP地址": ip_address.strip(),
        "生产厂商": vendor.strip(),
        "端口": str(port),
        "备注": remark.strip(),
    }

    return True, device, errors


def show_delete_device_form():
    """显示删除设备表单"""
    st.subheader("🗑️ 删除设备")
    
    manager = st.session_state.device_manager
    devices = manager.load_devices()
    
    if not devices:
        st.warning("没有可删除的设备")
        return
    
    # 选择要删除的设备
    device_names = [d["设备名"] for d in devices]
    selected_device = st.selectbox("选择要删除的设备", device_names)
    
    if selected_device:
        # 显示设备详情
        device_info = None
        for device in devices:
            if device["设备名"] == selected_device:
                device_info = device
                break
        
        if device_info:
            # 显示设备详情
            st.warning(f"⚠️ 即将删除设备: {selected_device}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.info(f"**IP地址:** {device_info['IP地址']}")
                st.info(f"**厂商:** {device_info['生产厂商']}")
            with col2:
                st.info(f"**端口:** {device_info.get('端口', '22')}")
                if device_info.get('备注'):
                    st.info(f"**备注:** {device_info['备注']}")
            
            st.markdown("---")
            
            # 确认删除
            confirm = st.checkbox("我确认要删除此设备，此操作不可恢复")
            
            if confirm:
                if st.button("🗑️ 确认删除", type="primary", use_container_width=True):
                    with st.spinner("正在删除设备..."):
                        if manager.delete_device(selected_device):
                            st.success(f"✅ 设备 '{selected_device}' 已删除！")
                            st.session_state.refresh_counter += 1
                            st.rerun()
                        else:
                            st.error("❌ 删除设备失败")


def show_statistics():
    """显示统计分析"""
    st.subheader("📈 设备统计分析")
    
    manager = st.session_state.device_manager
    stats = manager.get_statistics()
    devices = manager.load_devices()
    
    # 总体统计
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("设备总数", stats["total_devices"])
    with col2:
        st.metric("厂商数量", len(stats["vendor_stats"]))
    with col3:
        # 统计非默认端口设备数
        non_default_ports = sum(1 for d in devices if d.get("端口", "22") != "22")
        st.metric("非默认端口", non_default_ports)
    with col4:
        # 统计有备注的设备数
        with_remarks = sum(1 for d in devices if d.get("备注", "").strip())
        st.metric("有备注设备", with_remarks)
    
    st.markdown("---")
    
    # 厂商分布
    st.subheader("厂商分布")
    if stats["vendor_stats"]:
        vendor_df = pd.DataFrame(
            list(stats["vendor_stats"].items()),
            columns=["厂商", "设备数量"]
        ).sort_values("设备数量", ascending=False)
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.bar_chart(vendor_df.set_index("厂商"))
        with col2:
            st.dataframe(vendor_df, use_container_width=True)
    else:
        st.info("暂无设备数据")
    
    st.markdown("---")
    
    # 端口分布统计
    st.subheader("端口分布")
    if devices:
        port_stats = {}
        for device in devices:
            port = device.get("端口", "22")
            port_stats[port] = port_stats.get(port, 0) + 1
        
        port_df = pd.DataFrame(
            list(port_stats.items()),
            columns=["端口", "设备数量"]
        ).sort_values("设备数量", ascending=False)
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.bar_chart(port_df.set_index("端口"))
        with col2:
            st.dataframe(port_df, use_container_width=True)
    else:
        st.info("暂无设备数据")
    
    st.markdown("---")
    
    # 数据质量检查
    st.subheader("🔍 数据质量检查")
    
    if devices:
        # 检查重复设备名
        device_names = [d["设备名"] for d in devices]
        duplicate_names = [name for name in set(device_names) if device_names.count(name) > 1]
        
        # 检查重复IP地址
        ip_addresses = [d["IP地址"] for d in devices]
        duplicate_ips = [ip for ip in set(ip_addresses) if ip_addresses.count(ip) > 1]
        
        # 检查无效端口
        invalid_ports = []
        for device in devices:
            port = device.get("端口", "22")
            try:
                port_num = int(port)
                if port_num < 1 or port_num > 65535:
                    invalid_ports.append(device["设备名"])
            except ValueError:
                invalid_ports.append(device["设备名"])
        
        # 检查无效IP地址
        invalid_ips = []
        for device in devices:
            is_valid, _ = validate_ip_address(device["IP地址"])
            if not is_valid:
                invalid_ips.append((device["设备名"], device["IP地址"]))
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if duplicate_names:
                st.error(f"重复设备名: {len(duplicate_names)} 个")
                with st.expander("查看详情"):
                    for name in duplicate_names:
                        st.write(f"- {name}")
            else:
                st.success("设备名唯一性: ✓")
        
        with col2:
            if duplicate_ips:
                st.error(f"重复IP地址: {len(duplicate_ips)} 个")
                with st.expander("查看详情"):
                    for ip in duplicate_ips:
                        st.write(f"- {ip}")
            else:
                st.success("IP地址唯一性: ✓")
        
        with col3:
            if invalid_ports:
                st.error(f"无效端口: {len(invalid_ports)} 个")
                with st.expander("查看详情"):
                    for name in invalid_ports:
                        st.write(f"- {name}")
            else:
                st.success("端口有效性: ✓")
        
        with col4:
            if invalid_ips:
                st.error(f"无效IP: {len(invalid_ips)} 个")
                with st.expander("查看详情"):
                    for name, ip in invalid_ips:
                        st.write(f"- {name}: {ip}")
            else:
                st.success("IP格式有效性: ✓")
    else:
        st.info("暂无设备数据可检查")
    
    st.markdown("---")
    
    # 导出统计报告
    st.subheader("📥 导出统计报告")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("导出厂商分布报告", use_container_width=True):
            if stats["vendor_stats"]:
                vendor_df = pd.DataFrame(
                    list(stats["vendor_stats"].items()),
                    columns=["厂商", "设备数量"]
                ).sort_values("设备数量", ascending=False)
                csv = vendor_df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 下载厂商分布 CSV",
                    data=csv,
                    file_name=f"vendor_stats_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                )
    
    with col2:
        if st.button("导出完整统计报告", use_container_width=True):
            report = {
                "统计时间": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                "设备总数": stats["total_devices"],
                "厂商数量": len(stats["vendor_stats"]),
                "非默认端口设备": sum(1 for d in devices if d.get("端口", "22") != "22"),
                "有备注设备": sum(1 for d in devices if d.get("备注", "").strip()),
                "数据质量": {
                    "重复设备名": len([name for name in set([d["设备名"] for d in devices]) if [d["设备名"] for d in devices].count(name) > 1]),
                    "重复IP地址": len([ip for ip in set([d["IP地址"] for d in devices]) if [d["IP地址"] for d in devices].count(ip) > 1]),
                }
            }
            import json
            json_str = json.dumps(report, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 下载完整统计 JSON",
                data=json_str,
                file_name=f"full_stats_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
            )


def export_to_csv():
    """导出设备数据为CSV"""
    manager = st.session_state.device_manager
    devices = manager.load_devices()
    
    if devices:
        df = pd.DataFrame(devices)
        csv = df.to_csv(index=False).encode('utf-8-sig')
        
        st.download_button(
            label="📥 下载CSV文件",
            data=csv,
            file_name="devices_export.csv",
            mime="text/csv",
        )
    else:
        st.warning("没有设备数据可导出")


def import_from_csv():
    """从CSV导入设备数据"""
    st.subheader("📤 导入CSV数据")
    
    st.markdown("""
    **导入说明:**
    1. 请先下载示例CSV模板或导出当前数据作为参考
    2. CSV文件必须包含：设备名、IP地址、生产厂商
    3. 导入时会自动跳过设备名重复的记录
    """)
    
    uploaded_file = st.file_uploader("选择CSV文件", type="csv")
    
    if uploaded_file is not None:
        try:
            # 读取上传的CSV
            df = pd.read_csv(uploaded_file)
            
            # 检查必需列
            required_cols = ["设备名", "IP地址", "生产厂商"]
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                st.error(f"导入失败: CSV文件缺少必需列 {missing_cols}")
                return
            
            st.info(f"解析成功，共找到 {len(df)} 条记录")
            
            if st.button("确认导入", type="primary"):
                manager = st.session_state.device_manager
                success_count = 0
                skip_count = 0
                
                # 转换为字典列表准备导入
                for _, row in df.iterrows():
                    # 跳过空行
                    if pd.isna(row.get("设备名")) or pd.isna(row.get("IP地址")) or pd.isna(row.get("生产厂商")):
                        continue
                        
                    device = {
                        "设备名": str(row["设备名"]).strip(),
                        "IP地址": str(row["IP地址"]).strip(),
                        "生产厂商": str(row["生产厂商"]).strip(),
                    }
                    
                    if "端口" in df.columns and pd.notna(row["端口"]):
                        device["端口"] = str(row["端口"]).strip()
                    else:
                        device["端口"] = "22"
                        
                    if "备注" in df.columns and pd.notna(row["备注"]):
                        device["备注"] = str(row["备注"]).strip()
                    else:
                        device["备注"] = ""
                    
                    # 尝试添加设备
                    if manager.add_device(device):
                        success_count += 1
                    else:
                        skip_count += 1
                
                if success_count > 0:
                    st.success(f"导入完成！成功添加 {success_count} 台设备，跳过 {skip_count} 台已有设备。")
                    st.session_state.refresh_counter += 1
                else:
                    st.warning(f"没有添加新设备。跳过了 {skip_count} 台已有设备或无效数据。")
                    
        except Exception as e:
            st.error(f"导入失败: {str(e)}")


def show_import_export():
    """显示导入导出页面"""
    st.subheader("📦 导入与导出")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📥 导出数据")
        st.markdown("将当前所有设备数据导出为CSV文件，可用作备份或修改模板。")
        export_to_csv()
        
    with col2:
        st.markdown("### 📤 导入数据")
        import_from_csv()

def run_process_and_capture_output(command, cwd):
    """后台线程运行进程并捕获输出"""
    try:
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=cwd,
            env=env,
            encoding='utf-8',  # 强制使用utf-8
            errors='replace'  # 忽略解码错误
        )
        
        # 将进程对象存入session_state是不安全的，因为Streamlit的并发模型
        # 这里我们使用简单的全局变量或临时文件可能更可靠
        # 但为了演示，我们假设在单用户模式下直接读取
        
        return process
    except Exception as e:
        st.error(f"启动进程失败: {e}")
        return None

def show_inspection_page():
    """显示巡检控制页面"""
    st.subheader("🚀 启动设备巡检")
    
    # 巡检配置
    with st.expander("⚙️ 巡检参数配置", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            log_mode = st.checkbox("日志收集模式 (--logmode)", help="只收集日志，不执行完整巡检")
            dry_run = st.checkbox("模拟运行 (--dry-run)", help="不实际连接设备，仅检查流程")
        
        with col2:
            vendor = st.selectbox("指定厂商 (--vendor)", ["全部"] + st.session_state.device_manager.get_vendors())
            target_ip = st.text_input("指定IP (--ip)", placeholder="可选，例如 192.168.1.1")
    
    st.markdown("---")
    
    # 启动/停止控制
    col_btn1, col_btn2 = st.columns([1, 1])
    
    with col_btn1:
        if not st.session_state.get('inspection_running', False):
            if st.button("🚀 开始巡检", type="primary", use_container_width=True):
                # 构建命令
                cmd = [sys.executable, "-X", "utf8", "-u", "main.py"]  # -u for unbuffered stdout
                cmd.append("--yes")  # Web模式下自动确认
                if log_mode:
                    cmd.append("--logmode")
                if dry_run:
                    cmd.append("--dry-run")
                if vendor != "全部":
                    cmd.extend(["--vendor", vendor])
                if target_ip:
                    cmd.extend(["--ip", target_ip])
                
                # 设置运行状态
                st.session_state.inspection_running = True
                st.session_state.inspection_output = "正在启动巡检任务...\n"
                st.session_state.inspection_start_time = time.time()
                
                # 启动进程
                cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                try:
                    env = os.environ.copy()
                    env["PYTHONIOENCODING"] = "utf-8"
                    env["PYTHONUTF8"] = "1"

                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        cwd=cwd,
                        env=env,
                        encoding='utf-8',
                        errors='replace'
                    )
                    st.session_state.process = process
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 启动失败: {e}")
                    st.session_state.inspection_running = False
        else:
            if st.button("⏹️ 停止巡检", type="secondary", use_container_width=True):
                if 'process' in st.session_state and st.session_state.process:
                    st.session_state.process.terminate()
                    try:
                        st.session_state.process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        st.session_state.process.kill()
                    
                    st.session_state.inspection_running = False
                    st.warning("⚠️ 巡检已停止")
                    if 'process' in st.session_state:
                        del st.session_state.process
                    st.rerun()
    
    with col_btn2:
        # 显示运行状态
        if st.session_state.get('inspection_running', False):
            elapsed = int(time.time() - st.session_state.get('inspection_start_time', time.time()))
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            st.info(f"⏱️ 运行时间: {hours:02d}:{minutes:02d}:{seconds:02d}")
        else:
            st.info("⏸️ 巡检未运行")
    
    st.markdown("---")
    
    # 实时日志显示逻辑
    if st.session_state.get('inspection_running', False) and 'process' in st.session_state:
        process = st.session_state.process
        
        # 显示运行状态
        st.info("🔄 巡检正在运行中... (请勿刷新页面)")
        
        # 使用 st.empty 作为占位符
        output_placeholder = st.empty()
        
        # 直接从进程读取输出
        output_lines = []
        
        while True:
            # 检查进程状态
            if process.poll() is not None:
                # 读取剩余输出
                remaining_output = process.stdout.read()
                if remaining_output:
                    output_lines.append(remaining_output)
                
                st.session_state.inspection_running = False
                st.session_state.inspection_output = ''.join(output_lines)
                
                # 显示完成状态
                st.success("✅ 巡检任务已完成！")
                break
            
            # 读取可用输出
            line = process.stdout.readline()
            if line:
                output_lines.append(line)
                
                # 限制显示的日志长度，避免浏览器卡顿
                display_output = ''.join(output_lines[-500:])  # 只显示最后500行
                
                # 更新显示
                with output_placeholder.container():
                    st.markdown("### 📜 实时巡检日志")
                    st.code(display_output, language="text")
            
            time.sleep(0.05)  # 每50ms更新一次
        
        # 显示最终日志
        st.markdown("### 📜 巡检日志")
        st.code(''.join(output_lines), language="text")
        
        # 清理
        if 'process' in st.session_state:
            del st.session_state.process
    
    else:
        # 显示历史日志
        if st.session_state.get('inspection_output'):
            st.markdown("### 📜 巡检日志")
            st.code(st.session_state.inspection_output, language="text")
            
            # 导出日志按钮
            if st.button("📥 导出巡检日志", use_container_width=True):
                log_content = st.session_state.inspection_output
                st.download_button(
                    label="下载日志文件",
                    data=log_content.encode('utf-8'),
                    file_name=f"inspection_log_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.log",
                    mime="text/plain",
                )

def main():
    """主函数"""
    # 初始化
    init_session_state()
    
    # 显示页面标题
    show_header()
    
    # 显示侧边栏并获取操作选择
    operation, search_keyword, vendor_filter = show_sidebar()
    
    # 根据选择显示对应内容
    if operation == "📋 查看设备":
        show_device_table(search_keyword, vendor_filter)
    elif operation == "➕ 添加设备":
        show_add_device_form()
    elif operation == "✏️ 编辑设备":
        show_edit_device_form()
    elif operation == "🗑️ 删除设备":
        show_delete_device_form()
    elif operation == "📈 统计分析":
        show_statistics()
    elif operation == "📦 导入导出":
        show_import_export()
    elif operation == "🚀 启动巡检":
        show_inspection_page()


if __name__ == "__main__":
    main()
