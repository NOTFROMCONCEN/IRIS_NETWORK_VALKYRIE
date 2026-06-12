#!/usr/bin/env python3
"""
设备管理UI应用 - 基于Streamlit的设备增删改查界面
"""

import subprocess
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

try:
    from ..core.paths import resolve_corebase_path
    from .device_manager import DeviceManager
    from ..core.lock import check_inspection_status, InspectionLock
except ImportError:
    from core.paths import resolve_corebase_path
    from ui.device_manager import DeviceManager
    from core.lock import check_inspection_status, InspectionLock


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
    if "device_manager" not in st.session_state:
        st.session_state.device_manager = DeviceManager()
    if "refresh_counter" not in st.session_state:
        st.session_state.refresh_counter = 0
    if "edit_device_name" not in st.session_state:
        st.session_state.edit_device_name = None
    if "inspection_running" not in st.session_state:
        st.session_state.inspection_running = False
    if "inspection_output" not in st.session_state:
        st.session_state.inspection_output = ""
    if "inspection_log_path" not in st.session_state:
        st.session_state.inspection_log_path = None
    if "inspection_returncode" not in st.session_state:
        st.session_state.inspection_returncode = None


def read_inspection_output(log_path: str | None, max_lines: int | None = None) -> str:
    """读取巡检日志文件内容。"""
    if not log_path:
        return ""

    path = Path(log_path)
    if not path.exists():
        return ""

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        if max_lines is not None:
            lines = lines[-max_lines:]
        return "".join(lines)
    except Exception as e:
        return f"[日志读取失败] {e}"


def build_inspection_cli_args(
    log_mode: bool,
    dry_run: bool,
    vendor: str,
    target_group: str,
    target_ip: str,
    config_path: str = "",
    output_dir: str = "",
    force: bool = False,
) -> list[str]:
    """构造巡检 CLI 参数，供 UI 启动和预览共用。"""
    args = ["main.py", "--yes"]

    if log_mode:
        args.append("--logmode")
    if dry_run:
        args.append("--dry-run")
    if vendor != "全部":
        args.extend(["--vendor", vendor])
    if target_group != "全部分组":
        args.extend(["--group", target_group])
    if target_ip.strip():
        args.extend(["--ip", target_ip.strip()])
    if config_path.strip():
        args.extend(["--config", config_path.strip()])
    if output_dir.strip():
        args.extend(["--output-dir", output_dir.strip()])
    if force:
        args.append("--force")

    return args


def start_inspection_process(
    log_mode: bool,
    dry_run: bool,
    vendor: str,
    target_group: str,
    target_ip: str,
    config_path: str = "",
    output_dir: str = "",
):
    """启动巡检子进程，并将输出写入日志文件。"""
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        "-u",
        *build_inspection_cli_args(
            log_mode,
            dry_run,
            vendor,
            target_group,
            target_ip,
            config_path,
            output_dir,
        ),
    ]

    cwd = str(resolve_corebase_path("."))
    log_dir = resolve_corebase_path("output/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = (
        log_dir / f"inspection_ui_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    log_handle = open(log_path, "w", encoding="utf-8")
    try:
        process = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=cwd,
            env=env,
        )
    finally:
        log_handle.close()

    st.session_state.process = process
    st.session_state.inspection_running = True
    st.session_state.inspection_output = ""
    st.session_state.inspection_log_path = str(log_path)
    st.session_state.inspection_returncode = None
    st.session_state.inspection_start_time = time.time()


def stop_inspection_process():
    """停止巡检子进程并保留当前日志输出。"""
    process = st.session_state.get("process")
    if process:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        st.session_state.inspection_returncode = process.returncode

    st.session_state.inspection_running = False
    st.session_state.inspection_output = read_inspection_output(
        st.session_state.get("inspection_log_path")
    )
    if "process" in st.session_state:
        del st.session_state.process


@st.fragment(run_every="2s")
def render_running_inspection_fragment():
    """轮询巡检进程状态并自动刷新日志输出。"""
    process = st.session_state.get("process")
    if not st.session_state.get("inspection_running", False) or not process:
        return

    returncode = process.poll()
    if returncode is not None:
        st.session_state.inspection_running = False
        st.session_state.inspection_returncode = returncode
        st.session_state.inspection_output = read_inspection_output(
            st.session_state.get("inspection_log_path")
        )
        if "process" in st.session_state:
            del st.session_state.process
        st.rerun()
        return

    elapsed = int(
        time.time() - st.session_state.get("inspection_start_time", time.time())
    )
    hours, remainder = divmod(elapsed, 3600)
    minutes, seconds = divmod(remainder, 60)

    st.info("🔄 巡检正在运行中，日志每 2 秒自动刷新一次")
    st.caption(f"⏱️ 运行时间: {hours:02d}:{minutes:02d}:{seconds:02d}")
    st.markdown("### 📜 实时巡检日志")
    st.code(
        read_inspection_output(
            st.session_state.get("inspection_log_path"), max_lines=500
        ),
        language="text",
    )


def show_header():
    """显示页面标题"""
    st.set_page_config(
        page_title="网络设备管理",
        page_icon="🖧",
        layout="wide",
        initial_sidebar_state="expanded",
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

            last_mod = datetime.fromtimestamp(stats["last_modified"]).strftime(
                "%Y-%m-%d %H:%M"
            )
            st.metric("🕒 最后修改", last_mod)
        else:
            st.metric("🕒 最后修改", "无")
    with col4:
        st.metric("📄 文件路径", "devices.xlsx")

    st.markdown("---")


def show_sidebar():
    """显示侧边栏"""
    manager = st.session_state.device_manager

    with st.sidebar:
        st.header("📊 操作菜单")

        # 操作选择
        operation = st.radio(
            "选择操作",
            [
                "📋 查看设备",
                "➕ 添加设备",
                "✏️ 编辑设备",
                "🗑️ 删除设备",
                "📈 统计分析",
                "📦 导入导出",
                "🔍 设备发现",
                "� 启动巡检",
            ],
            key="operation_select",
        )

        st.markdown("---")

        # 搜索和过滤
        st.header("🔍 搜索过滤")
        search_keyword = st.text_input("搜索设备名或IP地址", "")
        group_filter = st.selectbox(
            "按分组过滤", ["全部分组"] + manager.get_device_groups()
        )
        vendor_filter = st.selectbox("按厂商过滤", ["全部厂商"] + manager.get_vendors())

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
            st.markdown(
                """
            **设备字段说明:**
            - **设备名**: 设备的唯一标识名称
            - **IP地址**: 设备的IP地址
            - **生产厂商**: 设备厂商（如华为、H3C等）
            - **端口**: SSH端口，默认22
            - **备注**: 设备备注信息

            **最新巡检筛选支持:**
            - **厂商**: 使用程序当前支持的厂商关键字
            - **分组**: 兼容 `分组_设备名`、`[分组]设备名`、`分组-设备名`
            - **IP**: 可直接指定单台设备
            
            **支持的操作:**
            1. 查看所有设备列表
            2. 添加新设备
            3. 编辑现有设备
            4. 删除设备
            5. 搜索和过滤设备
            6. 导入/导出数据
            7. 启动设备巡检
            """
            )

    return operation, search_keyword, group_filter, vendor_filter


def show_device_table(
    search_keyword="", group_filter="全部分组", vendor_filter="全部厂商"
):
    """显示设备表格"""
    manager = st.session_state.device_manager

    # 获取设备列表
    vendor = vendor_filter if vendor_filter != "全部厂商" else ""
    group = group_filter if group_filter != "全部分组" else ""
    devices = manager.search_devices(search_keyword, vendor, group)

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
            "设备名": st.column_config.TextColumn(
                "设备名", width="medium", required=True
            ),
            "IP地址": st.column_config.TextColumn(
                "IP地址", width="medium", required=True
            ),
            "生产厂商": st.column_config.SelectboxColumn(
                "生产厂商",
                width="medium",
                options=manager.get_vendor_options(),
                required=True,
            ),
            "端口": st.column_config.NumberColumn(
                "端口",
                width="small",
                min_value=1,
                max_value=65535,
                default=22,
                help="SSH 端口号，默认 22",
            ),
            "备注": st.column_config.TextColumn("备注", width="large"),
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key="device_table",
    )

    # 保存修改
    if not edited_df.equals(df):
        if st.button("💾 保存所有修改", type="primary", use_container_width=True):
            try:
                with show_loading("正在保存设备信息..."):
                    # 转换为设备列表
                    updated_devices = edited_df.to_dict("records")
                    if manager.save_devices(updated_devices):
                        show_success_message(
                            f"成功保存 {len(updated_devices)} 台设备信息"
                        )
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

    csv = df.to_csv(index=False).encode("utf-8-sig")

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
    ipv4_pattern = r"^(\d{1,3}\.){3}\d{1,3}$"
    if re.match(ipv4_pattern, ip):
        octets = ip.split(".")
        if all(0 <= int(octet) <= 255 for octet in octets):
            return True, ""
        else:
            return False, "IP 地址的每个字节必须在 0-255 之间"

    # IPv6 验证（简化版）
    if ":" in ip:
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
        show_error_message(
            "表单验证失败", "\n".join(f"  • {error}" for error in errors)
        )
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
                show_error_message(
                    "表单验证失败", "\n".join(f"  • {error}" for error in errors)
                )
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
            vendor_options = manager.get_vendor_options()
            select_options = vendor_options + ["其他"]
            current_vendor = str(initial.get("生产厂商", "")).strip()

            if current_vendor and current_vendor not in vendor_options:
                default_vendor_index = len(select_options) - 1
            else:
                default_vendor_index = (
                    vendor_options.index(current_vendor)
                    if current_vendor in vendor_options
                    else 0
                )

            selected_vendor = st.selectbox(
                "生产厂商 *",
                select_options,
                index=default_vendor_index,
            )

            custom_vendor = ""
            if selected_vendor == "其他":
                custom_vendor = st.text_input(
                    "请输入厂商名称",
                    value=(
                        current_vendor if current_vendor not in vendor_options else ""
                    ),
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

        submitted = st.form_submit_button(
            submit_label, type="primary", use_container_width=True
        )

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
                if device_info.get("备注"):
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
            list(stats["vendor_stats"].items()), columns=["厂商", "设备数量"]
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
            list(port_stats.items()), columns=["端口", "设备数量"]
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
        duplicate_names = [
            name for name in set(device_names) if device_names.count(name) > 1
        ]

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
                    list(stats["vendor_stats"].items()), columns=["厂商", "设备数量"]
                ).sort_values("设备数量", ascending=False)
                csv = vendor_df.to_csv(index=False).encode("utf-8-sig")
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
                "非默认端口设备": sum(
                    1 for d in devices if d.get("端口", "22") != "22"
                ),
                "有备注设备": sum(1 for d in devices if d.get("备注", "").strip()),
                "数据质量": {
                    "重复设备名": len(
                        [
                            name
                            for name in set([d["设备名"] for d in devices])
                            if [d["设备名"] for d in devices].count(name) > 1
                        ]
                    ),
                    "重复IP地址": len(
                        [
                            ip
                            for ip in set([d["IP地址"] for d in devices])
                            if [d["IP地址"] for d in devices].count(ip) > 1
                        ]
                    ),
                },
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
        csv = df.to_csv(index=False).encode("utf-8-sig")

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

    st.markdown(
        """
    **导入说明:**
    1. 请先下载示例CSV模板或导出当前数据作为参考
    2. CSV文件必须包含：设备名、IP地址、生产厂商
    3. 导入时会自动跳过设备名重复的记录
    """
    )

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
                    if (
                        pd.isna(row.get("设备名"))
                        or pd.isna(row.get("IP地址"))
                        or pd.isna(row.get("生产厂商"))
                    ):
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
                    st.success(
                        f"导入完成！成功添加 {success_count} 台设备，跳过 {skip_count} 台已有设备。"
                    )
                    st.session_state.refresh_counter += 1
                else:
                    st.warning(
                        f"没有添加新设备。跳过了 {skip_count} 台已有设备或无效数据。"
                    )

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


def show_discovery_page():
    """显示设备发现页面"""
    st.subheader("🔍 设备自发现")

    # 初始化发现相关的 session_state
    if "discovery_result" not in st.session_state:
        st.session_state.discovery_result = None
    if "discovery_running" not in st.session_state:
        st.session_state.discovery_running = False

    # ---- 配置区 ----
    st.markdown("### 发现配置")

    discover_mode = st.radio(
        "发现模式",
        ["lldp", "subnet", "all"],
        format_func=lambda x: {
            "lldp": "🔗 LLDP/CDP 邻居发现",
            "subnet": "🌐 子网扫描",
            "all": "🔗🌐 组合发现 (LLDP + 子网扫描)",
        }[x],
        horizontal=True,
        key="discover_mode",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**LLDP 配置**")
        depth = st.slider("递归深度", min_value=1, max_value=5, value=3, key="discover_depth")
        seed_ip = st.text_input("种子设备IP (可选，留空使用清单全部设备)", key="discover_seed_ip")

    with col2:
        st.markdown("**子网扫描配置**")
        subnets_str = st.text_input(
            "扫描子网 (CIDR格式，逗号分隔)",
            placeholder="如: 192.168.1.0/24,10.0.0.0/24",
            key="discover_subnets",
        )
        discover_dry_run = st.checkbox("仅探测可达性 (不尝试SSH登录)", key="discover_dry_run")

    # ---- 执行区 ----
    st.markdown("---")

    if st.button("🚀 开始发现", type="primary", use_container_width=True, disabled=st.session_state.discovery_running):
        # 验证参数
        subnets = [s.strip() for s in subnets_str.split(",") if s.strip()] if subnets_str else []

        if discover_mode in ("subnet", "all") and not subnets:
            show_error_message("子网扫描模式需要输入至少一个子网")
        else:
            st.session_state.discovery_running = True
            st.session_state.discovery_result = None

            try:
                # 加载配置和凭证
                try:
                    from core.utils import load_config, load_passwords, load_devices, update_devices_with_passwords
                except ImportError:
                    from ..core.utils import load_config, load_passwords, load_devices, update_devices_with_passwords

                try:
                    from core.discovery import DiscoveryManager
                except ImportError:
                    from ..core.discovery import DiscoveryManager

                try:
                    from core.paths import resolve_corebase_path
                except ImportError:
                    from ..core.paths import resolve_corebase_path

                config = load_config()
                passwords = load_passwords()

                # 构建排除IP和种子设备
                excel_file = resolve_corebase_path("devices/devices.xlsx")
                existing_ips = set()
                seed_devices = []

                if excel_file.exists():
                    try:
                        devices = load_devices(str(excel_file))
                        devices = update_devices_with_passwords(devices, passwords)
                        existing_ips = {d.get("ip", "") for d in devices if d.get("ip")}

                        if discover_mode in ("lldp", "all"):
                            if seed_ip:
                                seed_devices = [d for d in devices if d.get("ip") == seed_ip]
                                if not seed_devices:
                                    show_error_message(f"未找到IP为 {seed_ip} 的设备")
                                    st.session_state.discovery_running = False
                                    st.stop()
                            else:
                                seed_devices = list(devices)
                    except Exception as e:
                        show_warning_message(f"加载设备清单失败: {e}")

                # 创建发现管理器
                discovery_mgr = DiscoveryManager(config, passwords)

                # 进度占位符
                progress_placeholder = st.empty()
                status_placeholder = st.empty()

                def progress_callback(msg):
                    status_placeholder.info(f"⏳ {msg}")

                # 执行发现
                if discover_mode == "lldp":
                    if not seed_devices:
                        show_error_message("LLDP发现需要种子设备，请在清单中添加设备或指定种子IP")
                        st.session_state.discovery_running = False
                        st.stop()
                    result = discovery_mgr.discover_from_seeds(
                        seed_devices=seed_devices,
                        max_depth=depth,
                        exclude_ips=existing_ips,
                        progress_callback=progress_callback,
                    )
                elif discover_mode == "subnet":
                    result = discovery_mgr.scan_subnets(
                        subnets=subnets,
                        exclude_ips=existing_ips,
                        dry_run=discover_dry_run,
                        progress_callback=progress_callback,
                    )
                else:  # all
                    result = discovery_mgr.combined_discover(
                        seed_devices=seed_devices,
                        subnets=subnets,
                        max_depth=depth,
                        exclude_ips=existing_ips,
                        dry_run=discover_dry_run,
                        progress_callback=progress_callback,
                    )

                st.session_state.discovery_result = result
                progress_placeholder.empty()
                status_placeholder.empty()

            except Exception as e:
                show_error_message(f"发现过程异常: {e}")
            finally:
                st.session_state.discovery_running = False

    # ---- 结果展示区 ----
    result = st.session_state.discovery_result
    if result is not None:
        st.markdown("---")
        st.markdown("### 📊 发现结果")

        # 汇总指标
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("总计发现", result.total_found)
        col2.metric("已识别", sum(1 for d in result.devices if d.identified))
        col3.metric("去重移除", result.duplicates_removed)
        col4.metric("已在清单", result.already_in_inventory)
        col5.metric("新设备", len(result.new_devices))

        if result.errors:
            with st.expander("⚠️ 发现过程中的警告"):
                for err in result.errors:
                    st.warning(err)

        # 设备表格
        if result.devices:
            st.markdown("#### 发现设备列表")

            # 转为 DataFrame 展示
            table_data = result.to_table_data()
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # 导出按钮
            col_export1, col_export2 = st.columns(2)
            with col_export1:
                if st.button("📥 导出结果到 Excel"):
                    try:
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False, dir=str(
                            Path(__file__).parent.parent / "output" / "results"
                        )) as tmp:
                            df.to_excel(tmp.name, index=False)
                            show_success_message(f"已导出到: {tmp.name}")
                    except Exception as e:
                        show_error_message(f"导出失败: {e}")

            with col_export2:
                if st.button("📥 导出为 CSV"):
                    csv_data = df.to_csv(index=False).encode("utf-8-sig")
                    st.download_button(
                        label="下载 CSV 文件",
                        data=csv_data,
                        file_name="discovered_devices.csv",
                        mime="text/csv",
                    )

            # 导入设备到清单
            new_devices = result.new_devices
            if new_devices:
                st.markdown("---")
                st.markdown("### 📥 导入设备到清单")

                st.info(f"发现 {len(new_devices)} 台新设备可以导入到设备清单")

                # 设备选择
                selected_indices = []
                for i, dev in enumerate(new_devices):
                    vendor_str = dev.vendor_raw or dev.vendor or "?"
                    default_checked = dev.identified
                    checked = st.checkbox(
                        f"**{dev.display_ip}** ({dev.hostname or '?'}) - {vendor_str} - {dev.source}",
                        value=default_checked,
                        key=f"discover_select_{i}",
                    )
                    if checked:
                        selected_indices.append(i)

                if selected_indices and st.button("✅ 导入选中设备", type="primary"):
                    try:
                        manager = st.session_state.device_manager
                        existing_devices = manager.load_devices()
                        imported = 0

                        for idx in selected_indices:
                            dev = new_devices[idx]
                            inv_dict = dev.to_inventory_dict()
                            ip_exists = any(
                                d.get("IP地址", "") == inv_dict["IP地址"]
                                for d in existing_devices
                            )
                            if not ip_exists:
                                existing_devices.append(inv_dict)
                                imported += 1

                        if imported > 0:
                            if manager.save_devices(existing_devices):
                                show_success_message(f"已导入 {imported} 台设备到设备清单")
                                st.session_state.discovery_result = None
                                st.rerun()
                            else:
                                show_error_message("保存设备清单失败")
                        else:
                            show_warning_message("选中的设备已存在于清单中")

                    except Exception as e:
                        show_error_message(f"导入失败: {e}")
        else:
            st.info("未发现任何新设备")


def show_inspection_page():
    """显示巡检控制页面"""
    st.subheader("🚀 启动设备巡检")
    manager = st.session_state.device_manager
    supported_vendors = manager.get_supported_vendors()
    available_groups = manager.get_device_groups()

    # 检查全局巡检锁状态（防止 CLI 与 WEB 同时执行）
    lock_status = check_inspection_status()
    external_running = (
        lock_status["running"]
        and lock_status["pid"] is not None
        and lock_status["pid"] != os.getpid()
    )

    # 巡检配置
    with st.expander("⚙️ 巡检参数配置", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            log_mode = st.checkbox(
                "日志收集模式 (--logmode)", help="只收集日志，不执行完整巡检"
            )
            dry_run = st.checkbox(
                "模拟运行 (--dry-run)", help="不实际连接设备，仅检查流程"
            )

        with col2:
            vendor = st.selectbox("指定厂商 (--vendor)", ["全部"] + supported_vendors)

            target_group = st.selectbox(
                "指定分组 (--group)", ["全部分组"] + available_groups
            )

        with col3:
            target_ip = st.text_input(
                "指定IP (--ip)", placeholder="可选，例如 192.168.1.1"
            )

            config_path = st.text_input(
                "自定义配置文件 (--config)",
                placeholder="可选，例如 config/config.yaml",
                help="支持相对 CoreBase 的路径或绝对路径；留空则使用默认配置文件。",
            )

            output_dir = st.text_input(
                "自定义结果目录 (--output-dir)",
                placeholder="可选，例如 output/results_custom",
                help="支持相对 CoreBase 的路径或绝对路径；留空则使用默认结果目录。",
            )

            st.caption(
                "支持厂商: " + ", ".join(supported_vendors)
                if supported_vendors
                else "未加载到支持厂商"
            )

    st.caption(
        "路径说明: 相对路径按 CoreBase 目录解析；配置文件不存在时主程序会回退到默认配置。"
    )

    preview_parts = [
        "python",
        *build_inspection_cli_args(
            log_mode,
            dry_run,
            vendor,
            target_group,
            target_ip,
            config_path,
            output_dir,
        ),
    ]
    st.caption("启动命令预览: " + " ".join(preview_parts))

    st.markdown("---")

    # 启动/停止控制
    col_btn1, col_btn2 = st.columns([1, 1])

    with col_btn1:
        if external_running:
            st.button(
                "🚫 巡检被占用",
                type="secondary",
                use_container_width=True,
                disabled=True,
            )
        elif not st.session_state.get("inspection_running", False):
            if st.button("🚀 开始巡检", type="primary", use_container_width=True):
                try:
                    start_inspection_process(
                        log_mode,
                        dry_run,
                        vendor,
                        target_group,
                        target_ip,
                        config_path,
                        output_dir,
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ 启动失败: {e}")
                    st.session_state.inspection_running = False
        else:
            if st.button("⏹️ 停止巡检", type="secondary", use_container_width=True):
                stop_inspection_process()
                # 同时清理全局锁（WEB 模式下子进程持有锁，但停止时主动清理）
                InspectionLock().release()
                st.warning("⚠️ 巡检已停止")
                st.rerun()

    with col_btn2:
        # 显示运行状态
        if st.session_state.get("inspection_running", False):
            elapsed = int(
                time.time() - st.session_state.get("inspection_start_time", time.time())
            )
            hours, remainder = divmod(elapsed, 3600)
            minutes, seconds = divmod(remainder, 60)
            st.info(f"⏱️ 运行时间: {hours:02d}:{minutes:02d}:{seconds:02d}")
        elif external_running:
            started = lock_status.get("started_at", "未知")
            mode = lock_status.get("mode", "未知")
            pid = lock_status.get("pid", "未知")
            st.warning(
                f"⚠️ 外部巡检正在运行\n\n"
                f"- 模式: {mode}\n"
                f"- PID: {pid}\n"
                f"- 开始于: {started}"
            )
        else:
            st.info("⏸️ 巡检未运行")

    st.markdown("---")

    if (
        st.session_state.get("inspection_running", False)
        and "process" in st.session_state
    ):
        render_running_inspection_fragment()

    else:
        # 显示历史日志
        if st.session_state.get("inspection_returncode") is not None:
            if st.session_state.inspection_returncode == 0:
                st.success("✅ 巡检任务已完成！")
            else:
                st.error(
                    f"❌ 巡检任务已结束，退出码: {st.session_state.inspection_returncode}"
                )

        if not st.session_state.get("inspection_output") and st.session_state.get(
            "inspection_log_path"
        ):
            st.session_state.inspection_output = read_inspection_output(
                st.session_state.get("inspection_log_path")
            )

        if st.session_state.get("inspection_output"):
            st.markdown("### 📜 巡检日志")
            st.code(st.session_state.inspection_output, language="text")

            # 导出日志按钮
            if st.button("📥 导出巡检日志", use_container_width=True):
                log_content = st.session_state.inspection_output
                st.download_button(
                    label="下载日志文件",
                    data=log_content.encode("utf-8"),
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
    operation, search_keyword, group_filter, vendor_filter = show_sidebar()

    # 根据选择显示对应内容
    if operation == "📋 查看设备":
        show_device_table(search_keyword, group_filter, vendor_filter)
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
    elif operation == "🔍 设备发现":
        show_discovery_page()
    elif operation == "🚀 启动巡检":
        show_inspection_page()


if __name__ == "__main__":
    main()
